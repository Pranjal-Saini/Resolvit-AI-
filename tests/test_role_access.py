"""Role boundaries must hold for direct URLs, API requests and shared-browser sessions."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import db, gateway, reviewer_auth, seed
from backend.app.main import app, append_message
from shared.contracts import CallContext, ToolCall


class RoleAccessTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(db, 'DB_PATH', Path(directory)/'roles.db'))
        self.enterContext(patch.dict('os.environ', {
            'AGENT_USERNAME':'support-test', 'AGENT_PASSWORD':'support-test-password',
            'REVIEWER_USERNAME':'approver-test', 'REVIEWER_PASSWORD':'approver-test-password'}))
        self.enterContext(patch.object(reviewer_auth, '_sessions', {}))
        self.enterContext(patch.object(reviewer_auth, '_attempts', {}))
        seed.seed()
        self.client = self.enterContext(TestClient(app))
        for case_id, status, customer in [('SUPPORT','escalated','C002'), ('REVIEW','open','C001'), ('AI','open','C003')]:
            db.execute('INSERT INTO sessions(id,customer_id) VALUES(?,?)', (case_id, customer))
            db.execute('INSERT INTO cases(id,session_id,customer_id,status,summary,created_at) VALUES(?,?,?,?,?,?)',
                       (case_id, case_id, customer, status, case_id+' private summary', gateway.now()))
            append_message(case_id, 'user', case_id+' private message', case_id)
        self.ctx = CallContext(case_id='REVIEW', session_id='REVIEW', customer_id='C001')
        gateway.execute(ToolCall(name='trigger_reversal', args={'txn_id':'T1002','amount':5000},
                                 policy_ref='resolveai_operations.md#Auto-reversal limit'), self.ctx)
        gateway.execute(ToolCall(name='freeze_wallet_upi', args={'reason':'compromise'}),
                        CallContext(case_id='SUPPORT', session_id='SUPPORT', customer_id='C002'))

    def login(self, role):
        endpoint = '/agent/login' if role == 'agent' else '/review/login'
        name = 'support-test' if role == 'agent' else 'approver-test'
        response = self.client.post(endpoint, json={'username':name, 'password':name+'-password'})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_anonymous_data_and_dashboard_access_are_blocked(self):
        for path in ['/cases','/cases/SUPPORT','/cases/REVIEW','/audit','/audit?case_id=SUPPORT','/metrics','/customers','/tools','/review/queue']:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        for path, target in [('/agent','/login/agent'),('/review','/login/approver')]:
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertEqual(response.headers['location'], target)
        legacy = self.client.get('/ui/design-preview.html')
        self.assertNotIn('Take over chat', legacy.text)
        self.assertIn('Sign in as support', legacy.text)

    def test_other_roles_credentials_cannot_sign_in(self):
        self.assertEqual(self.client.post('/agent/login', json={'username':'approver-test','password':'approver-test-password'}).status_code,401)
        self.assertEqual(self.client.post('/review/login', json={'username':'support-test','password':'support-test-password'}).status_code,401)

    def test_support_cannot_read_or_decide_approval_work(self):
        self.login('agent')
        self.assertEqual([item['id'] for item in self.client.get('/cases').json()], ['SUPPORT'])
        self.assertEqual(self.client.get('/cases?status=awaiting_approval').json(), [])
        for path in ['/cases/REVIEW','/cases/AI','/audit?case_id=REVIEW']:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get('/review/queue').status_code, 403)
        for action in ['approve','reject','request-info']:
            self.assertEqual(self.client.post('/cases/REVIEW/'+action, json={'note':'test'}).status_code,403)
        self.assertEqual(self.client.get('/tools').status_code,403)
        self.assertEqual(self.client.get('/metrics').json()['total'],1)
        self.assertEqual([r['id'] for r in self.client.get('/customers').json()], ['C002'])
        self.assertEqual({r['case_id'] for r in self.client.get('/audit').json()}, {'SUPPORT'})
        self.assertNotIn('REVIEW private', json.dumps(self.client.get('/cases/SUPPORT').json()))

    def test_approver_cannot_read_or_reply_to_support_work(self):
        self.login('approver')
        self.assertEqual([item['id'] for item in self.client.get('/cases').json()], ['REVIEW'])
        for path in ['/cases/SUPPORT','/cases/AI','/audit?case_id=SUPPORT']:
            self.assertEqual(self.client.get(path).status_code,404)
        for action in ['message','resolve','return-review']:
            self.assertEqual(self.client.post('/cases/SUPPORT/'+action,json={'message':'hello','note':'test'}).status_code,403)
        self.assertEqual({r['case_id'] for r in self.client.get('/audit').json()}, {'REVIEW'})
        self.assertEqual(self.client.get('/metrics').json()['total'],1)

    def test_two_tabs_can_keep_independent_role_sessions(self):
        agent = self.login('agent')
        reviewer = self.login('approver')
        self.assertIn('resolveai_agent=',agent.headers['set-cookie'])
        self.assertIn('resolveai_reviewer=',reviewer.headers['set-cookie'])
        self.assertEqual(self.client.get('/cases').status_code,400)
        for role, visible in [('agent','SUPPORT'),('approver','REVIEW')]:
            self.assertEqual([r['id'] for r in self.client.get('/cases',headers={'X-Workspace-Role':role}).json()], [visible])
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={},headers={'X-Workspace-Role':'agent'}).status_code,403)
        self.client.post('/agent/logout')
        self.assertEqual(self.client.get('/review/session').status_code,200)
        self.assertEqual(self.client.get('/agent/session').status_code,403)

    def test_identity_is_taken_from_session_and_support_can_resolve(self):
        self.login('agent')
        result=self.client.post('/cases/SUPPORT/message',json={'reviewer':'Impersonator','message':'I can help you.'})
        self.assertEqual(result.status_code,200)
        detail=self.client.get('/cases/SUPPORT').json()
        self.assertIn('[Support · support-test]',detail['messages'][-1]['content'])
        self.assertNotIn('Impersonator',json.dumps(detail))
        self.assertEqual(self.client.post('/cases/REVIEW/message',json={'message':'wrong queue'}).status_code,404)
        self.assertEqual(self.client.post('/cases/SUPPORT/resolve',json={'note':'Investigation complete.'}).status_code,200)
        self.assertEqual(self.client.post('/cases/SUPPORT/message',json={'message':'late reply'}).status_code,409)
        self.assertEqual(self.client.get('/cases/SUPPORT').json()['resolution_type'],'human_support')

    def test_information_handoff_moves_case_between_private_queues(self):
        self.login('approver')
        self.assertEqual(self.client.post('/cases/REVIEW/request-info',json={'note':'Please collect the receipt.'}).status_code,200)
        self.assertEqual(self.client.get('/cases/REVIEW').status_code,404)
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={}).status_code,404)
        self.client.post('/review/logout')
        self.login('agent')
        detail=self.client.get('/cases/REVIEW').json()
        self.assertIsNone(detail['pending_approval'])
        self.assertTrue(detail['review_requested'])
        self.assertEqual(self.client.post('/cases/REVIEW/resolve',json={'note':'Skip the approval'}).status_code,409)
        self.assertEqual(self.client.post('/cases/REVIEW/message',json={'message':'Please send your receipt.'}).status_code,200)
        self.assertEqual(self.client.post('/cases/REVIEW/return-review',json={'note':'Receipt collected.'}).status_code,200)
        self.assertEqual(self.client.get('/cases/REVIEW').status_code,404)
        self.client.post('/agent/logout'); self.login('approver')
        self.assertEqual(self.client.get('/cases/REVIEW').status_code,200)
        result=self.client.post('/cases/REVIEW/approve',json={})
        self.assertEqual(result.json()['result']['status'],'ok')
        self.assertEqual(self.client.post('/cases/REVIEW/approve',json={}).status_code,409)
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'],6200)

    def test_case_messages_do_not_leak_other_cases_in_same_session(self):
        db.execute("INSERT INTO cases(id,session_id,customer_id,status,created_at) VALUES('SECOND','SUPPORT','C002','awaiting_approval',?)",(gateway.now(),))
        db.execute("INSERT INTO approvals(case_id,tool,args_json,status,created_at) VALUES('SECOND','update_contact','{}','pending',?)",(gateway.now(),))
        append_message('SUPPORT','assistant','Approval-only message','SECOND')
        self.login('agent')
        self.assertNotIn('Approval-only message',json.dumps(self.client.get('/cases/SUPPORT').json()))
        self.client.post('/agent/logout');self.login('approver')
        self.assertNotIn('SUPPORT private message',json.dumps(self.client.get('/cases/SECOND').json()))

    def test_expired_support_session_is_denied(self):
        self.login('agent')
        token=self.client.cookies.get(reviewer_auth.COOKIES['agent'])
        reviewer_auth._sessions[token]=('support-test',time.monotonic()-1,'agent')
        self.assertEqual(self.client.get('/cases').status_code,401)

    def test_workspace_markup_has_no_other_role_navigation(self):
        for role,path in [('agent','/agent'),('approver','/review')]:
            self.login(role)
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn(f'data-role="{role}"',response.text)
            self.assertNotIn('review-tab',response.text)
            self.assertNotIn('agent-tab',response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')

    def test_seed_reset_handles_case_scoped_messages(self):
        seed.seed()
        self.assertEqual(db.fetch_all('SELECT * FROM case_messages'),[])


if __name__ == '__main__':
    unittest.main()
