# ResolveAI: two-persona UI plan

Status: updated interactive design preview; not published to the main UI. The earlier draft-first workflow is superseded by the user's instruction that humans join only on escalation.

## Operating model

AI handles routine customer conversations and sends replies automatically. The gateway still decides whether actions are allowed. The human chat agent enters only when a conversation needs human handling. The approver is a separate persona for an escalated decision, such as a high-value refund.

Dashboard users are already authorized. No extra sign-in, access key or OTP is proposed.

## Workspace 1: escalated chats

Default: a queue of escalated conversations and one selected conversation. Routine AI chats never appear here.

Show only customer/case/status, a compact linked-payment strip, the conversation and a concise handoff reason. Policy evidence and timeline open on demand.

Flow:
1. AI responds and identifies a need for human support.
2. It posts a customer-facing handoff and adds the case to the human queue.
3. The human reads the transcript and escalation reason.
4. **Take over chat** atomically assigns the conversation to that human and pauses AI replies.
5. The human sends replies directly; they are not reviewing every routine AI response.
6. An explicit **Return to AI** releases ownership. No silent AI/human switching.

Before takeover, the transcript is read-only. Prevent simultaneous AI and human replies, duplicate takeover and stale case actions in the real implementation.

## Workspace 2: review queue

Show one decision at a time, with six facts: customer/case, issue, payment facts, requested action, reason for review and relevant policy.

- **Approve**: gateway revalidates and executes; AI automatically sends only the confirmed outcome. This does not require a chat-agent review.
- **Reject**: record reason and let AI notify the customer accurately.
- **Request information**: send a note to the human chat queue; the human takes over to collect the missing information.

An approval exception does not automatically need human chat takeover. Fraud investigation or uncertainty can need a human conversation without any executable payment approval. Keep these routes distinct.

## Example demo

- The AI has responded to Priya about an unauthorized payment, confirmed a wallet freeze and escalated investigation. The human sees only this escalated chat and takes over.
- Rahul's failed ₹5,000 payment is held above the ₹2,000 auto limit. It appears in Review queue, not the human chat queue.
- Approval confirms the refund and AI sends the result automatically.
- Alternatively, Request information moves Rahul into the human queue with the reviewer's note.

## Data reduction

Only two navigation entries. Remove global metrics, charts, activity feeds, tool registry and customer-simulator controls from the operational workspace. Keep case evidence in contextual drawers. Payment state and conversation state remain distinct.

## Implementation prerequisites

This preview is illustrative and has no API calls. Before promoting it:

- Retain the real AI auto-response flow for routine conversations; do not implement the superseded read-only draft/send workflow.
- Persist handling ownership (`AI`, `waiting for human`, `human handling`) separately from case resolution/approval status. Existing case status alone does not establish who can send.
- Add transactional takeover/return endpoints. Reject AI sends while a human owns the case and reject human sends before takeover.
- Build a queue endpoint that returns only cases needing human conversation support, with a structured handoff reason. An `awaiting_approval` case alone must not imply chat takeover.
- Add request-information notes and routing from approver to human queue.
- After approval/rejection, send an authoritative AI/system outcome once. Use committed gateway facts; a model outage must not hide a refund or create a second one.
- Link messages to cases and identify customer, AI, human and internal messages.
- Refresh queue/ownership/decisions across both workspaces without invoking the model for polling.
- Preserve gateway cap, ownership, citation checks, masking and duplicate protection.

## Acceptance criteria

Routine AI-resolved chats are absent from the human queue. The transcript and handoff reason are available before takeover. Only one human can take over; AI stays paused until return. Approver approval does not require a human to resend the AI outcome. Information requests create a human queue item with context. Failed actions never produce a success message. Duplicate approval or notification cannot repeat financial execution.

## Research basis

[Intercom Inbox](https://www.intercom.com/helpdesk/inbox) and its [conversation documentation](https://www.intercom.com/help/en/articles/6433002-start-a-conversation-from-the-inbox) support a conversation-centered workspace. [Zendesk approvals](https://support.zendesk.com/hc/en-us/articles/8481193191322-Responding-to-approval-requests-as-an-agent) show dedicated decision work with approval, denial and information requests. [NN/g progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) supports keeping secondary evidence out of the default view. The specific escalation-only workflow is the user's requirement, not a claim drawn from those sources.

## Verification limit

Prototype interaction checks cover escalation filtering, takeover, paused AI, human reply, separate approval, automatic outcome notification, request-information handoff and return to AI. They use jsdom, not a rendered browser. Production ownership synchronization and live backend integration are not implemented by this preview.
