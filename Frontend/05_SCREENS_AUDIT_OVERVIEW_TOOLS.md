# 05: Screen Specs: Audit, Overview, Tools, and Customer Chat (demo harness)

## 1. Audit (P0): "Every action, governed"
**Purpose:** answer G4 on one screen. Show that every tool call the AI attempted was checked, with tier, decision and policy reference.
**Data:** `GET /audit` and `GET /audit?case_id=`.

### Layout
```
Audit log                                                 [ Export CSV ]
Every action the AI attempted, and what the gateway decided.

[Case: All ▾]  [Decision: All ▾]  [Tier: All ▾]  [Search tool…]        14 events
─────────────────────────────────────────────────────────────────────────────────
TIME     CASE       ACTOR   TOOL               TIER        DECISION      POLICY
10:42    CASE-0007  Asha    reverse_payment    Money       ● Executed    paytm_upi…#Refunds
10:41    CASE-0007  agent   reverse_payment    Money       ● Needs appr. paytm_upi…#Refunds
10:40    CASE-0007  agent   get_payment_status Read        ● Executed    —
```

### Rules
- **Header sentence** (muted) above the filters explains the page in one line. No jargon.
- **Columns (left to right):** Time (relative + exact on hover), Case (mono, links to Queue with that case selected), Actor (`agent` vs. human name; human names are bolded to stand out), Tool (mono), Tier (chip), Decision (chip), Policy ref (mono, truncated with tooltip).
- **Newest first** (API order).
- **Filters** are client-side: Case (dropdown of case ids found), Decision, Tier, free-text tool search. Show active-filter count and a "Clear" ghost button.
- **Governance flag (the DoD rule):** any row with tier = money and decision = executed and **no policy_ref** gets a Danger "Missing policy" chip in the Policy column and a pale-red row tint. This should never appear in a correct system, which is exactly why it is worth showing.
- **Row click** opens a right-side **drawer** (420px): plain-language sentence, then fact grid (time, actor, tool, tier, decision, reason, policy_ref, audit id), then collapsible sections **Arguments (masked)** and **Result** (formatted JSON in mono on `--surface-sunken`), and the idempotency key at the bottom (subtle, copyable). Esc closes.
- **Pagination:** none needed. Show up to ~200 rows, then a muted "Showing latest 200".
- **Empty state:** "No audit events yet. Every action the AI takes will be recorded here."

### Header chips (a small summary row above the table, optional P1)
`Executed 9` · `Needs approval 2` · `Blocked 3` · `Errors 0`. These double as quick filters.

---

## 2. Overview (P1): "Is the AI earning its keep?"
**Purpose:** show business value at a glance and give managers the headline. Keep it deliberately small. The API gives five numbers; present them beautifully instead of inventing more.
**Data:** `GET /metrics`, `GET /cases?status=awaiting_approval`.

### Layout
```
Overview

┌────────────────────────────────────────────┐  ┌───────────┐ ┌───────────┐
│ AI resolution rate                         │  │ Total     │ │ Resolved  │
│ 71%                    (Display, 32px)     │  │ cases  7  │ │       5   │
│ handled end to end without a human         │  └───────────┘ └───────────┘
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░  (progress bar)      │  ┌───────────┐ ┌───────────┐
└────────────────────────────────────────────┘  │ Escalated │ │ Awaiting  │
                                                │       1   │ │ approval 1│
Case outcomes                                   └───────────┘ └───────────┘
[██████ resolved ██][▒ awaiting][▒ escalated]   ← one stacked horizontal bar + legend

Needs you now (2)                                          [ Open queue → ]
 • CASE-0007  Rahul Sharma  ₹5,000 reversal  2d
```

### Rules
- Hero card is the largest element; the rate is formatted `71%` (round, no decimals). Hint under it: "handled end to end without a human".
- **Never show a trend arrow or "vs last week"**; there is no historical data. Do not fabricate any.
- Stacked bar segments use Success / Attention / Escalated colors with a legend containing counts.
- "Needs you now" lists up to 3 cases (same `case_row`), with an "Open queue" primary-text link. If none: the "All clear" empty state.
- If `total == 0`: show "No cases yet" and the rate as "—" (never "0%", which looks like failure).

---

## 3. Tools (P2): "What the AI is allowed to do"
**Purpose:** transparency for managers; supports the pitch's "autonomy by risk tier" message. Read-only viewer of `GET /tools`.

### Layout
Intro line: "The AI can only use these tools, and the gateway enforces each limit. Policies can narrow what the AI does, never widen it."
Group cards by tier, ordered **low risk → high risk**: Read, Reversible, Platform, Protective, Sensitive, Money.

Each **tool card** shows:
- Tool name (mono) and a one-line description.
- Tier chip + a **guardrail line** in plain language, e.g.
  - Money: "Capped at ₹2,000. Only for payments that failed after debit. Requires a policy citation. Above the cap, a human must approve."
  - Sensitive: "Requires step-up verification or human approval."
  - Protective: "Runs immediately to protect the customer."
  - Read: "No limits. Looks up data only."
- Arguments as small chips: `txn_id` (required), `amount` (required), `limit` (optional).
- Fields to read: `tier`, `cap_inr`, `eligible_status`, `args`.

Add a top **legend row** that explains the six tier chips (one line each). No edit controls. If `/tools` shape differs from expectation, render unknown fields as a key/value list. Never crash.

---

## 4. Customer chat (demo harness, minimal design effort)
**Purpose:** let the team trigger G1–G3 live. It is **not** the reviewer's product, so spend little time here, but it must not look broken on stage.
- Sidebar-less page. Centered column, max 720px.
- Top bar: customer dropdown (`/customers`), shows "Chatting as Rahul Sharma (C001)". Token is derived automatically (`demo-<customer_id>`). Never display the token.
- Message bubbles: customer right (brand), AI left (surface with border). Under each AI message show **action chips** from `actions` (e.g. `✓ reverse_payment · Reversed ₹499`) and a **policy citation chip** from `citations` (`paytm_upi_failed_txn.md › Refunds`). This is what judges see for G1.
- Status banner under the AI reply when `status` is `awaiting_approval` ("Sent to a specialist"), `escalated`, or `resolved`.
- Quick-prompt buttons (demo accelerators): "₹499 debited for my electricity bill but it failed", "₹5000 flight booking failed, money deducted", "Someone hacked my account", "Is my grocery payment done?".
- Generate a fresh `session_id` per "New conversation" button.
- Handle 401 `need_otp` with a friendly "Session expired. Please sign in again."
