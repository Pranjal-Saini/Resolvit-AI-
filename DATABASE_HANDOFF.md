# Database integration handoff

## Verified locally

- Demo database: `backend/resolveai.db`, 10 customers and 20 transactions.
- Nine database, approval and account-protection tests pass: `.venv/bin/python -m unittest discover -s tests -p test_database.py -v`.
- Five isolated backend checks pass: `.venv/bin/python -m scripts.demo_check`.
- Backend checks cover refunds, concurrent duplicate requests, approvals, audit entries, masking and HTTP wiring using a deterministic agent fixture, not the real agent.
- Real-agent verification uses a temporary database; shared demo records are preserved.

## Agent integration

The backend imports `engine.agent.run_agent(message, history, ctx, gateway)` and expects a `shared.contracts.AgentResponse`. The real engine is now integrated. Groq testing verified the ₹499 refund and repeated complaint, including persisted case/audit data and no second wallet credit.

Use the supplied gateway module to execute tools, rather than a separate mock store:

```python
from shared.contracts import ToolCall

result = gateway.execute(
    ToolCall(
        name="trigger_reversal",
        args={"txn_id": "T1001", "amount": 499},
        policy_ref="resolveai_operations.md#Auto-reversal limit",
    ),
    ctx,
)
```

The agent must choose the tool and policy reference based on the request and retrieved policy; the snippet only shows the integration contract.

| Agent transcript name | Backend tool name |
|---|---|
| `trigger_reversal` | `trigger_reversal` |
| `get_txn_status` | `get_txn_status` |
| `list_recent_transactions` | `list_recent_transactions` |

Use the gateway's returned refund reference in the customer reply. This mock backend returns `RFND-T1001`; do not invent an RRN.

## Joint acceptance check

1. Connect the real agent through the interface above.
2. Start the backend with `.venv/bin/python -m uvicorn backend.app.main:app --port 8000`.
3. Send POST `/chat` with `session_id`, `customer_id: "C001"`, `token: "demo-C001"`, and the failed ₹499 electricity-payment message.
4. Starting from fresh demo data, verify T1001 is `reversed`, C001's balance is ₹1,699, the case is `resolved`, and the audit contains the executed reversal with its policy reference.
5. Repeat the request. The balance must remain ₹1,699; no second refund may execute.

Do not run seed during teammate testing: it clears case, conversation, approval and audit data. Do not change the schema or shared contracts just to match another mock implementation.

## Engine contract alignment

The registry exposes the seven agreed engine tools. Reversals require a policy reference even with human approval, the full debited amount, and transaction ownership. Contact updates require step-up verification. AgentResponse.status is persisted unchanged. The engine and shared configuration have been pulled. The refund response includes `credited_to: "wallet"` and `refund_status: "completed"`; status lookups and transaction lists retain these facts for repeated complaints. Read tools always return current data; mutation retries retain duplicate protection.
