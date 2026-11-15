"""Agent loop. CLI: python -m engine.agent "<message>" [customer_id]  (runs against stub_gateway)"""
import json
import re
import sys

from shared.contracts import ActionTaken, AgentResponse, CallContext, ToolCall, ToolResult
from engine import llm
from engine.policy import get_policy
from engine.prompts import CASE_SUMMARY, LOOKUP_POLICY_TOOL, SYSTEM

MAX_STEPS = 5
# Diagram registry names. Status is derived from these in code, never by the LLM.
MONEY_TOOLS = {"trigger_reversal", "issue_refund", "retry_recharge", "credit_cashback", "cancel_booking_refund"}
PROTECTIVE_TOOLS = {"lock_account", "freeze_wallet_upi", "open_fraud_case"}
FALLBACK_REPLY = "I've passed your case to a specialist who will follow up shortly."


def derive_status(actions: list[ActionTaken], reply: str) -> str:
    statuses = {a.status for a in actions}
    ok = {a.tool for a in actions if a.status == "ok"}
    if "escalate_to_human" in ok or any(
            a.status == "error" or (a.status == "blocked" and a.tool in MONEY_TOOLS) for a in actions):
        return "escalated"
    if "needs_approval" in statuses:
        return "awaiting_approval"
    if ok & (MONEY_TOOLS | PROTECTIVE_TOOLS):
        return "resolved"
    # A real question needs an answer; a polite "anything else I can help with?" does not.
    if any(s.endswith("?") and "anything else" not in s.lower() for s in re.split(r"(?<=[.?!])\s+", reply.strip())):
        return "need_info"
    if "schedule_followup" in ok:  # waiting on a recheck (e.g. pending payment): not finished yet
        return "open"
    # Answered from verified tool data (e.g. "already reversed", "payment succeeded"): nothing left to do.
    # With no tool call at all the answer is unverified, so the case stays open.
    return "resolved" if ok else "open"


def _clean(text: str | None) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()  # qwen3 reasoning blocks


def _summary(name: str, args: dict, res: ToolResult) -> str:
    detail = res.reason or json.dumps(res.data)[:120]
    return f"{name}({', '.join(f'{k}={v}' for k, v in args.items())}) -> {res.status}: {detail}"


def _case_summary(message: str, actions: list[ActionTaken], refs: list[str]) -> str:
    facts = (f"Customer said: {message}\nActions:\n" + "\n".join(f"- {a.summary}" for a in actions)
             + f"\nPolicy cited: {', '.join(refs) or 'none'}")
    try:
        return _clean(llm.chat([{"role": "system", "content": CASE_SUMMARY},
                                {"role": "user", "content": facts}]).content) or facts
    except llm.LLMUnavailable:
        return facts


