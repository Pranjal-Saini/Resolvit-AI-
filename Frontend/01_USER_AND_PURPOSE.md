# 01: The User, Their Purpose, and Why Each Screen Exists

## 1. What the product does (the context the UI sits in)
A customer chats about a Paytm-style payment problem. An AI agent investigates with read-only tools, cites a policy rule (RAG), and acts through a **tool gateway** that enforces risk tiers, caps and eligibility in plain Python. The AI resolves what it safely can. When something exceeds a limit or needs judgment, the gateway creates an **approval** and the case lands with a human.

So the helpdesk professional is **not** answering chats. They are the **human-in-the-loop**: the final authority on the small share of cases the AI is not allowed to finish alone.

## 2. The user: "Asha", the support reviewer
| | |
|---|---|
| Role | Support agent / team lead at a payments company |
| Context | Several cases waiting, often interrupted, works inside a ticket queue all day |
| Mindset | Wants to clear the queue accurately and fast. Afraid of two things: approving something wrong (money lost) and rejecting something right (angry customer) |
| Tech comfort | Comfortable with ticketing tools (Zendesk-style). Not an engineer. Does not know what a "tier" or "idempotency key" is |
| Trust issue | Does not yet trust the AI. Needs to *see* what it did before putting her name on a decision |

### Her jobs-to-be-done
1. **Triage:** "What needs me right now, and what's most urgent?"
2. **Decide:** "Is this refund legitimate? Can I approve it safely?"
3. **Understand without asking:** "What did the customer want, what did the AI check, and what's missing?" She must never have to re-ask the customer.
4. **Act:** approve (the system executes the action) or reject with a reason the customer sees politely.
5. **Prove:** when a manager or auditor asks "what did the AI do on this case, and was it allowed?", she answers in seconds.
6. **Stay confident:** see that the AI is working (resolution rate), so she knows her queue is only the hard cases.

## 3. What she needs (and the screen that gives it)
| Need | Why it matters | Provided by |
|---|---|---|
| See at a glance how many cases need a human, oldest first | Triage speed, SLA | **Review Queue** + sidebar badge |
| One-sentence reason a case reached her | Avoid reading anything extra | **Decision card** ("Over the ₹2,000 limit by ₹3,000") |
| The exact action, amount, target, customer | Prevent mistakes on money | **Decision card** |
| The AI's summary and the policy it relied on | Trust and defensibility | **Case summary** + **Policy citation** |
| What the AI already checked and did | No duplicate work, no re-asking | **Evidence timeline** |
| Approve / reject in one clear step | Speed with safety | **Action bar** + one confirmation |
| Proof that every action was governed | Compliance, demo "wow" | **Audit viewer** |
| Proof the AI is doing the bulk of the work | Business value | **Overview** (auto-resolution rate) |
| Know which tools the AI can use and its limits | Transparency for managers | **Tool registry viewer** |

## 4. Why these screens, and in what priority
The PRD's demo goals are G1–G4. Each one maps to a UI moment:

| Goal | What the audience must see | UI moment |
|---|---|---|
| G1: auto-resolve under cap | The AI did it alone, with a citation | Case in Resolved state + audit trail rows (executed, with policy ref) |
| G2: escalate over cap | A human is asked, approves, action runs | Queue → Decision card → Approve → success receipt |
| G3: protective freeze | AI acts first on fraud, then flags a human | Escalated case with "wallet frozen" action in the timeline |
| G4: visible governance | Tier, decision, policy_ref for every call | Audit viewer |

**Therefore the product is the Review Console, not a generic admin panel.** Build the queue-and-decision experience first and make it excellent. Everything else supports it.

## 5. What we deliberately will NOT build, and why
- **A chat client for the reviewer.** The reviewer decides on evidence. Typing to customers is out of scope and not supported by the API.
- **A YAML tool editor.** The PRD scopes this to a read-only viewer. Editing is a pitch-deck roadmap item.
- **Charts for their own sake.** The metrics API gives five numbers. Show those well instead of inventing trends.
- **Notifications, assignment, SLAs, comments.** Real helpdesk features, but not supported by the contracts. Show age on cases, nothing more.

## 6. Experience goals (the feeling)
- **Calm and in control**, not an alarm panel. Most of the time the queue is short or empty, and that is a *good* state we should celebrate ("All clear. The AI handled everything else").
- **Credible**, with data-dense but quiet detail like a Stripe or Linear dashboard.
- **Fast.** Selecting a case never navigates away. The list and the workspace are side by side.
