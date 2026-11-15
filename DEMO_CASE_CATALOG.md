# Twenty-case UI demo catalogue

Open http://127.0.0.1:8010/judges and choose a role, or sign in at `/login/agent` or `/login/approver` and choose **Demo cases · 20**. Credentials are in `REVIEW_LOGIN.md`.

This panel contains isolated, scripted examples inside each authenticated workspace. It does not call the real agent, execute gateway actions, connect to Paytm or mutate a database. Its checks establish role-specific controls and presentation, not policy-engine or Paytm API compatibility. The live queue is separate and backend-connected.

## Use during the presentation

1. Filter a category and inspect the customer query, expected behavior and integration scope.
2. Select **Try this scenario** for a route belonging to your role, or **View expected outcome** for a read-only observation. Routine AI cases never enter either private staff queue.
3. Human-support accounts can simulate replies for human scenarios. Approver accounts can simulate approval, rejection or information requests for review scenarios. Simulated handoffs do not open the other person's workspace.
4. Use **Run 20 UI checks** to verify the displayed fixture routes. A passed UI check can still carry a backend integration gap.
5. Select **Return to live queue** to leave the fixture and view your real role-scoped cases.

## Catalogue

| # | Customer condition | Expected route |
|---|---|---|
| 01 | Failed ₹499 UPI payment | AI mock reversal |
| 02 | Failed ₹5,000 payment | Approver |
| 03 | Failed payment exactly ₹2,000 | AI; demo-cap boundary |
| 04 | Failed payment ₹2,001 | Approver; never round down |
| 05 | Pending ₹1,500 transfer | AI pending-state answer |
| 06 | Successful payment disputed by merchant | Human investigation |
| 07 | Already reversed recharge requested again | AI; no second refund |
| 08 | Transfer to wrong UPI recipient | Human; no promised recovery |
| 09 | Unauthorized wallet payment | Mock freeze then human investigation |
| 10 | Unclear failed-payment complaint | AI asks for clarification |
| 11 | Failed prepaid recharge | AI mock failed-debit response |
| 12 | Successful recharge without benefit | Human fulfilment investigation |
| 13 | Pending DTH recharge | AI pending-state answer |
| 14 | Pending electricity bill / repeat-payment question | AI; avoid duplicate payment |
| 15 | Duplicate successful water-bill payments | Human compares payment evidence |
| 16 | Failed broadband bill payment | AI mock failed-debit response |
| 17 | Failed wallet merchant payment | AI mock wallet credit |
| 18 | Successful gift-voucher payment without delivery | Human issuance investigation |
| 19 | Registered contact change | Approver; no OTP/access key |
| 20 | Contact-change request during compromise | Mock freeze, block change, human handoff |

## Verification result

All 20 scripted cases passed DOM checks for each role (40 role/scenario combinations). Assertions cover role-specific controls, category filtering, contact changes, compromise blocking, and zero scenario network side effects. Separate HTTP/UI tests verify live information handoff and gateway actions. These tests use jsdom and do not establish pixel rendering or mobile/browser behavior.

Run:

```bash
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_demo_catalog.cjs
```

If jsdom is not already installed, install it as a test-only dependency outside the project with `npm install --prefix /tmp/resolveai-ui-qa jsdom`.

## Paytm compatibility boundaries

The ₹2,000 cap is this hackathon's internal demo rule, not a claim about Paytm's refund policy. Mock wallet credits do not establish where a real provider refund should go. Real refund destination/status must be supplied by the provider.

Twelve catalogue cases explicitly flag missing integrations or data: durable rechecks, merchant settlement, wrong-recipient recovery, actual bank/UPI blocking, telecom/DTH/broadband fulfilment, biller reconciliation, duplicate bill matching, voucher issuance and identity recovery. The selected cases explain the specific gap. Two boundary fixtures and several example disputes are catalogue-only records, not transactions in the seeded backend.

These synthetic scenarios use the three requested business areas. Official Paytm support documents ground the UPI issue categories—failed/pending payments, debited-not-credited payments, incorrect transfers and complaints—but do not certify this UI or its scripted outcomes:

- [Paytm UPI support](https://paytm.com/support/upi)
- [Paytm UPI payment failures and refunds](https://paytm.com/support/upi/upi-transaction-failed-on-paytm-fixes-refund)
- [Raising a UPI complaint](https://paytm.com/support/upi/how-to-raise-upi-complaint-paytm)

No live Paytm credentials, merchant API, bank reconciliation or real money movement have been used in this catalogue.
