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
    if "needs_approval" in statuses:
        return "awaiting_approval"
    if "escalate_to_human" in ok or any(
            a.status == "error" or (a.status == "blocked" and a.tool in MONEY_TOOLS) for a in actions):
        return "escalated"
    if ok & (MONEY_TOOLS | PROTECTIVE_TOOLS):
        return "resolved"
    return "need_info" if "?" in reply else "open"


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
    tools = gateway.tool_definitions() + [LOOKUP_POLICY_TOOL]
    messages = [{"role": "system", "content": SYSTEM}, *history[-6:], {"role": "user", "content": message}]
    actions, citations, seen, refs = [], {}, {}, []
    bad_json, reply = 0, ""

    try:
        for step in range(MAX_STEPS + 1):
            # Last round has no tools, forcing a text reply after MAX_STEPS tool rounds.
            msg = llm.chat(messages, tools if step < MAX_STEPS else None)
            if not msg.tool_calls:
                reply = _clean(msg.content)
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
                elif name in MONEY_TOOLS and not any(not c.low_confidence for c in citations.values()):
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
                    if ref:
                        refs.append(ref)
                    actions.append(ActionTaken(tool=name, status=res.status, summary=_summary(name, args, res)))
                    content = res.model_dump_json()
                seen[key] = content
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            if bad_json > 1:
                break
    except llm.LLMUnavailable:
        return AgentResponse(reply="I'm connecting you to a specialist.", status="escalated", actions=actions,
                             citations=sorted(citations.values(), key=lambda c: -c.score),
                             case_summary="LLM unavailable")

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
