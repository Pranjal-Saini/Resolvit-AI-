# Resolvit.ai Helpdesk Console: Design Pack (Index)

> **For the AI building the UI:** read the files in the order below. Together they are your complete design spec. Build only the **helpdesk professional's dashboard**. Do not change any backend contract (PRD §6 is frozen). Where this pack needs data the API does not give you, it says so and names a fallback.

## What we are designing
The **Review Console**: the one screen set where a human support professional sees what the AI could not finish on its own, decides quickly and with confidence, and can prove that the AI stayed inside its limits.

**One-line design thesis:** *The AI does the work. The human only makes the calls that matter. The console exists to make each call fast, informed and defensible.*

## Reading order
| # | File | Answers |
|---|---|---|
| 00 | `00_DESIGN_INDEX.md` | This file. Principles, build order, naming |
| 01 | `01_USER_AND_PURPOSE.md` | Who the user is, what they need, why each screen exists |
| 02 | `02_INFORMATION_ARCHITECTURE.md` | Screens, navigation, priority (P0/P1/P2) |
| 03 | `03_DESIGN_SYSTEM.md` | Colors, type, spacing, components, status language |
| 04 | `04_SCREEN_REVIEW_QUEUE_AND_CASE.md` | The core screen: queue + case workspace + approve/reject |
| 05 | `05_SCREENS_AUDIT_OVERVIEW_TOOLS.md` | Audit viewer, Overview, Tool registry, customer chat (demo only) |
| 06 | `06_INTERACTION_AND_CONTENT.md` | States, feedback, microcopy, accessibility, live updates |
| 07 | `07_STREAMLIT_IMPLEMENTATION.md` | How to build all of this in Streamlit, API-to-UI mapping, data gaps |
| 08 | `08_DEMO_FLOW_AND_ACCEPTANCE.md` | Demo script (G1–G4), acceptance checklist, build order by hour |

## Five design principles (apply to every decision)
1. **Decision first.** The first thing on any case is the decision to make and the facts needed to make it. History comes second.
2. **Show your working.** Every AI action shows what it did, why (policy citation) and what the gateway decided. Trust comes from evidence, not claims.
3. **Calm by default, loud only when it matters.** Mostly neutral. Orange appears only when a human is needed. Red only for blocked or failed. Never decorate with color.
4. **Zero re-asking.** The human never has to read a chat transcript to understand a case. The summary and the evidence are already there.
5. **Safe to act.** Money actions are explicit, show the exact amount and target, and are confirmed once. Nothing destructive happens on a single accidental click.

## Success criteria for the UI (what "great" means here)
- A new reviewer understands the queue in **under 5 seconds** and can approve a case in **under 20 seconds** (open → decide → done).
- A judge watching the demo can **see governance**: tier, cap, decision, policy reference, on one screen, without explanation.
- Nothing on screen needs a manual to understand. Jargon (`money_moving`, `idempotency`) is translated for the primary views and visible only in detail views.

## Naming
The PRD calls the product **ResolveAI**. The pitch deck calls it **Resolvit.ai**. The console UI should show **Resolvit.ai** (the deck is what judges see). Put the product name in one config constant (`PRODUCT_NAME`) so it can be changed in one place. Do not rename any code, API or file.

## Out of scope for this pack
Marketing pages, customer-facing chat polish (a minimal demo chat is in file 05), mobile layout, dark mode, real authentication, a YAML editor (the PRD says read-only viewer), and anything C++/Postgres/Redis.
