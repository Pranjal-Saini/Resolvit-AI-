"""Isolated backend HTTP and gateway checks; no real demo data is reset.

Run: python -m scripts.demo_check
The deterministic agent fixture tests integration wiring without an LLM.
"""
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor

# Support the documented `python scripts/demo_check.py` invocation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import uvicorn
from backend.app import db, gateway, pii, seed
from backend.app.main import app
from shared.contracts import AgentResponse, CallContext, ToolCall


class BackendChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.original_path = db.DB_PATH
        db.DB_PATH = Path(cls.directory.name) / 'checks.db'
        seed.seed()
        cls.sock = socket.socket()
        cls.sock.bind(('127.0.0.1', 0))
        cls.base = f'http://127.0.0.1:{cls.sock.getsockname()[1]}'
        cls.server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={'sockets': [cls.sock]}, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 10
        while not cls.server.started:
            if not cls.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('test server failed to start')
            time.sleep(.02)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(10)
        db.DB_PATH = cls.original_path
        cls.directory.cleanup()
        if cls.thread.is_alive():
            raise RuntimeError('test server failed to stop')

    def setUp(self):
        seed.seed()

    def request(self, method, path, **kwargs):
        return requests.request(method, self.base + path, timeout=10, **kwargs)

    def chat(self, session='s1', customer='C001', message='hello', token=None):
        return self.request('POST', '/chat', json={'session_id': session, 'customer_id': customer, 'token': token or 'demo-' + customer, 'message': message})

    def context(self):
        response = self.chat()
        self.assertEqual(response.status_code, 200)
        return CallContext(case_id=response.json()['case_id'], session_id='s1', customer_id='C001')

    def test_gateway_safety(self):
        ctx = self.context()
        def reverse(txn, amount, policy='policy section 1'):
            return gateway.execute(ToolCall(name='reverse_payment', args={'txn_id': txn, 'amount': amount}, policy_ref=policy), ctx)
        self.assertEqual(reverse('T1001', 499, None).status, 'blocked')
        self.assertEqual(reverse('T1003', 250).status, 'blocked')
        self.assertEqual(reverse('T2001', 1000).status, 'blocked')
        for amount in (0, -1, 500):
            self.assertEqual(reverse('T1001', amount).status, 'blocked')
        for amount in (True, '499', float('nan'), float('inf')):
            self.assertEqual(reverse('T1001', amount).status, 'error')
        self.assertEqual(gateway.execute(ToolCall(name='drop_tables'), ctx).status, 'blocked')
        self.assertEqual(gateway.execute(ToolCall(name='reverse_payment'), ctx).status, 'error')
        ctx.verified = False
        self.assertEqual(reverse('T1001', 499).status, 'blocked')
        ctx.verified = True
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: reverse('T1001', 499), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0].status, 'ok')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 1699)
        approval = reverse('T1002', 5000)
        self.assertEqual(approval.status, 'needs_approval')
        self.assertEqual(reverse('T1002', 5000).approval_id, approval.approval_id)
        response = self.request('POST', f'/cases/{ctx.case_id}/approve', json={'reviewer': 'Reviewer'})
        self.assertEqual(response.json()['result']['status'], 'ok')
        self.assertEqual(response.json()['status'], 'resolved')
        self.assertEqual(self.request('POST', f'/cases/{ctx.case_id}/approve', json={'reviewer': 'Reviewer'}).status_code, 409)
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 6699)
        self.assertTrue({'blocked', 'needs_approval', 'executed', 'replayed'} <= {row['decision'] for row in self.request('GET', '/audit').json()})

    def test_pii_sensitive_rejection(self):
        ctx = self.context()
        text = '9876543210 rahul@example.com rahul@paytm 1234567890123456'
        masked = pii.mask(text, 's1')
        self.assertEqual(masked, '<PHONE_1> <EMAIL_1> <UPI_1> <ACCT_1>')
        self.assertEqual(pii.mask(text, 's1'), masked)
        self.assertEqual(pii.unmask({'x': [masked]}, 's1'), {'x': [text]})
        result = gateway.execute(ToolCall(name='get_customer_profile'), ctx)
        self.assertNotIn('9876543210', json.dumps(result.data))
        call = ToolCall(name='update_registered_phone', args={'new_phone': '<PHONE_1>'})
        self.assertEqual(gateway.execute(call, ctx).status, 'needs_approval')
        response = self.request('POST', f'/cases/{ctx.case_id}/reject', json={'reviewer': 'Reviewer', 'note': 'Please verify identity'})
        self.assertEqual(response.json()['status'], 'rejected')
        self.assertEqual(self.request('POST', f'/cases/{ctx.case_id}/approve', json={'reviewer': 'Reviewer'}).status_code, 409)
        other = self.chat(session='s2').json()['case_id']
        ctx = CallContext(case_id=other, session_id='s2', customer_id='C001', step_up_passed=True)
        self.assertEqual(gateway.execute(ToolCall(name='update_registered_phone', args={'new_phone': '9988776655'}), ctx).status, 'ok')
        self.assertNotIn('9988776655', json.dumps(self.request('GET', '/audit').json()))

    def test_http_fixture_scenarios(self):
        def fixture(message, history, ctx, gateway):
            if 'hacked' in message:
                call = ToolCall(name='freeze_wallet', args={'reason': 'compromise'})
            else:
                large = '5000' in message
                call = ToolCall(name='reverse_payment', args={'txn_id': 'T1002' if large else 'T1001', 'amount': 5000 if large else 499}, policy_ref='demo policy section 1')
            result = gateway.execute(call, ctx)
            return AgentResponse(reply='Processed', status='resolved' if result.status == 'ok' else 'awaiting_approval')
        engine = types.ModuleType('engine')
        agent = types.ModuleType('engine.agent')
        agent.run_agent = fixture
        from unittest.mock import patch
        with patch.dict(sys.modules, {'engine': engine, 'engine.agent': agent}):
            small = self.chat(message='499 debited for electricity bill but failed').json()
            self.assertEqual(small['status'], 'resolved')
            self.assertEqual(db.fetch_one("SELECT status FROM transactions WHERE id='T1001'")['status'], 'reversed')
            large = self.chat('large', message='5000 flight booking failed').json()
            self.assertEqual(large['status'], 'awaiting_approval')
            self.assertEqual(self.request('POST', f"/cases/{large['case_id']}/approve", json={'reviewer': 'Reviewer'}).json()['status'], 'resolved')
            self.assertEqual(self.chat('hack', 'C002', 'someone hacked my account').status_code, 200)
            self.assertEqual(db.fetch_one("SELECT wallet_status FROM customers WHERE id='C002'")['wallet_status'], 'frozen')
        self.assertTrue(any(row['policy_ref'] for row in self.request('GET', '/audit').json()))
        self.assertEqual(self.chat(token='bad').status_code, 401)
        self.assertEqual(self.chat(customer='C002').status_code, 403)
        self.assertEqual(self.request('GET', '/metrics').json()['auto_resolution_rate'], 2 / 3)
        self.assertEqual(len(self.request('GET', '/tools').json()['tools']), 9)
        self.assertEqual(len(gateway.tool_definitions()), 9)
        self.assertEqual(self.request('GET', '/cases/missing').status_code, 404)

    def test_stub_and_agent_failure(self):
        from unittest.mock import patch
        with patch.dict(sys.modules, {'engine': None, 'engine.agent': None}):
            first = self.chat(message='phone 9876543210').json()
            self.assertEqual(first['reply'], '(stub) received')
            self.assertEqual(self.chat().json()['case_id'], first['case_id'])
        agent = types.ModuleType('engine.agent')
        def fail(*args):
            raise RuntimeError('private detail')
        agent.run_agent = fail
        with patch.dict(sys.modules, {'engine.agent': agent}):
            self.assertEqual(self.chat().json()['status'], 'escalated')
        self.assertNotIn('9876543210', json.dumps(self.request('GET', '/cases/' + first['case_id']).json()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
