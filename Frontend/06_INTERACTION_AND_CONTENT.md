# 06: Interaction, States, Content and Accessibility

## 1. Live updates
- The console polls; there is no websocket. **Refresh every 5 seconds** the queue, counts, and sidebar badge. Pause polling while a dialog or reject panel is open, so the screen never shifts under the reviewer.
- **Never reset the user's place.** A refresh must keep the selected case, the active tab, the scroll position, and any text typed in the reject note.
- **New arrival cue:** when a new `awaiting_approval` case appears, (a) the sidebar badge count increments, (b) the row gets a one-time orange-tint fade, (c) a quiet toast "New case needs approval: Rahul Sharma, ₹5,000". Do **not** auto-switch the selected case; let her finish what she is reading.
- "Live" indicator in the sidebar; hover/subtext shows "Updated 3s ago".

## 2. Loading, empty, error: required for every data region
| State | Treatment |
|---|---|
| **Loading (first)** | Skeleton blocks matching the final layout (grey rounded bars). No full-page spinner |
| **Loading (refresh)** | Silent. No flicker, no spinner |
| **Empty** | `empty_state` component with a helpful sentence (see files 04/05) |
| **Error: API down** | Persistent top banner (Danger tint): "Can't reach the server. Retrying…" + last-updated time. Keep showing the last good data, greyed slightly. Sidebar dot turns red |
| **Error: action failed** | Inline callout next to the action with the plain reason and a retry button |
| **Partial data** | Omit the missing field. Never print `None`, `null`, `NaN`, `undefined` |

## 3. Confirmation and safety (money actions)
- Approving always requires **one explicit confirmation** showing amount, destination and reviewer name (file 04 §4).
- Rejecting requires a reason, because it is communicated to the customer and recorded.
- The primary button text states the consequence: **"Approve ₹5,000 & execute"**, never "Submit" or "OK".
- After success, show the **receipt** (refund ref) in the toast and the resolution card, so the reviewer sees proof.
- No undo (money has moved). The confirmation step is the safeguard. Say so in the dialog.
- Reviewer name is required before any action. Disabled buttons explain why via tooltip.

## 4. Microcopy rules
**Voice:** clear, calm, professional. Short sentences. Active voice. No exclamation marks, no emoji.

| Instead of | Write |
|---|---|
| `awaiting_approval` | Needs approval |
| `money_moving` | Money |
| `needs_approval (blocked by cap)` | "Above the ₹2,000 auto-approval limit" |
| `failed_debited` | "Failed, but money was debited" |
| `policy_ref required` | "No policy was cited for this action" |
| "Error 500" | "Something went wrong on our side. Try again." |
| "Success!" | "Approved. ₹5,000 reversed (RFND-T1002)." |
| "N/A" | omit, or "—" in tables |

**Always say who did what:** "Asha approved…", "The AI checked…", "The gateway blocked…".
**Amounts:** `₹5,000`, Indian grouping, no decimals unless non-zero paise.
**Times:** relative ("5m ago", "2d ago") with exact timestamp on hover, in the user's timezone (Asia/Kolkata for the demo).
**IDs:** mono, copy-on-click, never truncated in the case header.
**Plain-language translation of a failed check (examples):**
- txn not eligible → "This payment isn't eligible for reversal (status: Success)."
- txn not the customer's → "This transaction doesn't belong to this customer."
- amount > txn amount → "Requested amount is higher than the original payment."

## 5. Keyboard and efficiency
**P1 (Streamlit-feasible):** all controls reachable by Tab, visible focus ring (2px `--brand`, 2px offset), Enter activates the focused control, Esc closes dialog/drawer.
**P2 (only if built in React):** `J`/`K` next/previous case, `A` approve (opens confirm), `R` reject, `/` focus search. Show a `?` shortcut hint. In Streamlit, skip these. Do not hack them in.

## 6. Accessibility baseline
- Contrast ≥ 4.5:1 for text; ≥ 3:1 for icons/borders that carry meaning.
- **Color is never the only signal**: every chip has text; every dot has an adjacent label or tooltip.
- Chips and icons have `aria-label`s or `title`s equal to their text.
- Click targets ≥ 32px high (40px for primary actions).
- Dialogs trap focus and return it to the triggering button on close.
- Respect `prefers-reduced-motion` (disable the fade).
- Font size never below 12px; essential info never below 14px.

## 7. Responsiveness
Primary target: **laptop/desktop ≥ 1280px** (demo hardware). At 1024–1279px: the list narrows to 320px and the fact grid goes from 3 to 2 columns. Below 1024px: stack list above workspace with a "Back to list" ghost button. Mobile is out of scope, but nothing may overflow horizontally.

## 8. Privacy in the UI
- The LLM-facing data is masked (`<PHONE_1>`, `<UPI_1>`). The reviewer UI must display whatever the API returns, **never attempt to unmask or reconstruct**.
- Audit args are already masked. Show them as received, and label the section "Arguments (masked)".
- Never show the demo auth token anywhere.

## 9. Performance feel
- Selecting a case should render in < 200ms from cached data, then refresh. Cache `/customers` and `/tools` for the session.
- Fetch `/cases/{id}` for the **selected** case only. For list rows needing the amount (awaiting_approval), fetch details for those cases in a batch on each refresh (small N in the demo).
