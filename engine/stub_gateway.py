"""Stub of backend/app/gateway.py: same interface, in-memory demo data, same tier rules.

Tool names follow the architecture diagram. Only the tools the demo needs are stubbed; the real
gateway can expose the full registry and the agent picks them up from tool_definitions().
list_recent_transactions is not in the diagram but the agent needs it to find the txn.
"""
import copy
import itertools

from shared.contracts import CallContext, ToolCall, ToolResult

CAP_INR = 2000

# name: (tier, description, {arg: (type, required)})
TOOLS = {
    "list_recent_transactions": ("read_only", "List the customer's recent transactions with status.",
                                 {"limit": ("integer", False)}),
    "get_txn_status": ("read_only", "Get the current status of one transaction.", {"txn_id": ("string", True)}),
    "trigger_reversal": ("money_moving", "Reverse a failed UPI payment that was debited but not credited.",
                         {"txn_id": ("string", True), "amount": ("number", True)}),
    "freeze_wallet_upi": ("protective", "Freeze the customer's wallet and UPI immediately (compromised account).",
                          {"reason": ("string", True)}),
    "update_contact": ("sensitive", "Change the customer's registered phone number.", {"new_phone": ("string", True)}),
    "schedule_followup": ("platform", "Schedule a recheck of a transaction after some minutes.",
                          {"txn_id": ("string", True), "minutes": ("integer", True)}),
    "escalate_to_human": ("platform", "Hand the case to a human support agent.", {"reason": ("string", True)}),
}

SEED = {
    "customers": {"C001": {"name": "Rahul Sharma", "wallet_status": "active"},
                  "C002": {"name": "Priya Verma", "wallet_status": "active"}},
    "txns": {
        "T1001": {"customer_id": "C001", "amount": 499, "payee": "Electricity Board", "type": "upi",
                  "status": "failed_debited", "created_at": "1 day ago"},
        "T1002": {"customer_id": "C001", "amount": 5000, "payee": "Flight Booking", "type": "upi",
                  "status": "failed_debited", "created_at": "2 days ago"},
        "T1003": {"customer_id": "C001", "amount": 250, "payee": "Grocery", "type": "upi",
                  "status": "success", "created_at": "today"},
        "T2001": {"customer_id": "C002", "amount": 1000, "payee": "Recharge", "type": "upi",
                  "status": "success", "created_at": "3 days ago"},
    },
}
DB = copy.deepcopy(SEED)
_ids = itertools.count(1)


def reset():
    global DB
    DB = copy.deepcopy(SEED)


def tool_definitions() -> list[dict]:
    defs = []
    for name, (tier, desc, args) in TOOLS.items():
        props = {a: {"type": t} for a, (t, _) in args.items()}
        if tier in ("money_moving", "sensitive"):
            props["policy_ref"] = {"type": "string", "description": "<source>#<section> from lookup_policy"}
        defs.append({"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": [a for a, (_, req) in args.items() if req]}}})
    return defs


def execute(call: ToolCall, ctx: CallContext) -> ToolResult:
    def res(status, data=None, reason=None, approval=False):
        return ToolResult(status=status, data=data or {}, reason=reason, audit_id=next(_ids),
                          approval_id=next(_ids) if approval else None)

    if call.name not in TOOLS:
        return res("blocked", reason=f"unknown tool {call.name}")
    tier, _, spec = TOOLS[call.name]
    missing = [a for a, (_, req) in spec.items() if req and a not in call.args]
    if missing:
        return res("blocked", reason=f"missing args: {missing}")
    if not ctx.verified:
        return res("blocked", reason="customer not verified")

    a = call.args
    mine = {k: v for k, v in DB["txns"].items() if v["customer_id"] == ctx.customer_id}
    txn = mine.get(a.get("txn_id"))
    if "txn_id" in spec and txn is None:
        return res("blocked", reason=f"transaction {a.get('txn_id')} not found for this customer")

    if call.name == "list_recent_transactions":
        items = [{"txn_id": k, **{f: v[f] for f in ("amount", "payee", "status", "created_at")}}
                 for k, v in mine.items()]
        return res("ok", {"transactions": items[: int(a.get("limit") or 5)]})
    if call.name == "get_txn_status":
        return res("ok", {"txn_id": a["txn_id"], "status": txn["status"], "amount": txn["amount"]})
    if call.name == "trigger_reversal":
        if not call.policy_ref:
            return res("blocked", reason="policy_ref required for money_moving tools")
        if txn["status"] != "failed_debited":
            return res("blocked", reason=f"not eligible: status is {txn['status']}")
        if float(a["amount"]) != txn["amount"]:
            return res("blocked", reason=f"amount must equal debited amount {txn['amount']}")
        if txn["amount"] > CAP_INR and not ctx.approved_by:
            return res("needs_approval", {"txn_id": a["txn_id"], "amount": txn["amount"]},
                       reason=f"amount above auto-reversal cap of {CAP_INR}", approval=True)
        txn["status"] = "reversed"
        return res("ok", {"txn_id": a["txn_id"], "status": "reversed", "amount": txn["amount"],
                          "refund_ref": f"RFND-{a['txn_id']}", "credited_to": "paytm_wallet"})
    if call.name == "freeze_wallet_upi":
        DB["customers"][ctx.customer_id]["wallet_status"] = "frozen"
        return res("ok", {"wallet_status": "frozen"})
    if call.name == "update_contact":
        if not ctx.step_up_passed and not ctx.approved_by:
            return res("needs_approval", reason="sensitive action needs step-up verification", approval=True)
        return res("ok", {"phone_updated": True})
    if call.name == "schedule_followup":
        return res("ok", {"txn_id": a["txn_id"], "recheck_in_minutes": a["minutes"]})
    if call.name == "escalate_to_human":
        return res("ok", {"case_status": "escalated"})
    return res("error", reason="not implemented in stub")
