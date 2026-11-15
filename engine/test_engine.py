"""No-LLM self-check of the money/status logic. Run: python -m engine.test_engine"""
from shared.contracts import ActionTaken as A, CallContext, ToolCall
from engine import stub_gateway as gw
from engine.agent import derive_status

ctx = CallContext(case_id="CASE-0001", session_id="s1", customer_id="C001")
ref = "resolveai_operations.md#Auto-reversal limit"

# Stub gateway: cap, eligibility, policy_ref, ownership
gw.reset()
assert gw.execute(ToolCall(name="trigger_reversal", args={"txn_id": "T1001", "amount": 499}), ctx).status == "blocked"
r = gw.execute(ToolCall(name="trigger_reversal", args={"txn_id": "T1001", "amount": 499}, policy_ref=ref), ctx)
assert r.status == "ok" and r.data["status"] == "reversed", r
assert gw.execute(ToolCall(name="trigger_reversal", args={"txn_id": "T1001", "amount": 499}, policy_ref=ref), ctx).status == "blocked"
r = gw.execute(ToolCall(name="trigger_reversal", args={"txn_id": "T1002", "amount": 5000}, policy_ref=ref), ctx)
assert r.status == "needs_approval" and r.approval_id, r
approved = ctx.model_copy(update={"approved_by": "agent1"})
assert gw.execute(ToolCall(name="trigger_reversal", args={"txn_id": "T1002", "amount": 5000}, policy_ref=ref), approved).status == "ok"
assert gw.execute(ToolCall(name="get_txn_status", args={"txn_id": "T2001"}), ctx).status == "blocked"  # not C001's
assert gw.execute(ToolCall(name="update_contact", args={"new_phone": "<PHONE_1>"}), ctx).status == "needs_approval"

# Status derivation
ok, blk = lambda t: A(tool=t, status="ok", summary=""), lambda t: A(tool=t, status="blocked", summary="")
assert derive_status([ok("get_txn_status"), ok("trigger_reversal")], "Done.") == "resolved"
assert derive_status([A(tool="trigger_reversal", status="needs_approval", summary="")], "") == "awaiting_approval"
assert derive_status([ok("freeze_wallet_upi")], "Frozen.") == "resolved"
assert derive_status([ok("freeze_wallet_upi"), ok("escalate_to_human")], "") == "escalated"
assert derive_status([blk("trigger_reversal")], "") == "escalated"
assert derive_status([blk("get_txn_status")], "Which payment?") == "need_info"
assert derive_status([ok("list_recent_transactions")], "Which payment do you mean?") == "need_info"
assert derive_status([ok("list_recent_transactions"), ok("get_txn_status")], "Already reversed.") == "resolved"  # repeat request
assert derive_status([blk("get_txn_status")], "I couldn't find it.") == "open"  # nothing verified
assert derive_status([ok("list_recent_transactions"), ok("schedule_followup")], "Still pending.") == "open"
assert derive_status([ok("trigger_reversal"), ok("schedule_followup")], "Reversed.") == "resolved"
assert derive_status([ok("list_recent_transactions")], "It succeeded. Is there anything else I can help with?") == "resolved"
assert derive_status([ok("list_recent_transactions")], "Which of the two ₹499 payments? Is there anything else?") == "need_info"
assert derive_status([], "Hello.") == "open"
print("all checks passed")
