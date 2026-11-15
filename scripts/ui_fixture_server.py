"""Test-only UI integration server. Never changes the shared demo database.

Run: .venv/bin/python -m scripts.ui_fixture_server
Uses a deterministic agent so UI regression checks need no API quota.
"""
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import uvicorn
from backend.app import db, seed
from backend.app.main import app
from shared.contracts import ActionTaken, AgentResponse, PolicyResult, ToolCall


def fixture_agent(message, history, ctx, gateway):
    ref = 'resolveai_operations.md#Auto-reversal limit'
    if 'phone' in message.lower() and 'hacked' not in message.lower():
        result=gateway.execute(ToolCall(name='update_contact',args={'new_phone':'9988776655'}),ctx)
        return AgentResponse(reply='Contact change needs reviewer approval.',status='awaiting_approval',actions=[ActionTaken(tool='update_contact',status=result.status,summary=result.reason)])
    if 'hacked' in message.lower():
        calls = [ToolCall(name='freeze_wallet_upi', args={'reason':'Account compromised'}),
                 ToolCall(name='escalate_to_human', args={'reason':'Fraud follow-up'})]
        reply = 'Your wallet is frozen. A specialist will follow up.'
        status = 'escalated'
    else:
        large = '5000' in message or '2500' in message
        txn_id = 'T10001' if ctx.customer_id == 'C010' else ('T1002' if large else 'T1001')
        amount = 2500 if ctx.customer_id == 'C010' else (5000 if large else 499)
        calls = [ToolCall(name='list_recent_transactions'),
                 ToolCall(name='trigger_reversal', args={'txn_id':txn_id,'amount':amount}, policy_ref=ref)]
        reply = 'Your request needs specialist approval.' if large else 'Your ₹499 payment was reversed and credited to your wallet. Reference RFND-T1001.'
        status = 'awaiting_approval' if large else 'resolved'
    actions = []
    for call in calls:
        result = gateway.execute(call, ctx)
        actions.append(ActionTaken(tool=call.name, status=result.status, summary=result.reason or str(result.data)))
    return AgentResponse(reply=reply, status=status, actions=actions,
                         citations=[PolicyResult(rule_text='Demo reversals above ₹2,000 need human approval.', source='resolveai_operations.md', section='Auto-reversal limit', score=1, low_confidence=False)],
                         case_summary='High-value payment requires human review.' if status=='awaiting_approval' else None)


if __name__ == '__main__':
    os.environ['REVIEWER_USERNAME']='ui-approver'
    os.environ['REVIEWER_PASSWORD']='ui-test-password'
    os.environ['AGENT_USERNAME']='ui-support'
    os.environ['AGENT_PASSWORD']='ui-support-password'
    with tempfile.TemporaryDirectory(prefix='resolveai-ui-fixture-') as directory:
        with patch.object(db, 'DB_PATH', Path(directory)/'ui.db'), patch('engine.agent.run_agent', fixture_agent):
            seed.seed()
            print('TEST FIXTURE ONLY: http://127.0.0.1:8011', flush=True)
            uvicorn.run(app, host='127.0.0.1', port=8011, log_level='warning')
