# ResolveAI — Backend Build Spec

> **For the coding agent (Claude Code / Codex):** this file is your complete spec. Build only what is described here, inside `backend/`, `shared/` and `scripts/`. Match every field name, status value and endpoint path exactly, because another part of the system is built against these same contracts. Keep it simple: Python 3.11, FastAPI, SQLite via stdlib `sqlite3` (no ORM), PyYAML, Pydantic v2. No Redis, no Docker, no Postgres.

## 1. Context
ResolveAI is an AI customer-service agent for Paytm-style payment issues, built in a 4-hour hackathon. An LLM agent decides what to do. **The backend decides what is allowed.** It owns:
- the FastAPI server and SQLite database
- a **mock Paytm API** (fake customers, transactions, wallet)
- a **tool registry** (`tools.yaml`) with risk tiers and amount caps
- the **tool gateway**: every action the agent wants to take passes deterministic safety checks here
- PII masking, the audit log, cases, and human approvals

The agent module (`engine.agent.run_agent`) is built separately. You call it from `/chat`. Until it exists, use the local stub described in B7.

### Principles
1. The gateway is the **hard ceiling**. Nothing executes without passing its checks.
2. **Money decisions are deterministic Python checks**, never LLM judgment.
3. The LLM only ever sees **masked PII**. Real values are restored only inside the gateway.
4. **Fail closed** on actions. Every decision is audited, including blocked ones.

## 2. Folder layout
```
resolveai/
  requirements.txt  .env.example
  shared/__init__.py  shared/contracts.py
  backend/__init__.py
  backend/tools.yaml
  backend/app/__init__.py  main.py  db.py  gateway.py  pii.py  mock_paytm.py  seed.py
  scripts/demo_check.py
```

## 3. Run commands
```bash
pip install -r requirements.txt
python -m backend.app.seed                       # creates and resets backend/resolveai.db
uvicorn backend.app.main:app --reload --port 8000
python scripts/demo_check.py                     # end-to-end smoke test
```

---

## 4. Contracts (frozen, copy exactly)

### 4.1 `shared/contracts.py`
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
    source: str
    section: str
    score: float
    low_confidence: bool

class ActionTaken(BaseModel):
    tool: str
    status: ToolStatus
    summary: str

class AgentResponse(BaseModel):
    reply: str
    status: CaseStatus
    actions: list[ActionTaken] = []
    citations: list[PolicyResult] = []
    case_summary: str | None = None

class ChatRequest(BaseModel):
    session_id: str
    customer_id: str
    token: str
    message: str

class ChatResponse(AgentResponse):
    case_id: str
```

### 4.2 Gateway interface (you implement it)
```python
# backend/app/gateway.py
def tool_definitions() -> list[dict]          # OpenAI "tools" format, built from tools.yaml
def execute(call: ToolCall, ctx: CallContext) -> ToolResult
```

### 4.3 Agent interface (you call it, someone else implements it)
```python
# engine/agent.py
def run_agent(message: str, history: list[dict], ctx: CallContext, gateway) -> AgentResponse
# history: [{"role": "user"|"assistant", "content": str}], already PII-masked
# gateway: pass the backend.app.gateway module
```

### 4.4 Tool registry (`backend/tools.yaml`)
| Tool | Tier | Args | Rules |
|---|---|---|---|
| get_customer_profile | read_only | — | uses ctx.customer_id |
| list_recent_transactions | read_only | limit (int, optional) | |
| get_payment_status | read_only | txn_id (str) | |
| get_wallet_balance | read_only | — | |
| reverse_payment | money_moving | txn_id (str), amount (number) | `cap_inr: 2000`, `eligible_status: [failed_debited]`, policy_ref required |
| freeze_wallet | protective | reason (str) | execute immediately |
| update_registered_phone | sensitive | new_phone (str) | step-up → needs_approval |
| schedule_followup | platform | txn_id (str), minutes (int) | stretch |
| escalate_to_human | platform | reason (str) | sets case to `escalated` |

YAML entry format:
```yaml
tools:
  - name: reverse_payment
    description: Reverse a failed UPI payment that was debited but not credited. Use only after checking status and policy.
    tier: money_moving
    cap_inr: 2000
    eligible_status: [failed_debited]
    args:
      txn_id: {type: string, required: true}
      amount: {type: number, required: true}
