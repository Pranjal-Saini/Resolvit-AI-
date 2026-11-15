# Paytm UPI: failed and pending transactions

Sources (paraphrased for retrieval, last checked 2026-11-15):
- Paytm Help, "Steps for resolving failed or pending UPI transactions": https://paytm.com/support/upi/steps-for-resolving-failed-or-pending-upi-transactions
- Paytm Help, "Payments and refunds on Paytm": https://paytm.com/support/payments/payments-and-refunds-on-paytm-key-things-to-know
- RBI, "Harmonisation of Turn Around Time (TAT) and customer compensation for failed transactions using authorised Payment Systems" (20 Sep 2019): https://rbi.org.in/commonman/English/scripts/Notification.aspx?Id=3074
- Paytm Blog, "UPI Transaction: Features, Benefits, Maximum Limit": https://paytm.com/blog/payments/upi/upi-transaction-features-benefits-maximum-limit

## Debited but not credited
If a UPI payment fails but the money is debited from the customer's bank account, it is a failed transaction. A failed transaction is one that was not fully completed for reasons not attributable to the customer, including a credit that could not be made because of missing or incomplete information. Paytm keeps tracking the refund until it is completed. In most cases the customer does not need to take any manual action.

## Refunds
For a failed transaction where money was debited, the refund is triggered automatically as soon as the transaction is marked failed. The refund goes back to the original source: bank account, card or UPI. Paytm initiates the refund within minutes or hours. The credit usually reflects in the source account in 3 to 5 business days, and can take up to 7 bank working days depending on the bank. The customer should not retry the same payment while a refund is pending, because retrying can debit them twice.

## Auto-reversal timelines
Under the RBI harmonised TAT rules, T is the calendar date of the transaction. For a UPI fund transfer where the customer is debited but the beneficiary account is not credited, the amount must be auto-reversed by T+1 day. For a UPI merchant payment where the account is debited but the merchant did not receive confirmation, auto-reversal must happen within T+5 days. The TAT is an outer limit. Failed transactions should be resolved sooner wherever possible.

## Compensation for delay
If a failed UPI transaction is not reversed within the TAT, the customer is paid compensation of 100 rupees for every day of delay beyond T+1 day for fund transfers, or beyond T+5 days for merchant payments. Compensation must be credited to the customer's account automatically, without the customer having to complain or claim it.

## Pending transactions
A pending UPI transaction usually resolves on its own. The customer should wait at least 30 minutes, and most pending payments settle within a few hours. The customer should not pay again while a transaction is pending, because this can create a duplicate payment. The status in order history usually updates automatically.

## UPI transaction limits
Regular UPI payments through Paytm are limited to 1 lakh rupees per day and a maximum of 20 UPI transactions per day. Individual banks can set lower limits. IPO and RBI Retail Direct payments have a higher limit of 5 lakh rupees per transaction.

## Raising a complaint
If a refund for a failed transaction has not arrived after 7 working days, the customer should raise a ticket from that transaction in the Paytm app using 24x7 Help, giving the transaction ID and amount. If the issue is not redressed within the TAT, the customer may complain under the RBI Integrated Ombudsman Scheme, 2021.
