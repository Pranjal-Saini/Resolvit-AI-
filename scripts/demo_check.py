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
from unittest.mock import patch
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
        from unittest.mock import patch
        with patch.dict(sys.modules, {'engine': None, 'engine.agent': None}):
            response = self.chat()
        self.assertEqual(response.status_code, 200)
        return CallContext(case_id=response.json()['case_id'], session_id='s1', customer_id='C001')

    def test_gateway_safety(self):
        ctx = self.context()
        def reverse(txn, amount, policy='policy section 1'):
            return gateway.execute(ToolCall(name='trigger_reversal', args={'txn_id': txn, 'amount': amount}, policy_ref=policy), ctx)
        self.assertEqual(reverse('T1001', 499, None).status, 'blocked')
        self.assertEqual(reverse('T1003', 250).status, 'blocked')
        self.assertEqual(reverse('T2001', 1000).status, 'blocked')
        for amount in (0, -1, 498, 500):
            self.assertEqual(reverse('T1001', amount).status, 'blocked')
        for amount in (True, '499', float('nan'), float('inf')):
            self.assertEqual(reverse('T1001', amount).status, 'error')
        self.assertEqual(gateway.execute(ToolCall(name='drop_tables'), ctx).status, 'blocked')
        self.assertEqual(gateway.execute(ToolCall(name='trigger_reversal'), ctx).status, 'error')
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
        result = gateway.execute(ToolCall(name='list_recent_transactions'), ctx)
        self.assertNotIn('9876543210', json.dumps(result.data))
        call = ToolCall(name='update_contact', args={'new_phone': '<PHONE_1>'})
        self.assertEqual(gateway.execute(call, ctx).status, 'needs_approval')
        response = self.request('POST', f'/cases/{ctx.case_id}/reject', json={'reviewer': 'Reviewer', 'note': 'Please verify identity'})
        self.assertEqual(response.json()['status'], 'rejected')
        self.assertEqual(self.request('POST', f'/cases/{ctx.case_id}/approve', json={'reviewer': 'Reviewer'}).status_code, 409)
        with patch.dict(sys.modules, {'engine': None, 'engine.agent': None}):
            other = self.chat(session='s2').json()['case_id']
        ctx = CallContext(case_id=other, session_id='s2', customer_id='C001', step_up_passed=True)
        self.assertEqual(gateway.execute(ToolCall(name='update_contact', args={'new_phone': '9988776655'}), ctx).status, 'ok')
        self.assertNotIn('9988776655', json.dumps(self.request('GET', '/audit').json()))

    def test_http_fixture_scenarios(self):
        def fixture(message, history, ctx, gateway):
            if 'hacked' in message:
                call = ToolCall(name='freeze_wallet_upi', args={'reason': 'compromise'})
            else:
                large = '5000' in message
                call = ToolCall(name='trigger_reversal', args={'txn_id': 'T1002' if large else 'T1001', 'amount': 5000 if large else 499}, policy_ref='demo policy section 1')
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
        self.assertEqual(len(self.request('GET', '/tools').json()['tools']), 7)
        self.assertEqual(len(gateway.tool_definitions()), 7)
        self.assertEqual(self.request('GET', '/cases/missing').status_code, 404)

    def test_engine_gateway_contract(self):
        definitions = {item['function']['name']: item['function']['parameters'] for item in gateway.tool_definitions()}
        self.assertEqual(set(definitions), {'list_recent_transactions', 'get_txn_status', 'trigger_reversal', 'freeze_wallet_upi', 'update_contact', 'schedule_followup', 'escalate_to_human'})
        for name in ('trigger_reversal', 'update_contact'):
            self.assertEqual(definitions[name]['properties']['policy_ref']['type'], 'string')
            self.assertNotIn('policy_ref', definitions[name]['required'])
        ctx = self.context()
        listed = gateway.execute(ToolCall(name='list_recent_transactions'), ctx)
        self.assertTrue(all(row['txn_id'] == row['id'] for row in listed.data['transactions']))
        checked = gateway.execute(ToolCall(name='get_txn_status', args={'txn_id': 'T1001'}), ctx)
        self.assertEqual(checked.data['txn_id'], 'T1001')
        for name, args in [('get_txn_status', {'txn_id': 'T2001'}), ('schedule_followup', {'txn_id': 'T2001', 'minutes': 5})]:
            self.assertEqual(gateway.execute(ToolCall(name=name, args=args), ctx).status, 'blocked')
        call = ToolCall(name='trigger_reversal', args={'txn_id': 'T1001', 'amount': 499}, policy_ref='resolveai_operations.md#Auto-reversal limit')
        result = gateway.execute(call, ctx)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.data, {'txn_id': 'T1001', 'status': 'reversed', 'amount': 499, 'refund_ref': 'RFND-T1001', 'credited_to': 'wallet', 'refund_status': 'completed'})
        checked = gateway.execute(ToolCall(name='get_txn_status', args={'txn_id': 'T1001'}), ctx)
        self.assertEqual(checked.data['status'], 'reversed')
        self.assertEqual(checked.data['credited_to'], 'wallet')
        self.assertEqual(checked.data['refund_status'], 'completed')
        listed = gateway.execute(ToolCall(name='list_recent_transactions'), ctx)
        reversed_row = next(row for row in listed.data['transactions'] if row['txn_id'] == 'T1001')
        self.assertEqual(reversed_row['credited_to'], 'wallet')
        ctx.approved_by = 'Reviewer'
        self.assertEqual(gateway.execute(ToolCall(name='trigger_reversal', args={'txn_id': 'T1002', 'amount': 5000}), ctx).status, 'blocked')
        self.assertEqual(gateway.execute(ToolCall(name='update_contact', args={'new_phone': '9988776655'}), ctx).status, 'needs_approval')
        from unittest.mock import patch
        agent = types.ModuleType('engine.agent')
        def fixture(message, history, ctx, gateway):
            gateway.execute(ToolCall(name='escalate_to_human', args={'reason': 'review'}), ctx)
            return AgentResponse(reply='Need more details', status='need_info')
        agent.run_agent = fixture
        with patch.dict(sys.modules, {'engine.agent': agent}):
            response = self.chat(session='status-check').json()
        self.assertEqual(response['status'], 'need_info')
        self.assertEqual(db.fetch_one('SELECT status FROM cases WHERE id=?', (response['case_id'],))['status'], 'need_info')

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