```

### 4.5 REST API
| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | /health | — | `{"ok": true}` |
| GET | /customers | — | `[{id, name}]` |
| POST | /chat | ChatRequest | ChatResponse. 401 `{"detail":"need_otp"}` if token invalid |
| GET | /cases | `?status=` | `[{id, customer_id, status, summary, created_at}]` |
| GET | /cases/{id} | — | case + `pending_approval` (or null) + `audit` list + `messages` |
| POST | /cases/{id}/approve | `{"reviewer": str}` | `{case_id, status, result: ToolResult}` |
| POST | /cases/{id}/reject | `{"reviewer": str, "note": str}` | `{case_id, status}` |
| GET | /audit | `?case_id=` | audit rows, newest first |
| GET | /metrics | — | `{total, resolved, escalated, awaiting_approval, auto_resolution_rate}` |
| GET | /tools | — | parsed tools.yaml |

Demo auth: token must equal `demo-<customer_id>`, e.g. `demo-C001`.

### 4.6 Database (`backend/resolveai.db`)
```
customers(id PK, name, phone, email, upi_id, wallet_balance, wallet_status)
transactions(id PK, customer_id, amount, payee, type, status, created_at)
sessions(id PK, customer_id, history_json, pii_map_json, current_case_id)
cases(id PK, session_id, customer_id, status, summary, resolution_type, created_at, resolved_at)
approvals(id PK, case_id, tool, args_json, policy_ref, status, reviewer, note, created_at)
audit_log(id PK, ts, case_id, actor, tool, tier, args_masked_json, decision, reason, result_json, policy_ref, idempotency_key)
```
Transaction status: `success | failed_debited | reversed | pending`. Wallet status: `active | frozen`.

### 4.7 Seed data
| Customer | Transactions | Demo scenario |
|---|---|---|
| C001 Rahul Sharma, 9876543210, rahul@example.com, rahul@paytm, wallet ₹1,200, active | T1001 ₹499 Electricity Board, `failed_debited`, 1 day ago | auto-reversal |
| | T1002 ₹5,000 Flight Booking, `failed_debited`, 2 days ago | over cap → human approval |
| | T1003 ₹250 Grocery, `success` | read-only status check |
| C002 Priya Verma, 9123456780, priya@example.com, priya@paytm, wallet ₹3,400, active | T2001 ₹1,000 Recharge, `success` | "account hacked" → freeze |

---

## 5. Tasks (in order)

### B1. Setup (0:00–0:15)
- [ ] Create the layout from §2. `shared/contracts.py` = §4.1 verbatim.
- [ ] `requirements.txt`: `fastapi uvicorn pydantic pyyaml requests openai sentence-transformers faiss-cpu streamlit python-dotenv`
- [ ] `.env.example`: `GROQ_API_KEY=`, `GEMINI_API_KEY=`, `API_BASE=http://localhost:8000`

### B2. Database + seed (0:15–0:30)
- [ ] `db.py`: `get_conn()` (`row_factory=sqlite3.Row`, `check_same_thread=False`), `init_db()` for the §4.6 tables, helpers `fetch_one`, `fetch_all`, `execute`.
- [ ] `seed.py`: drop and recreate, insert §4.7 with relative timestamps.
- [ ] Case IDs `CASE-0001`, …. Session IDs come from the client. Approvals and audit use autoincrement ints.

### B3. Tool registry (0:30–0:40)
- [ ] Write all 9 tools from §4.4 in `tools.yaml`. Descriptions are written for an LLM: short, saying when to use each tool.

### B4. Mock Paytm API, `mock_paytm.py` (0:40–1:00)
Plain functions over SQLite:
- [ ] `get_customer_profile(customer_id)`
- [ ] `list_recent_transactions(customer_id, limit=5)`
- [ ] `get_payment_status(customer_id, txn_id)`: raise an error if the txn isn't this customer's
- [ ] `get_wallet_balance(customer_id)`
- [ ] `reverse_payment(customer_id, txn_id, amount)` → status `reversed`, credit the wallet, return `{refund_ref: "RFND-<txn>", amount, credited_to: "wallet"}`
- [ ] `freeze_wallet(customer_id, reason)` → `frozen`
- [ ] `update_registered_phone(customer_id, new_phone)`
- [ ] `schedule_followup(...)` → `{followup_id}`
- [ ] `escalate_to_human(case_id, reason)` → case `escalated`
- [ ] `DISPATCH = {tool_name: fn}`

### B5. PII masking, `pii.py` (1:00–1:10)
- [ ] `mask(text, session_id)`: Indian phone `[6-9]\d{9}`, email, UPI id, 12–16 digit numbers → `<PHONE_1>`, `<EMAIL_1>`, `<UPI_1>`, `<ACCT_1>`. Store the mapping in `sessions.pii_map_json`. The same value always gets the same token.
- [ ] `unmask(obj, session_id)`: recursive over str, dict and list.
- [ ] `mask_obj(obj, session_id)`: masks tool results before they go to the LLM, and audit args.

