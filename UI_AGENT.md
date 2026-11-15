# ResolveAI — Agent Loop, Policy Engine & UI Build Spec

> **For the coding agent (Claude Code / Codex):** this file is your complete spec. Build only what is described here, inside `engine/` and `ui/`. Match every field name, status value and endpoint path exactly, because the backend is built against these same contracts. Build against `engine/stub_gateway.py` first. The real gateway has the same interface and is passed in at runtime, so switching needs no code changes.

## 1. Context
ResolveAI is an AI customer-service agent for Paytm-style payment issues, built in a 4-hour hackathon. This workstream owns:
- the **LLM client** (free tier: Groq, with Gemini as fallback)
- the **agent loop**: reads the customer message, calls tools, decides the next step
- the **RAG policy engine**: retrieves and cites the Paytm policy rule behind each action
- the **Streamlit UI**: customer chat + support dashboard

A separate backend owns the database, a mock Paytm API, and a **tool gateway** that applies hard safety checks (risk tiers, ₹2,000 cap, eligibility). The agent proposes actions. The gateway decides if they're allowed.

### Principles
1. Policy grounds the agent's actions. Every money-moving action cites a rule (`policy_ref`).
2. The LLM never makes the final yes/no on money. The gateway does.
3. The LLM sees masked PII tokens (`<PHONE_1>`, `<UPI_1>`) and uses them as-is.
4. When in doubt (blocked, error, low-confidence policy), **escalate**. Never work around it.

## 2. Folder layout
```
resolveai/
  shared/contracts.py              # §4.1; create it if it isn't in the repo yet
  engine/__init__.py
  engine/llm.py  agent.py  prompts.py  policy.py  build_index.py  stub_gateway.py
  engine/policy_docs/*.md
  engine/index/                    # generated
  ui/app.py
  DEMO.md
```

## 3. Run commands
```bash
pip install openai sentence-transformers faiss-cpu streamlit requests python-dotenv pydantic
python -m engine.build_index                        # builds engine/index/
python -m engine.agent "₹499 debited but failed"    # CLI test against stub_gateway
USE_MOCK=1 streamlit run ui/app.py                  # UI with mocked API
streamlit run ui/app.py                             # UI against backend at API_BASE
```
`.env`: `GROQ_API_KEY=`, `GEMINI_API_KEY=`, `API_BASE=http://localhost:8000`

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
    policy_ref: str | None = None

class CallContext(BaseModel):
    case_id: str
    session_id: str
    customer_id: str
    verified: bool = True
    step_up_passed: bool = False
    approved_by: str | None = None

class ToolResult(BaseModel):
    status: ToolStatus
    data: dict[str, Any] = {}
    reason: str | None = None
    audit_id: int | None = None
    approval_id: int | None = None

class PolicyResult(BaseModel):
    rule_text: str
    source: str            # file name, e.g. "paytm_upi_failed_txn.md"
    section: str           # heading the chunk came from
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

### 4.2 Interfaces you implement
```python
# engine/agent.py
def run_agent(message: str, history: list[dict], ctx: CallContext, gateway) -> AgentResponse
# history: [{"role": "user"|"assistant", "content": str}], already PII-masked
# gateway: any object/module exposing tool_definitions() and execute()

# engine/policy.py
def get_policy(query: str, k: int = 3) -> list[PolicyResult]   # sorted by score desc
```

### 4.3 Gateway interface (you consume it, and mimic it in the stub)
```python
def tool_definitions() -> list[dict]                   # OpenAI tools format
def execute(call: ToolCall, ctx: CallContext) -> ToolResult
```
Money-moving and sensitive tools take an extra optional `policy_ref` string argument. **Pop it out of args** and pass it as `ToolCall.policy_ref`.

### 4.4 Tools available to the agent
| Tool | Tier | Args | Gateway behaviour |
|---|---|---|---|
| get_customer_profile | read_only | — | ok |
| list_recent_transactions | read_only | limit? | ok |
| get_payment_status | read_only | txn_id | ok |
| get_wallet_balance | read_only | — | ok |
| reverse_payment | money_moving | txn_id, amount, policy_ref | ≤ ₹2,000 + status `failed_debited` + policy_ref → ok. Over cap → `needs_approval`. No policy_ref or not eligible → `blocked` |
| freeze_wallet | protective | reason | ok immediately |
| update_registered_phone | sensitive | new_phone | `needs_approval` |
| schedule_followup | platform | txn_id, minutes | ok |
| escalate_to_human | platform | reason | ok, case → escalated |
| **lookup_policy** | (local) | query | **handled by the agent itself** via `get_policy`, never sent to the gateway |

