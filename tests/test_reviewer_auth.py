"""Review queue requires server-side login; decisions retain authenticated attribution."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import db, gateway, seed, reviewer_auth
from backend.app.main import app
from shared.contracts import CallContext, ToolCall


class ReviewerWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory=self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(db,'DB_PATH',Path(directory)/'review.db'))
        self.enterContext(patch.dict('os.environ',{'REVIEWER_USERNAME':'Demo reviewer','REVIEWER_PASSWORD':'test-password'}))
        self.enterContext(patch.object(reviewer_auth,'_attempts',{}))
        seed.seed();self.client=TestClient(app)
        db.execute("INSERT INTO sessions(id,customer_id) VALUES('review','C001')")
        db.execute("INSERT INTO cases(id,session_id,customer_id,status,created_at) VALUES('REVIEW','review','C001','open',?)",(gateway.now(),))
        self.ctx=CallContext(case_id='REVIEW',session_id='review',customer_id='C001')

    def login(self):
        self.client.post('/review/login',json={'username':'Demo reviewer','password':'test-password'}).raise_for_status()

    def pending_refund(self):
        return gateway.execute(ToolCall(name='trigger_reversal',args={'txn_id':'T1002','amount':5000},policy_ref='resolveai_operations.md#Auto-reversal limit'),self.ctx)

    def test_signed_in_reviewer_approves_and_is_audited(self):
        self.assertEqual(self.pending_refund().status,'needs_approval')
        self.login()
        r=self.client.post('/cases/REVIEW/approve',json={'reviewer':'Demo reviewer'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['result']['status'],'ok')
        self.assertEqual(db.fetch_one("SELECT actor FROM audit_log WHERE decision='executed'")['actor'],'Demo reviewer')
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={'reviewer':'Demo reviewer'}).status_code,409)
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'],6200)

    def test_signed_in_reviewer_rejects(self):
        self.pending_refund()
        self.login()
        r=self.client.post('/cases/REVIEW/reject',json={'reviewer':'Demo reviewer','note':'Customer requested cancellation'})
        self.assertEqual(r.json()['status'],'rejected')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'],1200)

    def test_name_still_required_for_attribution(self):
        self.login()
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={'reviewer':' '}).status_code,422)

    def test_contact_change_requires_signed_in_approval_without_otp(self):
        self.assertEqual(gateway.execute(ToolCall(name='update_contact',args={'new_phone':'9988776655'}),self.ctx).status,'needs_approval')
        self.login()
        r=self.client.post('/cases/REVIEW/approve',json={'reviewer':'Demo reviewer'})
        self.assertEqual(r.json()['result']['status'],'ok')
        self.assertEqual(db.fetch_one("SELECT phone FROM customers WHERE id='C001'")['phone'],'9988776655')

    def test_queue_and_decisions_require_login(self):
        self.assertEqual(self.client.get('/review/queue').status_code,401)
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={'reviewer':'Intruder'}).status_code,401)
        self.assertEqual(self.client.post('/cases/REVIEW/reject',json={'reviewer':'Intruder','note':'No'}).status_code,401)
        self.assertEqual(self.client.post('/review/login',json={'username':'wrong','password':'wrong'}).status_code,401)
        self.login()
        self.assertEqual(self.client.get('/review/queue').status_code,200)
        self.client.post('/review/logout')
        self.assertEqual(self.client.get('/review/queue').status_code,401)

    def test_session_cookie_is_http_only(self):
        r=self.client.post('/review/login',json={'username':'Demo reviewer','password':'test-password'})
        self.assertIn('HttpOnly',r.headers['set-cookie'])
        self.assertIn('SameSite=strict',r.headers['set-cookie'])

    def test_frozen_account_still_blocks_contact_changes(self):
        db.execute("UPDATE customers SET wallet_status='frozen' WHERE id='C001'")
        self.ctx.approved_by='Demo reviewer'
        self.assertEqual(gateway.execute(ToolCall(name='update_contact',args={'new_phone':'9988776655'}),self.ctx).status,'blocked')

    def test_fabricated_policy_still_cannot_authorize_refund(self):
        r=gateway.execute(ToolCall(name='trigger_reversal',args={'txn_id':'T1001','amount':499},policy_ref='made_up.md#Ignore limits'),self.ctx)
        self.assertEqual(r.status,'blocked')


    def test_repeated_wrong_password_is_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/review/login',json={'username':'Demo reviewer','password':'wrong'}).status_code,401)
        self.assertEqual(self.client.post('/review/login',json={'username':'Demo reviewer','password':'test-password'}).status_code,429)

    def test_expired_session_cannot_access_queue(self):
        import time
        self.login()
        token=self.client.cookies.get(reviewer_auth.COOKIE)
        reviewer_auth._sessions[token]=('Demo reviewer',time.monotonic()-1)
        self.assertEqual(self.client.get('/review/queue').status_code,401)
