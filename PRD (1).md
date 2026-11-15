# ResolveAI — Product Requirements Document (Hackathon, 4 hours)

> Product requirements for ResolveAI, a 4-hour hackathon build by a 3-person team.
> Workstreams: **Backend** (API, database, mock Paytm, tool gateway) and **Agent + UI** (LLM agent loop, RAG policy engine, Streamlit UI).
> **The contracts in Section 6 are frozen.** Change them only after telling the whole team.

---

## 1. Problem
Most support chatbots stop at explaining a policy. A human still has to do the reversal, retry or account action. That keeps cost and wait time tied to ticket volume.

## 2. Solution (one line)
An AI agent that resolves Paytm-style payment issues end to end. It takes **real actions through a governed tool gateway**, grounds every decision in a **cited policy rule (RAG)**, and **escalates to a human** only when a risk tier or limit requires it.

## 3. Goals for the demo
| # | Goal | Success check |
|---|---|---|
| G1 | Auto-resolve a failed UPI payment under the cap | Customer gets a reversal receipt with a policy citation, and the audit row is written |
| G2 | Escalate an over-cap reversal | Case appears in the review queue with a summary. Approve → action executes → case resolved |
| G3 | Protective action | "My account was hacked" → wallet frozen immediately, logged |
| G4 | Visible governance | Audit viewer shows every tool call with tier, decision, policy_ref |

