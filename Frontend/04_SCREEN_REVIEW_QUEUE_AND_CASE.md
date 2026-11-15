# 04: Screen Spec: Review Queue and Case Workspace (the core)

This is the product. If time is short, perfect this screen and cut the rest.

**Data sources:** `GET /cases?status=`, `GET /cases/{id}`, `GET /customers`, `GET /metrics`, `POST /cases/{id}/approve`, `POST /cases/{id}/reject`. Field availability is detailed in file 07.

## 1. Layout (desktop, ≥1280px)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ Review queue                                                  ↻ 12s ago   │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  ← status strip   │
│ │Needs you │ │Escalated │ │Resolved  │ │AI resolution │                   │
│ │    2     │ │    1     │ │    5     │ │    71%       │                   │
│ └──────────┘ └──────────┘ └──────────┘ └──────────────┘                   │
├──────────────────────────┬────────────────────────────────────────────────┤
│ [Needs you 2][Escalated 1│  CASE WORKSPACE                                │
│  ][Resolved][All]        │  (see §3)                                      │
│ ──────────────────────── │                                                │
│ ● Rahul Sharma    2d ago │                                                │
│   Flight · ₹5,000  [Needs│                                                │
│   CASE-0007              │                                                │
│ ──────────────────────── │                                                │
│   Priya Verma     5m ago │                                                │
│   ...                    │                                                │
└──────────────────────────┴────────────────────────────────────────────────┘
        ~38% (list)                          ~62% (workspace)
```
- Both columns scroll independently. The status strip is fixed at the top of the content area.
- **Auto-select:** on load, the oldest `awaiting_approval` case is selected so the reviewer lands directly on a decision. If none, the first escalated case. If none, show the "All clear" empty state.

## 2. Case list (left pane)

### 2.1 Tabs / filters
`Needs you (n)` · `Escalated (n)` · `Resolved` · `All`. Counts come from the loaded list. Default = **Needs you**.

### 2.2 Sort
- Needs you / Escalated: **oldest first** (longest waiting = most urgent).
- Resolved / All: **newest first**.

### 2.3 Row content (see `case_row`)
| Element | Source | Fallback |
|---|---|---|
| Customer name | `/customers` lookup by `customer_id` | Show `customer_id` |
| What line | For `awaiting_approval`: `"<payee> · ₹<amount> reversal"` from `pending_approval`; otherwise first ~60 chars of `summary` | "No summary yet" |
| Status chip | `status` | |
| Age | `created_at` as relative time ("2d ago", "5m ago") | |
| Case ID | `id` | |

### 2.4 Empty states
| Situation | Message |
|---|---|
| No cases need approval | Icon: check-circle (success). **"All clear."** "The AI is handling everything else. New cases that need you will appear here automatically." |
| No escalations | "No escalated cases." |
| Nothing at all | "No cases yet. Start a conversation from the Customer chat page to see one appear." (link to chat page) |

## 3. Case workspace (right pane)
Top to bottom. The order is deliberate: **decision → reason → evidence**.

### 3.1 Header
```
CASE-0007  [Needs approval]                              Opened 2d ago
Rahul Sharma · C001 · rahul@paytm (masked if shown)
```
- Case ID in mono with copy button. Status chip. Relative age (hover = exact time).
- Customer name + ID. **Do not show raw phone/email** unless needed. If shown, show masked form (`98••••3210`).

### 3.2 Decision card (only when `status == awaiting_approval`)
White card, 3px orange top border.

**Title (H2, plain language):** `Approve ₹5,000 reversal to Rahul Sharma's wallet?`

**Why this needs you** (Attention callout, one sentence, derived from the audit `needs_approval` row reason or computed):
> ⚠ This amount is **₹3,000 above the ₹2,000 auto-approval limit**, so the AI cannot refund it alone.

**Fact grid** (3 columns):
| Transaction | Amount | Customer |
|---|---|---|
| `T1002` · Flight Booking | ₹5,000 | Rahul Sharma (C001) |
| Status: Failed, debited | Limit: ₹2,000 | Wallet: ₹1,200 |
| 2 days ago | Action: Reverse payment | Policy: `paytm_upi_failed_txn.md#Refunds` |

(Fill each cell from `pending_approval.args_json`, `/audit` rows and `/cases/{id}`; omit any cell whose data is unavailable. Never show "None" or "undefined".)

**Safety checks** (check_item list, derived from audit rows and approval data):
- ✓ Customer verified
- ✓ Transaction belongs to this customer
- ✓ Transaction status is eligible (failed, debited)
- ✓ Amount does not exceed the original transaction
- ✓ Policy cited
- ⚠ Amount exceeds auto-approval limit → human approval required

*If a check cannot be determined from available data, leave it out. Do not invent passes.*

**Action bar** (right-aligned at the bottom of the card):
`[ Reject ]   [ Approve ₹5,000 & execute ]`
- Primary label always contains the **exact amount**.
- Both disabled with a tooltip "Enter your name in the sidebar to continue" if the reviewer name is empty.

### 3.3 AI summary
Card titled **"What the AI found"**. Shows `case_summary` / `summary`. Render as 2–4 short lines. If the text is a single blob, show as-is. **Do not parse it**. Below it, a muted line: *"Prepared by the AI agent. You never need to re-ask the customer."*

### 3.4 Policy applied
`policy_callout` using the `policy_ref` (parse `file.md#Section` into `source` › `section`). If a money action has **no** policy_ref, show the Danger variant ("No policy cited, review carefully").

### 3.5 Tabs: **Timeline · Conversation · Audit**
Default tab = **Timeline**.

**Timeline.** One item per audit row of this case, oldest first, in plain language:
| Audit row | Sentence shown |
|---|---|
| `get_payment_status` executed | "Checked status of payment T1001" |
| `list_recent_transactions` executed | "Looked up recent transactions" |
| `reverse_payment` executed | "Reversed ₹499 for T1001 → wallet" + `RFND-T1001` mono |
| `reverse_payment` needs_approval | "Asked for human approval: ₹5,000 is above the ₹2,000 limit" |
| `reverse_payment` blocked | "Blocked: <reason>" (Danger) |
| `freeze_wallet` executed | "Froze wallet to protect the account" |
| `escalate_to_human` executed | "Handed to a human reviewer: <reason>" |
| approval by human | "<reviewer> approved the reversal" (actor ≠ agent) |
Unknown tool → "Ran <tool_name>". Each item: sentence, tier chip, decision chip, time, actor. Expand arrow reveals masked args and `policy_ref`.

**Conversation.** Chat bubbles from `messages`. Customer left (neutral bubble), AI right (brand-tint). Messages are already PII-masked; show as returned. Read-only.

**Audit.** Compact table of this case's audit rows (same columns as the Audit page, file 05).

### 3.6 Escalated cases (no approval row)
Escalated cases (fraud follow-up, low-confidence policy, agent error) have **no pending approval**. Do **not** show Approve/Reject. Instead show an **Escalation card** (Escalated style):
> **Handed to a human.** Reason: *<reason from escalate_to_human audit row or summary>*
> **What's been done:** Wallet frozen · Case summary prepared
> **Suggested next step:** Contact the customer to verify identity. *(static helper copy based on the reason keywords: fraud/hack → verify identity & review activity; otherwise "Review the conversation and follow up with the customer".)*

Below it, the same AI summary / policy / tabs sections. There is no "Mark handled" button because the API has no endpoint for it (see file 07, gaps).

### 3.7 Resolved / rejected cases
Show a **Resolution card** instead of the decision card:
- Resolved by AI: success top border, "**Resolved automatically**: ₹499 reversed to wallet. Ref `RFND-T1001`."
- Resolved by human: "**Approved by Asha**: ₹5,000 reversed. Ref `RFND-T1002`."
- Rejected: Danger top border, "**Rejected by Asha**" + the note.
Then the same summary, policy and tabs.

## 4. Approve flow (exact behavior)
1. Click **Approve ₹5,000 & execute** → **confirmation dialog**:
   - Title: "Confirm approval"
   - Fact grid: Action (Reverse payment), Amount (₹5,000), To (Rahul Sharma's wallet), Transaction (T1002), Approving as (Asha)
   - Line: "This will move money immediately and is recorded in the audit log."
   - Buttons: `Cancel` · `Approve & execute`
2. On confirm: button shows loading state (disabled, "Executing…"). Call `POST /cases/{id}/approve {reviewer}`.
3. **Success** (`result.status == "ok"`): toast "✓ Approved. ₹5,000 reversed (RFND-T1002)". The case moves to **Resolved**, the workspace swaps to the Resolution card, the list auto-selects the **next case needing approval** (keeps the reviewer in flow). Counters refresh.
4. **Result not ok** (`blocked` / `error`): keep the case selected, show an inline Danger callout above the action bar with `result.reason` in plain language and a "Try again" button. Never close the dialog silently on failure.

## 5. Reject flow
1. Click **Reject** → inline panel expands inside the decision card (not a dialog):
   - Label: "Reason for rejecting (shown to the customer politely)"
   - **Quick-reason chips** (click to fill): `Duplicate request` · `Transaction already settled` · `Policy doesn't allow this` · `Needs more verification`
   - Text area (required, min 3 chars).
   - Buttons: `Cancel` · `Reject case` (Danger-quiet, disabled until a reason exists).
2. On confirm: `POST /cases/{id}/reject {reviewer, note}`. Toast "Case rejected". Case moves to **Resolved/closed** with the Rejected resolution card. Auto-select next.

## 6. Status strip (top of page)
Four `stat_tile`s from `/metrics` and the loaded list:
| Tile | Value | Accent |
|---|---|---|
| Needs you | `awaiting_approval` | Attention if > 0 |
| Escalated | `escalated` | none |
| Resolved | `resolved` | none |
| AI resolution rate | `auto_resolution_rate` as a percentage, 0 decimals | Success tint, hint: "handled without a human" |

## 7. Edge cases
- **Case changed while open** (someone else approved): on refresh, if the selected case is no longer `awaiting_approval`, replace the action bar with a notice "This case was just resolved" and do not allow double-action. The backend is idempotent, but the UI must not look like it can double-spend.
- **No pending_approval but status is `awaiting_approval`** (inconsistent data): show the AI summary with a Danger callout "Approval details unavailable. Do not act from here" and disable buttons.
- **Very long summaries:** clamp to 6 lines with "Show more".
- **Slow API:** show skeleton blocks (grey bars) in the workspace, never a blank pane.
