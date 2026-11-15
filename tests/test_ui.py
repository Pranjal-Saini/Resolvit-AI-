"""The dashboard assets must be available from the same app as its API."""
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app


class UIServingTests(unittest.TestCase):
    def test_workspace_and_assets_are_served(self):
        client = TestClient(app)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('ResolveAI', response.text)
        self.assertIn('Sign in as support', response.text)
        self.assertEqual(client.get('/ui/login.js').status_code, 200)
        self.assertEqual(client.get('/ui/access.css').status_code, 200)
        self.assertEqual(client.get('/ui/role-workspace.js').status_code, 401)
        self.assertEqual(client.get('/health').json(), {'ok': True})

    def test_judges_entry_requires_role_login(self):
        client=TestClient(app)
        response=client.get('/judges')
        self.assertEqual(response.status_code,200)
        self.assertTrue(str(response.url).endswith('/?judges=1'))
        self.assertIn('Sign in as approver',response.text)
        response=client.get('/judges?role=agent')
        self.assertTrue(str(response.url).endswith('/login/agent?demo=1'))

    def test_review_entry_opens_login_gate(self):
        response=TestClient(app).get('/review')
        self.assertEqual(response.status_code,200)
        self.assertTrue(str(response.url).endswith('/login/approver'))

    def test_environment_file_is_not_exposed_as_an_asset(self):
        client = TestClient(app)
        self.assertEqual(client.get('/ui/%2e%2e/.env').status_code, 404)


class ChatHistoryTests(unittest.TestCase):
    def test_current_message_is_not_duplicated_in_agent_history(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from backend.app import db, seed
        from shared.contracts import AgentResponse
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', Path(directory)/'chat.db'):
            seed.seed()
            client = TestClient(app)
            with patch('engine.agent.run_agent', return_value=AgentResponse(reply='Which payment?', status='need_info')) as agent:
                body = {'session_id':'history-test','customer_id':'C001','token':'demo-C001','message':'First message'}
                self.assertEqual(client.post('/chat', json=body).status_code, 200)
                self.assertEqual(agent.call_args.args[1], [])
                body['message'] = 'Second message'
                self.assertEqual(client.post('/chat', json=body).status_code, 200)
                self.assertEqual(agent.call_args.args[0], 'Second message')
                self.assertEqual(agent.call_args.args[1], [
                    {'role':'user','content':'First message'},
                    {'role':'assistant','content':'Which payment?'},
                ])
