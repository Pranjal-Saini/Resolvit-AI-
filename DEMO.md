# Live demo with two separate staff roles

Launch the dedicated examples without resetting the working database:

```bash
RESOLVEAI_DEMO_DB=/tmp/resolveai-role-demo.db .venv/bin/python -m scripts.role_demo_server
```

A new file receives ten customers, twenty transactions and two gateway-backed illustrative cases. An existing file preserves its actions on restart. The examples are pre-created; their setup does not call an AI provider. All payment data is mocked.

## Open two tabs

1. Human support: http://127.0.0.1:8010/login/agent — `support` / `DemoSupport!2026`.
2. Approver: http://127.0.0.1:8010/login/approver — `approver` / `DemoReview!2026`.

The sessions are separate even in one browser. Each role sees only its own queue and actions. There is no switch to the other workspace inside the dashboard.

## Present in three minutes

1. In support, open **CASE-DEMO-SUPPORT**. The customer reports account compromise. Show the confirmed mock wallet freeze and escalation; reply as human support. Routine AI chats are absent from this queue.
2. In the approver tab, open **CASE-DEMO-REVIEW**. The question is: “My ₹5,000 flight payment failed after debit. Can you reverse it?” Show the requested action, amount and policy reference. No money has moved yet.
3. For the handoff demonstration, enter a receipt request and choose **Request information**. The case leaves the approver queue. Refresh support; it appears there, without any approval control.
4. Support can reply, then enter the information and choose **Return information to approver**. The case leaves support's queue and returns to the approver.
5. Approve the action. The gateway processes the mock refund once and records the authenticated approver; repeated approval is blocked. The decision appears under Completed work.

The ₹2,000 cap is the project's internal demo rule, not a claim about Paytm policy. No OTP is required for the mock approved contact-change flow.

## Let judges explore

Choose **Demo cases · 20** in either dashboard. The catalogue covers the requested UPI/transfers, recharge/bills, wallet/voucher and account-protection scenarios. Each has a query, expected behavior and integration scope. Run **20 UI checks**; both roles have access to the catalogue, but only their own routes have interactive simulated actions. Other routes remain read-only. The fixtures make no live agent, gateway or Paytm calls.

Return to the live queue when finished. Approving or resolving a live example changes the dedicated demo database; restarting the server does not undo it. Use a new dedicated filename for a fresh live presentation. Never reseed the working database merely to reset a presentation.

The customer team's software continues to call `/chat` with the existing demo-token contract. For prior live Groq rule-engine results, see `FINAL_JOINT_CHECK.md`; for the latest role checks, see `ROLE_ACCESS_CHECK.md`. The smaller local Ollama fallback is not a reliable substitute for the configured Groq payment flows. Never project `.env`.