**Non-goals for the hackathon (mention in the pitch, don't build):** C++ hot paths, real Paytm integration, Postgres/Redis, secrets vault, monitoring, real OTP, multi-tenant YAML per client.

## 4. Users
- **Customer:** chats in the app (Streamlit chat page).
- **Support agent (human):** reviews escalations, approves or rejects, reads the audit trail (Streamlit dashboard).

## 5. Architecture

```
Streamlit UI (chat + dashboard)
        │ HTTP (API_BASE=http://localhost:8000)
        ▼
FastAPI backend ── verify token ── PII mask ── sessions/cases (SQLite)
        │
        ▼  engine.agent.run_agent(message, history, ctx, gateway)
Agent loop (Groq LLM, tool calling, max 5 steps)
   ├── lookup_policy  → engine.policy.get_policy()  (FAISS over policy docs, cited)
   └── other tools    → backend gateway.execute()
                            ├─ checks: registry, args, verified, tier, cap, eligibility, policy_ref, idempotency
                            ├─ allowed  → mock Paytm API → audit log → ok
                            └─ over cap → approval row → needs_approval → human queue
```

**Key principles**
1. The **gateway is the hard ceiling.** Policy (RAG) can narrow what the agent does, never widen it.
2. **Money decisions are deterministic.** Caps and eligibility are Python checks in the gateway. The LLM never makes the final yes/no on money.
3. The **LLM sees masked PII** (`<PHONE_1>`, `<UPI_1>`). Real values are restored only inside the gateway.
4. **Fail closed on actions.** If anything is unclear, escalate.

### Repo layout and ownership
```
resolveai/
  requirements.txt                 # shared, append-only
  .env.example                     # GROQ_API_KEY, GEMINI_API_KEY, API_BASE
  shared/contracts.py              # Section 6.1, copied verbatim
  backend/                         # Backend workstream
    app/main.py  db.py  gateway.py  pii.py  mock_paytm.py  seed.py
    tools.yaml
  engine/                          # Agent + UI workstream
    agent.py  llm.py  policy.py  prompts.py  stub_gateway.py  build_index.py
    policy_docs/*.md
  ui/app.py                        # Agent + UI workstream
  scripts/demo_check.py            # Backend workstream (end-to-end smoke test)
```
**Rule:** each workstream edits only its own folders. Need a change elsewhere? Ask.

### Stack
Python 3.11, FastAPI + Uvicorn, SQLite (stdlib `sqlite3`), PyYAML, Pydantic v2, `openai` SDK pointed at Groq (`llama-3.3-70b-versatile`, Gemini Flash as fallback), `sentence-transformers` (`all-MiniLM-L6-v2`), `faiss-cpu`, Streamlit, `requests`.

---

## 6. Contracts (FROZEN)

### 6.1 `shared/contracts.py`
```python
from typing import Any, Literal
from pydantic import BaseModel

Tier = Literal["read_only", "reversible", "money_moving", "sensitive", "protective", "platform"]
ToolStatus = Literal["ok", "blocked", "needs_approval", "error"]
CaseStatus = Literal["open", "need_info", "resolved", "awaiting_approval", "escalated", "rejected"]

class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = {}
    policy_ref: str | None = None        # required by gateway for money_moving tools

class CallContext(BaseModel):
    case_id: str
    session_id: str
    customer_id: str
    verified: bool = True
    step_up_passed: bool = False
    approved_by: str | None = None        # set only when a human approves

class ToolResult(BaseModel):
    status: ToolStatus
    data: dict[str, Any] = {}
    reason: str | None = None
    audit_id: int | None = None
    approval_id: int | None = None

class PolicyResult(BaseModel):
    rule_text: str
    source: str                           # file name, e.g. "paytm_upi_failed_txn.md"
    section: str                          # heading the chunk came from
    score: float
    low_confidence: bool

class ActionTaken(BaseModel):
    tool: str
    status: ToolStatus
    summary: str                          # one human-readable line

class AgentResponse(BaseModel):
    reply: str
    status: CaseStatus
    actions: list[ActionTaken] = []
    citations: list[PolicyResult] = []
    case_summary: str | None = None       # filled when status is awaiting_approval or escalated

class ChatRequest(BaseModel):
    session_id: str
    customer_id: str
    token: str
    message: str

class ChatResponse(AgentResponse):
    case_id: str
```

### 6.2 Gateway interface (Python, Backend workstream)
```python
# backend/app/gateway.py
def tool_definitions() -> list[dict]
    # OpenAI "tools" format built from tools.yaml.
    # money_moving and sensitive tools get an extra optional string arg "policy_ref".
def execute(call: ToolCall, ctx: CallContext) -> ToolResult
```
`engine/stub_gateway.py` implements the same two functions with canned data, so the agent can be built before the real gateway exists.

### 6.3 Policy engine interface (Agent + UI workstream)
```python
# engine/policy.py
def get_policy(query: str, k: int = 3) -> list[PolicyResult]   # sorted by score desc
```
`lookup_policy` is exposed to the LLM as a tool, but the **agent** handles it locally. It never goes through the gateway.

### 6.4 Agent interface (Agent + UI workstream)
```python
# engine/agent.py
def run_agent(message: str, history: list[dict], ctx: CallContext, gateway) -> AgentResponse
    # history: OpenAI-style messages [{"role": "user"|"assistant", "content": str}], already PII-masked
    # gateway: module or object exposing tool_definitions() and execute()
```

### 6.5 `tools.yaml` format
```yaml
tools:
  - name: reverse_payment
    description: Reverse a failed UPI payment that was debited but not credited.
    tier: money_moving
    cap_inr: 2000
    eligible_status: [failed_debited]
    args:
      txn_id: {type: string, required: true}
      amount: {type: number, required: true}
```
Full registry:

| Tool | Tier | Args | Notes |
|---|---|---|---|
| get_customer_profile | read_only | — | uses ctx.customer_id |
| list_recent_transactions | read_only | limit? | |
| get_payment_status | read_only | txn_id | |
| get_wallet_balance | read_only | — | |
| reverse_payment | money_moving | txn_id, amount | cap ₹2,000, status must be `failed_debited`, policy_ref required |
| freeze_wallet | protective | reason | act first |
| update_registered_phone | sensitive | new_phone | needs step-up → needs_approval in the demo |
| schedule_followup | platform | txn_id, minutes | stretch |
| escalate_to_human | platform | reason | sets case to `escalated` |

### 6.6 REST API (Backend workstream)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | /health | — | `{"ok": true}` |
| GET | /customers | — | `[{id, name}]` for the demo dropdown |
| POST | /chat | ChatRequest | ChatResponse. 401 `{"detail":"need_otp"}` if token invalid |
| GET | /cases | `?status=` | `[{id, customer_id, status, summary, created_at}]` |
| GET | /cases/{id} | — | case + `pending_approval` + `audit` list + `messages` |
| POST | /cases/{id}/approve | `{"reviewer": str}` | `{case_id, status, result: ToolResult}` |
| POST | /cases/{id}/reject | `{"reviewer": str, "note": str}` | `{case_id, status}` |
| GET | /audit | `?case_id=` | audit rows, newest first |
| GET | /metrics | — | `{total, resolved, escalated, awaiting_approval, auto_resolution_rate}` |
| GET | /tools | — | parsed tools.yaml (read-only viewer) |

Demo auth: token must equal `demo-<customer_id>`, e.g. `demo-C001`.

### 6.7 Database (SQLite, `backend/resolveai.db`)
```
customers(id PK, name, phone, email, upi_id, wallet_balance, wallet_status)
transactions(id PK, customer_id, amount, payee, type, status, created_at)
sessions(id PK, customer_id, history_json, pii_map_json, current_case_id)
cases(id PK, session_id, customer_id, status, summary, resolution_type, created_at, resolved_at)
approvals(id PK, case_id, tool, args_json, policy_ref, status, reviewer, note, created_at)
audit_log(id PK, ts, case_id, actor, tool, tier, args_masked_json, decision, reason, result_json, policy_ref, idempotency_key)
```
Transaction status values: `success`, `failed_debited`, `reversed`, `pending`.

### 6.8 Seed data (demo)
| Customer | Data | Scenario |
|---|---|---|
| C001 Rahul Sharma, 9876543210, rahul@paytm, wallet ₹1,200 | T1001 ₹499 to Electricity Board, `failed_debited`, 1 day ago | G1 auto-reversal |
| | T1002 ₹5,000 to Flight Booking, `failed_debited`, 2 days ago | G2 escalation |
| | T1003 ₹250 to Grocery, `success` | "is my payment done?" read-only |
| C002 Priya Verma, 9123456780, priya@paytm, wallet ₹3,400 | T2001 ₹1,000 `success` | G3 "account hacked" → freeze |

---

## 7. End-to-end flows

**G1: auto-resolve**
1. Customer: "₹499 got debited for my electricity bill but it failed."
2. Agent → `list_recent_transactions` → `get_payment_status(T1001)` → `lookup_policy("failed UPI debited refund")`
3. Agent → `reverse_payment(T1001, 499, policy_ref="paytm_upi_failed_txn.md#Refunds")`
4. Gateway: tier money_moving, 499 ≤ 2000, status eligible, policy_ref present → mock reverses → audit → ok
5. Agent re-checks status = `reversed` → reply with receipt + citation → case `resolved`

**G2: escalate**
Same flow with T1002 (₹5,000). Gateway → `needs_approval` + approval row. Agent replies "sent to a specialist" with `case_summary` → case `awaiting_approval`. Human approves in the dashboard → backend executes with `ctx.approved_by` → case `resolved`.

**G3: protect**
"Someone hacked my account" → agent calls `freeze_wallet` right away → gateway executes (protective) → reply + `escalate_to_human` for follow-up.

## 8. Failure behaviour
- LLM error or rate limit → retry once on the fallback model → otherwise return `status="escalated"` with a polite reply.
- Policy top score below threshold (`low_confidence`) → agent must not call money_moving tools → escalate.
- Gateway exception → `ToolResult(status="error")` → agent escalates.

## 9. Timeline (4 hours)
| Time | Backend | Agent + UI |
|---|---|---|
| 0:00–0:30 | Repo, contracts.py, DB + seed, tools.yaml | API keys, policy docs, stub_gateway, LLM client works |
| 0:30–1:45 | Mock Paytm, gateway, PII, /chat with stub agent | Agent loop on stub + policy RAG |
| 1:45–2:15 | Cases/approve/audit/metrics endpoints | Streamlit chat + dashboard |
| **2:15–2:45** | **Integration: G1 end to end** | |
| 2:45–3:30 | G2 approve path, demo_check.py | G2/G3 polish, citations in UI |
| **3:30–4:00** | **Feature freeze.** Rehearse, record backup video | |

## 10. Definition of done
- `python scripts/demo_check.py` passes G1, G2 and G3 against the running server.
- Streamlit shows chat, review queue (approve/reject works), audit table and metrics.
- Every money-moving action in the audit log has a `policy_ref`.