def run_agent(message: str, history: list[dict], ctx: CallContext, gateway) -> AgentResponse:
    if re.search(r'partial(?:ly)? (?:refund|reversal)|refund only|not the full amount', message, re.I):
        call = ToolCall(name="escalate_to_human", args={"reason":"Partial refunds require specialist review; automatic reversal must equal the debited amount"})
        result = gateway.execute(call, ctx)
        return AgentResponse(reply="Partial refunds need specialist review. No automatic refund has been made.", status="escalated", actions=[ActionTaken(tool=call.name, status=result.status, summary=result.reason or "Partial refund sent for review")], case_summary="Customer requested a partial refund; no money moved.")
    tools = gateway.tool_definitions() + [LOOKUP_POLICY_TOOL]
    messages = [{"role": "system", "content": SYSTEM}, *history[-6:], {"role": "user", "content": message}]
    actions, citations, seen, refs = [], {}, {}, []
    bad_json, reply = 0, ""
    confirmed_refund = None
    observed_transactions = {}
    payment_reminder_sent = False
    tool_format_reminder_sent = False
    reported_amounts = {float(value.replace(',', '')) for value in re.findall(r'\b\d[\d,]*(?:\.\d+)?\b', message)}

    try:
        for step in range(MAX_STEPS + 1):
            # Last round has no tools, forcing a text reply after MAX_STEPS tool rounds.
            if step == MAX_STEPS:
                messages.append({"role": "system", "content": "No more tools. Write the final reply to the customer now."})
            msg = llm.chat(messages, tools if step < MAX_STEPS else None)
            if not msg.tool_calls:
                reply = _clean(msg.content)
                if "<tool_call>" in reply:  # model wrote a tool call as text: never show that to the customer
                    reply = ""
                if re.search(r'"name"\s*:\s*"(?:lookup_policy|trigger_reversal|list_recent_transactions)"', reply):
                    if not tool_format_reminder_sent and step < MAX_STEPS:
                        tool_format_reminder_sent = True
                        messages.append({"role":"assistant", "content":reply})
                        messages.append({"role":"system", "content":"Use structured tool calls, not JSON in the reply. Invoke the required tool now; do not claim a result until it succeeds."})
                        continue
                    reply = ""
                failed_matches = [txn for txn in observed_transactions.values()
                                  if txn.get("status") == "failed_debited" and txn.get("amount") in reported_amounts]
                if len(failed_matches) == 1 and not any(a.tool in MONEY_TOOLS for a in actions):
                    txn = failed_matches[0]
                    if not payment_reminder_sent and step < MAX_STEPS:
                        payment_reminder_sent = True
                        messages.append({"role": "assistant", "content": reply})
                        messages.append({"role": "system", "content": (
                            f"The reported payment {txn['txn_id']} for ₹{txn['amount']} is still failed_debited. "
                            "Do not report it resolved or promise an automatic refund. Call lookup_policy, then "
                            "submit trigger_reversal with the exact amount and policy_ref. The gateway decides approval.")})
                        continue
                    call = ToolCall(name="escalate_to_human", args={"reason": "Failed payment was identified but no reversal request was submitted"})
                    result = gateway.execute(call, ctx)
                    actions.append(ActionTaken(tool=call.name, status=result.status, summary=_summary(call.name, call.args, result)))
                    reply = FALLBACK_REPLY if result.status == "ok" else "I could not complete the payment request. Please contact support."
                break
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    bad_json += 1
                    content = json.dumps({"status": "error", "reason": "arguments were not valid JSON, resend"})
                    if bad_json > 1:
                        actions.append(ActionTaken(tool=name, status="error", summary="malformed tool arguments twice"))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
                    continue

                if name == "list_recent_transactions" and "limit" in args:
                    if args["limit"] is None:
                        args.pop("limit")
                    elif isinstance(args["limit"], str) and args["limit"].isdigit():
                        args["limit"] = int(args["limit"])
                ref = args.pop("policy_ref", None)
                key = (name, json.dumps(args, sort_keys=True), ref)
                if key in seen:
                    content = seen[key]  # duplicate call: reuse the result, never execute twice
                elif name == "lookup_policy":
                    results = get_policy(args.get("query") or message)
                    for r in results:
                        citations[(r.source, r.section)] = r
                    content = json.dumps([{"policy_ref": f"{r.source}#{r.section}", "rule": r.rule_text,
                                           "score": r.score, "low_confidence": r.low_confidence} for r in results])
                elif name in MONEY_TOOLS and not any(not c.low_confidence and f"{c.source}#{c.section}" == ref for c in citations.values()):
                    # Fail closed: no money moves without a confident policy match.
                    reason = "money actions need a confident policy match; call lookup_policy first"
                    if citations:  # looked up, but nothing confident -> this is a block, escalate
                        reason = "no confident policy match; escalate_to_human"
                        actions.append(ActionTaken(tool=name, status="blocked", summary=f"{name}: {reason}"))
                    content = json.dumps({"status": "blocked", "reason": reason})
                else:
                    try:
                        res = gateway.execute(ToolCall(name=name, args=args, policy_ref=ref), ctx)
                    except Exception as e:
                        res = ToolResult(status="error", reason=f"gateway error: {e}")
                    if res.status == "ok" and name in ("list_recent_transactions", "get_txn_status"):
                        rows = res.data.get("transactions", []) if name == "list_recent_transactions" else [res.data]
                        for row in rows:
                            txn_id = row.get("txn_id") or row.get("id")
                            if txn_id:
                                observed_transactions[txn_id] = {**row, "txn_id": txn_id}
                    if name == "list_recent_transactions" and res.status == "ok" and re.search(r'failed|deducted|debited|refund|revers', message, re.I):
                        failed = [row for row in observed_transactions.values() if row.get("status") == "failed_debited"]
                        words = set(re.findall(r'\w+', message.casefold()))
                        matches = [row for row in failed if row.get("amount") in reported_amounts or
                                   any(word in words for word in re.findall(r'\w+', row.get("payee", "").casefold()) if len(word) > 3)]
                        if len(failed) > 1 and len(matches) != 1:
                            actions.append(ActionTaken(tool=name, status=res.status, summary="Multiple failed payments found; customer must identify one"))
                            return AgentResponse(reply="I found more than one failed payment. What amount or payee is this about?", status="need_info", actions=actions)
                    if name == "trigger_reversal" and res.status == "ok" and res.data.get("status") == "reversed":
                        confirmed_refund = res.data
                    if ref:
                        refs.append(ref)
                    actions.append(ActionTaken(tool=name, status=res.status, summary=_summary(name, args, res)))
                    content = res.model_dump_json()
                seen[key] = content
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            if bad_json > 1:
                break
    except llm.LLMUnavailable:
        # A provider outage cannot undo an action already committed by the gateway.
        if confirmed_refund and derive_status(actions, "") == "resolved":
            destination = " and credited to your wallet" if confirmed_refund.get("credited_to") == "wallet" else ""
            reply = (f"Your payment of ₹{confirmed_refund['amount']:g} has been reversed{destination}. "
                     f"Refund reference: {confirmed_refund['refund_ref']}.")
            if refs:
                reply += f" Policy: {refs[-1]}."
            return AgentResponse(reply=reply, status="resolved", actions=actions,
                                 citations=sorted(citations.values(), key=lambda c: -c.score))
        pending = any(action.status == "needs_approval" for action in actions)
        return AgentResponse(
            reply="Your request is awaiting human approval. No refund has been processed." if pending else "I'm connecting you to a specialist.",
            status="awaiting_approval" if pending else "escalated", actions=actions,
            citations=sorted(citations.values(), key=lambda c: -c.score),
            case_summary="LLM unavailable; review the recorded tool outcomes before taking further action.")

    # A protective action always gets a human follow-up, whether or not the LLM remembered to escalate.
    ok = {a.tool for a in actions if a.status == "ok"}
    if ok & PROTECTIVE_TOOLS and "escalate_to_human" not in ok:
        args = {"reason": "protective action taken; fraud follow-up required"}
        try:
            res = gateway.execute(ToolCall(name="escalate_to_human", args=args), ctx)
        except Exception as e:
            res = ToolResult(status="error", reason=f"gateway error: {e}")
        actions.append(ActionTaken(tool="escalate_to_human", status=res.status,
                                   summary=_summary("escalate_to_human", args, res)))

    status = derive_status(actions, reply)
    return AgentResponse(
        reply=reply or FALLBACK_REPLY, status=status, actions=actions,
        citations=sorted(citations.values(), key=lambda c: -c.score),
        case_summary=_case_summary(message, actions, refs) if status in ("awaiting_approval", "escalated") else None)


if __name__ == "__main__":
    from engine import stub_gateway

    sys.stdout.reconfigure(encoding="utf-8")
    ctx = CallContext(case_id="CASE-TEST", session_id="s1", customer_id=sys.argv[2] if len(sys.argv) > 2 else "C001")
    print(run_agent(sys.argv[1], [], ctx, stub_gateway).model_dump_json(indent=2))
