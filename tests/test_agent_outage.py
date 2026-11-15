"""Provider outages must not hide the outcome of a committed payment action."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from backend.app import db, gateway, seed
from engine.agent import run_agent
from engine.llm import LLMUnavailable
from shared.contracts import CallContext, PolicyResult


def tool_message(name, args):
    import json
    return NS(content=None, tool_calls=[NS(id=name, function=NS(name=name, arguments=json.dumps(args)))])


class AgentOutageTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(db, 'DB_PATH', Path(directory) / 'outage.db'))
        seed.seed()
        db.execute("INSERT INTO sessions(id,customer_id) VALUES('outage','C001')")
        db.execute("INSERT INTO cases(id,session_id,customer_id,status,created_at) VALUES('CASE-OUTAGE','outage','C001','open',?)", (gateway.now(),))
        self.ctx = CallContext(case_id='CASE-OUTAGE', session_id='outage', customer_id='C001')
        self.ref = 'resolveai_operations.md#Auto-reversal limit'
        self.enterContext(patch('engine.agent.get_policy', return_value=[PolicyResult(rule_text='Demo limit', source='resolveai_operations.md', section='Auto-reversal limit', score=.9, low_confidence=False)]))

    def run_then_fail(self, txn, amount):
        messages = [tool_message('lookup_policy', {'query':'failed payment'}),
                    tool_message('trigger_reversal', {'txn_id':txn, 'amount':amount, 'policy_ref':self.ref}),
                    LLMUnavailable('provider quota exhausted')]
        with patch('engine.agent.llm.chat', side_effect=messages):
            return run_agent('Payment failed', [], self.ctx, gateway)

    def test_completed_refund_is_reported_when_provider_fails(self):
        response = self.run_then_fail('T1001', 499)
        self.assertEqual(response.status, 'resolved')
        self.assertIn('wallet', response.reply)
        self.assertIn('RFND-T1001', response.reply)
        self.assertIn(self.ref, response.reply)
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 1699)
        self.assertEqual(db.fetch_one("SELECT status FROM transactions WHERE id='T1001'")['status'], 'reversed')

    def test_pending_approval_survives_provider_failure(self):
        response = self.run_then_fail('T1002', 5000)
        self.assertEqual(response.status, 'awaiting_approval')
        self.assertIn('No refund', response.reply)
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 1200)
        self.assertEqual(db.fetch_one("SELECT status FROM approvals")['status'], 'pending')

    def test_outage_before_actions_escalates_without_moving_money(self):
        with patch('engine.agent.llm.chat', side_effect=LLMUnavailable('offline')):
            response = run_agent('Payment failed', [], self.ctx, gateway)
        self.assertEqual(response.status, 'escalated')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 1200)

    def test_premature_read_only_answer_is_redirected_to_approval(self):
        messages = [tool_message('list_recent_transactions', {}),
                    NS(content='A refund will happen automatically.', tool_calls=[]),
                    tool_message('lookup_policy', {'query':'failed payment'}),
                    tool_message('trigger_reversal', {'txn_id':'T1002','amount':5000,'policy_ref':self.ref}),
                    NS(content='A specialist will review the request.', tool_calls=[]),
                    NS(content='High-value failed payment awaiting approval.', tool_calls=[])]
        with patch('engine.agent.llm.chat', side_effect=messages) as provider:
            response = run_agent('₹5000 flight booking failed but money was deducted', [], self.ctx, gateway)
        self.assertEqual(response.status, 'awaiting_approval')
        self.assertEqual(db.fetch_one("SELECT status FROM approvals")['status'], 'pending')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'], 1200)
        reminder_messages = provider.call_args_list[2].args[0]
        self.assertTrue(any('still failed_debited' in m.get('content','') for m in reminder_messages))


    def test_explicit_partial_refund_never_becomes_full_refund(self):
        with patch('engine.agent.llm.chat') as provider:
            response=run_agent('My ₹499 electricity payment failed. Refund only ₹200, not the full amount.',[],self.ctx,gateway)
        self.assertEqual(response.status,'escalated')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'],1200)
        self.assertEqual(db.fetch_one("SELECT status FROM transactions WHERE id='T1001'")['status'],'failed_debited')
        provider.assert_not_called()

    def test_optional_read_limit_from_small_model_is_canonicalized(self):
        messages=[tool_message('list_recent_transactions',{'limit':'5'}), NS(content='Which payment do you mean?',tool_calls=[])]
        with patch('engine.agent.llm.chat',side_effect=messages):
            response=run_agent('Please find my payment',[],self.ctx,gateway)
        self.assertEqual(response.status,'need_info')
        self.assertEqual(db.fetch_one("SELECT decision FROM audit_log WHERE tool='list_recent_transactions'")['decision'],'executed')

    def test_ambiguous_payment_never_moves_money(self):
        messages=[tool_message('list_recent_transactions', {})]
        with patch('engine.agent.llm.chat',side_effect=messages):
            response=run_agent('My payment failed. Please help me.',[],self.ctx,gateway)
        self.assertEqual(response.status,'need_info')
        self.assertEqual(db.fetch_one("SELECT wallet_balance FROM customers WHERE id='C001'")['wallet_balance'],1200)
        self.assertEqual(db.fetch_all("SELECT id FROM audit_log WHERE tool='trigger_reversal'"),[])
