# ResolveAI demo script

Before: backend running at `API_BASE`, UI running, `GROQ_API_KEY` set in `.env` (Ollama `qwen3:8b` is the fallback), index built (`python -m engine.build_index`). Pre-run each message once.

## 1. Auto-resolve under the cap (G1)
Customer **C001 Rahul Sharma**, new conversation:
> ₹499 got debited for my electricity bill but it failed

Expect: status **resolved**, refund ref `RFND-T1001`, credited to the Paytm wallet, citation.
Point at: actions expander (list → status → policy lookup → `trigger_reversal` ok) and the cited rule (`resolveai_operations.md#Auto-reversal limit` / `paytm_upi_failed_txn.md`). Audit table shows `policy_ref` on the money action.

## 2. Over-cap → human approval (G2)
Customer **C001**, click **New conversation**:
> ₹5000 flight booking failed but money was deducted

Expect: status **awaiting_approval**, "a specialist will review".
Point at: dashboard review queue → case summary + pending `trigger_reversal` (₹5,000, policy_ref) → **Approve** → case resolved. Say: "the LLM never decides money: the gateway's ₹2,000 cap did, backed by a cited rule".

## 3. Protective action (G3)
Customer **C002 Priya Verma**:
> someone hacked my account

Expect: wallet **frozen** + status **escalated**.
Point at: `freeze_wallet_upi` ran first, `escalate_to_human` follows automatically (enforced in code), escalated list on the dashboard.

## Talking points
- Policy docs are paraphrased from Paytm Help + the RBI TAT circular (T+1 / T+5 reversal, ₹100/day compensation); the ₹2,000 cap is our own ops rule, clearly marked.
- Status is derived from tool results in code, never by the LLM.
- No confident policy match → no money tool reaches the gateway.

## Dashboard launch

The UI is now served by FastAPI. Run:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Choose **Customer support** for the prepared scenario buttons, then **Cases & approvals** to review a pending request. Review confirmations also appear in the customer conversation. Use **Audit trail** to inspect the actual gateway decisions.

Joint-check evidence and remaining verification limits are recorded in `UI_JOINT_CHECK.md`.
