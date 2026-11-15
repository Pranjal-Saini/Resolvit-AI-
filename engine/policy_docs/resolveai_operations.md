# ResolveAI operating rules

> Sample policy for demo. These are ResolveAI's internal operating rules, not rules published by Paytm. They sit on top of the Paytm and RBI rules and can only narrow what the agent does, never widen it.

## Auto-reversal limit
The AI agent may trigger an automatic reversal of a failed UPI payment only when the transaction status is failed_debited and the amount equals the debited amount. Automatic reversals are limited to 2,000 rupees per transaction. For a reversal above 2,000 rupees the agent still submits the reversal request with trigger_reversal; the gateway holds it and routes it to a specialist for approval, so no money moves until a human approves.

## Specialist review
A human support specialist must approve before money moves when a reversal or refund is above 2,000 rupees; the agent submits the request and the gateway places it in the approval queue. A specialist must also handle disputes and chargebacks, repeated failures on the same transaction, any action the gateway blocks or that errors, and any case where no policy rule matches with confidence. The agent hands over a case summary and tells the customer a specialist will review it.

## Protective actions
When a customer reports a hacked or compromised account or unauthorized transactions, the agent freezes the wallet and UPI immediately, before any other step, so that no more money can leave. It then escalates the case to a human for the fraud investigation.

## Contact changes
Changing the registered phone number or email is a sensitive action. The agent submits update_contact and the gateway holds it for authenticated specialist approval. The hackathon demo does not require an OTP or verification code. Contact details must never be changed while an account compromise is being investigated.

## Follow-ups
If a refund is initiated but not yet credited, the agent schedules a follow-up to recheck the status before the RBI turnaround time ends.