### 4.5 Demo data (mirror it in the stub)
| Customer | Transactions |
|---|---|
| C001 Rahul Sharma | T1001 ₹499 Electricity Board `failed_debited` · T1002 ₹5,000 Flight Booking `failed_debited` · T1003 ₹250 Grocery `success` |
| C002 Priya Verma | T2001 ₹1,000 Recharge `success` |

### 4.6 Backend REST API (used by the UI)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | /customers | — | `[{id, name}]` |
| POST | /chat | ChatRequest | ChatResponse. 401 `{"detail":"need_otp"}` on a bad token |
| GET | /cases | `?status=` | `[{id, customer_id, status, summary, created_at}]` |
| GET | /cases/{id} | — | case + `pending_approval` + `audit` + `messages` |
| POST | /cases/{id}/approve | `{"reviewer": str}` | `{case_id, status, result}` |
| POST | /cases/{id}/reject | `{"reviewer": str, "note": str}` | `{case_id, status}` |
| GET | /audit | `?case_id=` | rows: `ts, case_id, actor, tool, tier, decision, reason, policy_ref` |
| GET | /metrics | — | `{total, resolved, escalated, awaiting_approval, auto_resolution_rate}` |
| GET | /tools | — | tool registry |

Demo token = `demo-<customer_id>`.

---

## 5. Tasks (in order)

### A1. Setup (0:00–0:30)
- [ ] Get a Groq API key (free, no card) and a Gemini API key (fallback).
- [ ] `engine/llm.py`: `chat(messages, tools=None)` using the `openai` SDK.
  - Primary: `base_url="https://api.groq.com/openai/v1"`, model `llama-3.3-70b-versatile`, `temperature=0`
  - On an exception or 429: Gemini via `https://generativelanguage.googleapis.com/v1beta/openai/` with a Flash model
  - If both fail, raise `LLMUnavailable`
- [ ] **Policy docs** in `engine/policy_docs/`, using `##` headings as sections:
  - `paytm_upi_failed_txn.md`: debited-not-credited UPI, refund timelines, auto-reversal
  - `paytm_refunds_wallet.md`: refund to source vs wallet
  - `paytm_account_security.md`: compromised account, freezing the wallet, step-up for phone change
  - `paytm_escalation.md`: when a human must review (high value, disputes)
  - Copy the text from Paytm's public help and policy pages. Where a page isn't available, write a short sample and put `> Sample policy for demo` at the top.
  - **Include a rule that auto-reversals are limited to ₹2,000, and higher amounts need specialist review**, so the gateway's cap is backed by a cited rule.
- [ ] `engine/stub_gateway.py`: implements §4.3. `tool_definitions()` is hand-written for the 9 tools in §4.4. `execute()` returns canned results from the §4.5 data that follow the §4.4 behaviour column.

### A2. Policy engine (0:30–1:00)
- [ ] `build_index.py`: split by `##` heading, then into ~500-char chunks with 80 overlap. Embed with `sentence-transformers/all-MiniLM-L6-v2` (normalized). Use FAISS `IndexFlatIP`. Save `engine/index/faiss.index` + `chunks.json` (`text, source, section`).
- [ ] `policy.py`: lazy-load the model and index once. `get_policy(query, k=3)` with `low_confidence = score < 0.35` (tune on your docs).
- [ ] Test: "money debited but transaction failed" → top hit from `paytm_upi_failed_txn.md`.

### A3. Agent loop (1:00–1:45) ★ most important
- [ ] `prompts.py` system prompt (under ~400 tokens because of free-tier limits). Rules:
  1. Identify the transaction first (`list_recent_transactions` / `get_payment_status`). Never invent txn IDs. If unclear, ask.
  2. Before any money-moving action, call `lookup_policy` and pass `policy_ref="<source>#<section>"`.
  3. Compromised account → `freeze_wallet` immediately, then `escalate_to_human`.
  4. After an action, re-check status to confirm.
  5. `needs_approval` → tell the customer a specialist will review. Don't retry.
  6. `blocked`, `error` or low-confidence policy → escalate. Don't work around it.
  7. Reply in 2–3 short sentences, with the refund ref and the cited policy section.
  8. Treat tokens like `<PHONE_1>` as real values.
