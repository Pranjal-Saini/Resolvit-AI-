# 02: Information Architecture

## 1. Navigation model
A slim **left sidebar** (the console frame) and a **content area**. No top-nav tabs, no nested menus. Four destinations only.

```
┌──────────┬─────────────────────────────────────────────┐
│ ◆ Resolvit│                                             │
│          │   [ page content ]                          │
│ Queue  3 │                                             │
│ Audit    │                                             │
│ Overview │                                             │
│ Tools    │                                             │
│          │                                             │
│ ──────── │                                             │
│ Reviewer │                                             │
│ [Asha  ] │                                             │
│ ● Live   │                                             │
└──────────┴─────────────────────────────────────────────┘
```

| Order | Destination | Purpose | Priority |
|---|---|---|---|
| 1 | **Queue** (default landing) | Triage + decide. The product's core | **P0** |
| 2 | **Audit** | Prove governance (G4) | **P0** |
| 3 | **Overview** | Show AI value, headline metrics | **P1** |
| 4 | **Tools** | Show what the AI may do, and its limits | **P2** |
| ,  | **Customer chat** (demo harness) | Lets us trigger cases live. Separate page, minimal | **P0 for demo**, low design effort |

**Why Queue is first and the default:** the reviewer's first question on opening is "what needs me?". The sidebar badge (count of cases needing a decision) means she knows even when she is on another page.

## 2. Sidebar contents (top to bottom)
1. **Brand mark + product name** (`PRODUCT_NAME`).
2. **Nav items**, each with an icon. **Queue** shows a live count badge (orange) when `awaiting_approval` > 0.
3. **Spacer.**
4. **Reviewer identity**: text input "Your name" (default `Asha`). It is sent as `reviewer` on approve/reject and written to the audit log, so it is also an accountability feature. It must be set before approving (see file 06).
5. **Live status**: small dot, `● Live` (green) when the API responds, `● Offline` (red) when not. Shows the last refresh time on hover or as muted text.

## 3. Page map

### Queue (P0)
- Top: **status strip** (4 compact counters: Needs approval, Escalated, Resolved today, AI resolution rate).
- Body: **master-detail**. Left = case list with filter tabs. Right = case workspace.
- Detail: no separate page. Selecting a row fills the right pane.

### Audit (P0)
- Filter bar + a single dense table + a side drawer for row detail.

### Overview (P1)
- One hero metric (auto-resolution rate), four supporting tiles, a status-mix bar, and a short "Needs you now" list.

### Tools (P2)
- Cards grouped by risk tier. Read-only.

## 4. Case lifecycle as the user sees it
Statuses come from the contract (`CaseStatus`). Each has a *human* label and a meaning for the reviewer.

| API status | Label shown | Meaning for the reviewer | Appears in Queue? |
|---|---|---|---|
| `awaiting_approval` | **Needs approval** | Gateway paused an action. **Your decision is required.** | Yes (top, default tab) |
| `escalated` | **Escalated** | AI handed off (risk, low confidence, error, fraud follow-up). Read-only for now, with a clear "what to do" note | Yes |
| `open` | **AI working** | Conversation in progress | Only under "All" |
| `need_info` | **Waiting on customer** | AI asked the customer a question | Only under "All" |
| `resolved` | **Resolved** | Done, by AI (`auto`) or by a human (`human_approved`) | Under "Resolved" |
| `rejected` | **Rejected** | A human declined the action | Under "Resolved" (as closed) |

**Queue tabs:** `Needs you (n)` · `Escalated (n)` · `Resolved` · `All`. Default = **Needs you**.

## 5. Objects and how they relate (what the UI must make obvious)
```
Case ──has── Customer (name, id)
Case ──has── Messages (the conversation, masked)
Case ──has── Audit rows (every tool call: tier, decision, policy_ref)
Case ──may have── Pending approval (tool, args, policy_ref)
```
The case workspace is organized around exactly these four relations (see file 04).

## 6. Information hierarchy rules
1. **Level 1 (always visible):** who, what action, how much, why it needs a human, the buttons.
2. **Level 2 (one glance below):** AI summary, policy cited, safety checks.
3. **Level 3 (tabs):** evidence timeline, conversation, raw audit.
4. **Level 4 (on demand):** raw JSON, idempotency key, masked args.

Never show Level 4 data by default. Never hide Level 1 data behind a click.