### B6. Gateway, `gateway.py` (1:10–1:45) ★ most important
- [ ] `load_registry()` (cached).
- [ ] `tool_definitions()` → `{"type":"function","function":{"name","description","parameters":{"type":"object","properties":{...},"required":[...]}}}`. Add an optional `policy_ref: string` to `money_moving` and `sensitive` tools ("citation of the policy rule allowing this action").
- [ ] `execute(call, ctx)`. Apply these checks **in order** and audit **every** outcome:
  1. Unknown tool → `blocked`
  2. Required args missing or wrong type → `error`
  3. `ctx.verified` false and tier ≠ read_only → `blocked`
  4. Idempotency: `sha256(case_id + name + sorted args)`. If an executed row with that key exists, return its stored result.
  5. Tier rules:
     - `read_only`, `reversible`, `protective`, `platform` → execute
     - `sensitive` → execute only if `step_up_passed` or `approved_by`. Otherwise create an approval → `needs_approval`
     - `money_moving`:
       - no `policy_ref` and no `approved_by` → `blocked` "policy_ref required"
       - txn not the customer's, or status not in `eligible_status` → `blocked` (with reason)
       - `amount` > txn amount → `blocked`
       - `amount` > `cap_inr` and no `approved_by` → insert a `pending` approval, case → `awaiting_approval`, return `needs_approval` + `approval_id`
       - else execute
  6. Execute: `unmask(args)` → `DISPATCH[name]` → `mask_obj(result)` → audit `executed` → `ok`
  7. Any exception → audit → `ToolResult(status="error", reason=str(e))`
- [ ] `audit(...)` helper returns the row id. `actor` = `"agent"` or the reviewer's name.

### B7. Endpoints, `main.py` (1:45–2:15)
- [ ] CORS open. Call `init_db()` on startup.
- [ ] `POST /chat`:
  1. Bad token → 401 `need_otp`
  2. Load or create the session. Reuse `current_case_id` if the case is `open` or `need_info`, else create a new case.
  3. `masked = pii.mask(message, session_id)`, append to history
  4. `try: from engine.agent import run_agent` / `except ImportError:` use a **local stub** that returns `AgentResponse(reply="(stub) received", status="open")`, so you're never blocked
  5. `resp = run_agent(masked, history[-6:], ctx, gateway)`. If it raises, return `status="escalated"` with a polite reply.
  6. Save the reply to history. Update case status and summary from `resp`. If resolved, set `resolved_at` and `resolution_type="auto"`.
  7. Return `ChatResponse(**resp.model_dump(), case_id=...)` with the reply text unmasked.
- [ ] `GET /customers`, `/cases`, `/cases/{id}`, `/audit`, `/metrics`, `/tools`, `/health`
- [ ] `POST /cases/{id}/approve`: execute the pending approval through `gateway.execute` with `ctx.approved_by=reviewer` → approval `approved`, case `resolved`, `resolution_type="human_approved"` → append to session history "Your refund of ₹X has been approved and processed. Ref: …"
- [ ] `POST /cases/{id}/reject` → approval and case `rejected` + a polite message in history
- [ ] `auto_resolution_rate = auto_resolved / total` (0 when there are no cases)

### B8. Gateway unit checks (alongside B6, no LLM needed)
```python
execute(ToolCall(name="reverse_payment", args={"txn_id":"T1001","amount":499}, policy_ref="x"), ctx)   # ok
execute(ToolCall(name="reverse_payment", args={"txn_id":"T1002","amount":5000}, policy_ref="x"), ctx)  # needs_approval
execute(ToolCall(name="reverse_payment", args={"txn_id":"T1003","amount":250}, policy_ref="x"), ctx)   # blocked: not eligible
execute(ToolCall(name="reverse_payment", args={"txn_id":"T1001","amount":499}), ctx)                   # blocked: no policy_ref
execute(ToolCall(name="drop_tables", args={}), ctx)                                                    # blocked: unknown
# repeat the first call → same result, no second reversal (idempotent)
```

### B9. Smoke test, `scripts/demo_check.py` (2:45–3:15)
Re-seed, then over HTTP:
- [ ] C001: "₹499 debited for electricity bill but it failed" → `resolved`, T1001 `reversed`, an audit row with `policy_ref`
- [ ] New session, C001: "₹5000 flight booking failed, money deducted" → `awaiting_approval`. Approve → `resolved`
- [ ] C002: "someone hacked my account" → wallet `frozen`
- [ ] Bad token → 401
- [ ] Print ✅/❌ per check

## 6. Timeline
| Time | Task |
|---|---|
| 0:00–0:30 | B1, B2 |
| 0:30–1:10 | B3, B4, B5 |
| 1:10–1:45 | B6 + B8 |
| 1:45–2:15 | B7 |
| 2:15–2:45 | Integration with the real agent |
| 2:45–3:30 | B9, approval-path fixes |
| 3:30–4:00 | Feature freeze, rehearse demo |

## 7. Done when
- [ ] B8 checks behave as listed
- [ ] `demo_check.py` is all ✅
- [ ] The audit log shows blocked, needs_approval and executed rows, each with tier and decision

## 8. Stretch (only after §7 passes)
- Follow-up timer: an asyncio task every 30s rechecks `pending` txns from `schedule_followup`
- `/cases/{id}` returns a timeline of events