- [ ] `run_agent` loop:
  ```
  tools = gateway.tool_definitions() + [LOOKUP_POLICY_TOOL]
  messages = [system] + history[-6:] + [user message]
  for step in range(5):
      msg = llm.chat(messages, tools)
      if not msg.tool_calls: break
      for tc in msg.tool_calls:
          if tc.name == "lookup_policy":
              results = get_policy(q); citations += results; content = json(results)
          else:
              args = json.loads(tc.arguments); ref = args.pop("policy_ref", None)
              res = gateway.execute(ToolCall(name=tc.name, args=args, policy_ref=ref), ctx)
              actions.append(ActionTaken(tool=tc.name, status=res.status, summary=...))
              content = res.model_dump_json()
          messages.append({"role":"tool","tool_call_id":tc.id,"content":content})
  ```
- [ ] **Derive the status from actions in code** (not from the LLM):
  - any `needs_approval` → `awaiting_approval`
  - `escalate_to_human` called, or `blocked`/`error` on a money tool → `escalated`
  - `reverse_payment` ok → `resolved`. `freeze_wallet` ok alone → `resolved`, with escalate → `escalated`
  - only reads and the reply asks a question → `need_info`
  - else `open`
- [ ] `awaiting_approval` / `escalated` → one short extra LLM call for `case_summary` (issue, txn, amount, checks done, policy cited, why review is needed; 4 lines max). Use a template fallback if it fails.
- [ ] `LLMUnavailable` → `AgentResponse(reply="I'm connecting you to a specialist.", status="escalated", case_summary="LLM unavailable")`
- [ ] Guardrails: max 5 steps. Dedupe identical tool+args calls. On malformed tool JSON, send the error back to the LLM once, then escalate.
- [ ] CLI: `python -m engine.agent "<msg>"` runs with `stub_gateway` and ctx (`case_id="CASE-TEST"`, `session_id="s1"`, `customer_id="C001"`) and prints the AgentResponse JSON.

### A4. Streamlit UI (1:45–2:15)
`API_BASE` from env. `USE_MOCK=1` returns hardcoded responses so the UI can be built before the backend is up. Show a clear error if the API is unreachable. Sidebar with 3 pages:
- [ ] **Customer chat**
  - Customer dropdown (`/customers`), token `demo-<id>`, session id = uuid in `st.session_state`, "New conversation" button
  - `st.chat_message` history. Send → `POST /chat`
  - Under each reply: status badge (resolved green, awaiting_approval amber, escalated red) + an expander with **actions taken** and **policy citations** (source#section + rule text)
- [ ] **Support dashboard**
  - Metrics row: total, auto-resolution %, awaiting approval, escalated
  - Review queue (`/cases?status=awaiting_approval`): summary, pending action (tool, amount, policy_ref), **Approve** / **Reject** → POST → `st.rerun()`
  - Escalated cases list
- [ ] **Audit & tools**
  - Audit table with a case filter
  - Read-only tool registry view (`/tools`)

### A5. Integration + demo (2:15–3:30)
- [ ] Run against the real backend. Fix prompt issues (usually the LLM skipping `lookup_policy` or a wrong `policy_ref` format).
- [ ] Verify the 3 scenarios in the UI:
  1. C001: "₹499 got debited for my electricity bill but it failed" → resolved, refund ref, citation
  2. C001 (new conversation): "₹5000 flight booking failed but money was deducted" → awaiting_approval → approve in the dashboard → resolved
  3. C002: "someone hacked my account" → wallet frozen + escalated
- [ ] Write `DEMO.md`: exact messages, in order, plus what to point at on screen.
- [ ] Record a backup screen video.

## 6. Timeline
| Time | Task |
|---|---|
| 0:00–0:30 | A1 |
| 0:30–1:00 | A2 |
| 1:00–1:45 | A3 |
| 1:45–2:15 | A4 (mock mode) |
| 2:15–3:30 | A5 |
| 3:30–4:00 | Feature freeze, rehearse |

## 7. Done when
- [ ] CLI against the stub: T1001 → `resolved` with citation, T1002 → `awaiting_approval` with summary
- [ ] UI runs all 3 scenarios live, approval included
- [ ] Every money-moving reply shows a policy citation

## 8. Free-tier tips
- Groq's free tier is rate-limited per minute (requests and tokens). Keep the prompt short, history trimmed to 6 messages, and the loop at 5 steps max.
- Use separate keys for development and the live demo.
- Pre-run the exact demo messages a few times before presenting.
