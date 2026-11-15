# 08: Demo Flow, Build Order and Acceptance Checklist

## 1. The 3-minute demo story (what the UI must support)
Narrate the **user**, not the tech. The judge should feel like they are the helpdesk professional.

| # | Scene (≈time) | On screen | What the audience should think |
|---|---|---|---|
| 1 | **Setup** (15s) | Console, Queue empty: "All clear" | "Calm, nothing is on fire" |
| 2 | **G1: AI resolves alone** (40s) | Customer chat: "₹499 got debited for my electricity bill but it failed" → AI reply with receipt + policy chip. Switch to Queue → Resolved tab → case shows "Resolved automatically" + timeline | "The AI did real work and cited a rule" |
| 3 | **G2: human in the loop** (60s) | Chat: "₹5000 flight booking failed" → "sent to a specialist". Queue badge flips to **1**, toast appears, case auto-selected → Decision card ("₹3,000 above limit"), checks, summary, policy → **Approve ₹5,000 & execute** → confirm → success toast + receipt → Resolved | "Fast, clear, safe, I never re-asked the customer" |
| 4 | **G3: protect first** (30s) | Chat as Priya: "someone hacked my account" → Escalated case: timeline shows wallet frozen first, escalation card | "It acts to protect, then hands off" |
| 5 | **G4: prove it** (35s) | Audit page: filter "Needs approval" → show rows with tier, decision, policy ref; open drawer on the reversal | "Everything is governed and traceable" |
| 6 | **Value** (15s) | Overview: AI resolution rate hero | "This reduces cost per ticket" |
| 7 | **Roadmap** (10s) | Tools page: tiers and limits | "A new client is a new YAML file" |

**Demo-reliability rules for the UI**
- Pre-seed with `python -m backend.app.seed`, and re-seed before every run.
- Keep the Queue and the Customer chat open in **two browser windows side by side**. The Queue updates itself (5s polling), so no manual refresh on stage.
- Set the reviewer name to a real-looking name before the demo ("Asha").
- Record a **backup video** at the 3:30 freeze (PRD).

## 2. Build order (matches the PRD timeline; Agent + UI workstream)
| Window | Build | Priority |
|---|---|---|
| 0:00–0:30 | `theme.py` + `inject_css()`, `.streamlit/config.toml`, `format.py`, `api.py` with `USE_MOCK` | P0 |
| 0:30–1:45 | `components.py`: chip, stat_tile, case_row, fact_grid, check_item, timeline_item, policy_callout, empty_state (build and eyeball with mock data on a scratch page) | P0 |
| 1:45–2:15 | **Queue page**: status strip, list, decision card, approve dialog, reject panel, tabs (Timeline / Conversation / Audit) · **Audit page** · **Customer chat** (minimal) | P0 |
| 2:15–2:45 | Integration with the real backend (G1 end-to-end). Fix field-shape mismatches only in `api.py` | P0 |
| 2:45–3:30 | G2 approve path polish, Escalated and Resolved cards, live polling + toasts, **Overview**, **Tools**, citations on chat | P1 / P2 |
| 3:30–4:00 | **Freeze.** Only bug fixes. Rehearse. Record backup | |

**Cut line if time is short:** drop Tools, then Overview, then the audit drawer (keep the table). **Never cut:** decision card, approve confirmation, audit table, the sidebar badge.

## 3. Acceptance checklist (the AI builder must self-verify)

### Functional
- [ ] Queue lands on the oldest `awaiting_approval` case, auto-selected.
- [ ] Decision card shows exact amount, customer, transaction id, the reason it needs a human, and the policy reference.
- [ ] Approve opens a confirmation containing amount, destination and reviewer; on success shows the refund ref and moves the case to Resolved; the next waiting case is selected.
- [ ] Reject requires a reason and updates the case to Rejected.
- [ ] Approve/reject are disabled until a reviewer name is entered, with an explanatory tooltip.
- [ ] Escalated cases show an Escalation card and **no** approve/reject buttons.
- [ ] Resolved cases (auto and human) show the correct resolution card.
- [ ] Audit page lists all rows with Time, Case, Actor, Tool, Tier, Decision, Policy; filters work; row click shows detail; missing-policy money actions are flagged.
- [ ] Overview shows the rate (or "—" when no cases), four tiles, status bar and "needs you now".
- [ ] Tools page groups tools by tier with plain-language guardrails.
- [ ] Sidebar badge shows live count of cases needing approval; "Live/Offline" indicator works.
- [ ] Data refreshes every 5s without losing selection, tab, or typed text.

### Quality
- [ ] No raw enum values (`awaiting_approval`, `money_moving`) in primary UI.
- [ ] No `None`/`null`/`NaN` ever rendered. Missing data is omitted or shown as "—".
- [ ] All amounts formatted `₹` with Indian grouping.
- [ ] All LLM-sourced text is HTML-escaped.
- [ ] Loading, empty, and error states exist for every region (file 06 §2).
- [ ] Only one accent color (orange) used for "attention"; color is never the sole signal.
- [ ] Stopping the backend shows the offline banner and keeps last good data. Restarting recovers without a page reload.
- [ ] A fresh reviewer can find and approve the over-cap case in **under 20 seconds** without instructions (test on a teammate).

### Contract safety
- [ ] No changes outside `ui/`. No contract/endpoint/field renamed.
- [ ] Every call uses the documented paths and bodies (`/cases/{id}/approve` with `{"reviewer": ...}`, `/cases/{id}/reject` with `{"reviewer": ..., "note": ...}`).
- [ ] UI never unmasks PII or displays the auth token.

## 4. Questions to raise with the team (before building, don't assume)
1. Does `/cases/{id}`'s `pending_approval` include `args_json` parsed or as a string? (Handle both.)
2. Can the backend include `payee` and `created_at` of the transaction in the approval's `args_json` or the case `summary`? It would make the decision card richer. *Optional, as the UI works without it.*
3. Will a human "Mark handled" for escalated cases be needed? It requires a new endpoint, so it needs a team decision (contracts are frozen).
4. Final product name in UI: **Resolvit.ai** (deck) or **ResolveAI** (PRD)?
