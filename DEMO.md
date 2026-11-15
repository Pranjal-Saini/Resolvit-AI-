# Live demo: one question, the full journey

Open http://127.0.0.1:8010 → Customer support → **Prepare live demo**. This selects **C001 Rahul Sharma** and starts a fresh conversation. It does not send automatically.

## Customer question

> ₹5,000 was deducted for my flight booking, but the payment failed. Can you check what happened and help me get my money back?

## Present in three minutes

1. **Send.** Say: “The customer describes a problem naturally; no transaction ID is needed.”
2. **Expand Actions & policy citations.** Show the transaction lookup, T1002, the policy and `trigger_reversal` returning `needs_approval`. Say: “The AI identifies the request, but the gateway enforces the ₹2,000 auto-reversal limit.”
3. **Open the case.** Show `awaiting_approval`, the ₹5,000 amount and policy reference. No money has moved yet.
4. **Approve as reviewer.** Sign in with the dummy account in `REVIEW_LOGIN.md`, then click Approve action. The server records the signed-in reviewer. No OTP is required. Show `resolved` and refund reference `RFND-T1002`.
5. **Show the customer confirmation and audit trail.** Point out the human approval and executed reversal. Say: “Every action is recorded, and repeated approval cannot refund twice.”

## Optional contrasts

- Automatic: C001 — “₹499 got debited for my electricity bill but it failed.”
- Protection: C002 — “Someone hacked my account. Please freeze my wallet immediately.”
- Ambiguity: C001 on fresh data — “My payment failed.” The assistant should ask which payment.

## Before presenting

Use fresh dedicated demo data. A new conversation does not reset transactions; an already-reversed T1002 will not produce a new approval request. Check Groq quota; the small local fallback escalates payment flows rather than reliably completing them. Signed-in reviewers are recorded for audit attribution. Never project `.env`. No real Paytm money moves.

## Regular local launch

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Only reseed if you intend to clear that database’s demo activity.
