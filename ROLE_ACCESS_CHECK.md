# Separate workspace verification · 15 November 2026

Human support and approvers now have separate login pages, credentials, session cookies, queues and actions. The server enforces the separation for direct API requests as well as the interface. No role-switch tab is present inside either workspace.

## Demo entry points

| Role | Login link | Dummy login ID | Dummy password |
|---|---|---|---|
| Human support | http://127.0.0.1:8010/login/agent | `support` | `DemoSupport!2026` |
| Approver | http://127.0.0.1:8010/login/approver | `approver` | `DemoReview!2026` |

The demo server is running with a separate database at `/private/tmp/resolveai-role-demo.db`. It contains a mock account-compromise support case and a pending ₹5,000 refund for the approver. These pre-created examples use the real gateway with mocked financial data; their setup does not call an AI provider. Existing working/presentation databases were preserved. Restarting this server preserves demo actions and requires signing in again.

## Access rules verified

- Anonymous visitors see the role chooser or a login page. Private case, audit, metric, customer and tool endpoints reject anonymous access.
- Human support sees escalated cases and its completed support cases. It can reply/resolve; it cannot list, open, approve or reject approval work.
- Approvers see approval work and its recorded decisions. They can approve/reject/request information; they cannot open unrelated escalations, send support replies or resolve support investigations.
- Case details, list filters, audits, customer lists and metrics all apply server-side role scope. Guessing another role's case ID returns 404. Forbidden role actions return 403.
- Request information transfers the case to support and removes approver access. Returning information transfers it back to the approver and removes support access. The pending approval cannot be completed through support's resolve action.
- Customer conversation context travels with an explicitly handed-off case. Unrelated cases in the same customer session do not share their private message history in staff APIs.
- The authenticated identity supplies reply and approval attribution. Supplying another name in a request cannot impersonate that user.
- Agent and approver sessions use separate HttpOnly / SameSite Strict cookies. Two tabs can remain signed in independently; signing out of one role preserves the other. Requests with both cookies must explicitly select a role for shared APIs using `X-Workspace-Role`.
- Cookies expire after one hour; HTTPS sets Secure. Five failed logins per role/IP per minute trigger the existing limit. Private responses use `Cache-Control: no-store`. Legacy shared dashboards are no longer served as alternate routes around login.

## Results

| Check | Result |
|---|---|
| Python suite, including 11 new role-isolation regressions | 42 passed |
| Controlled-agent HTTP/gateway suite | 5 passed |
| Two-interface DOM + real HTTP workflow round | 12 passed |
| Judge catalogue checks | 20 passed for each role, 40 combinations |
| Both login forms, wrong credentials, password clearing and independent sessions | Passed |
| Setup/migration preservation, engine checks and JavaScript syntax | Passed |
| Actual port-8010 links and configured dummy accounts | Passed, no payment actions taken during smoke check |

The interface round exercised automatic customer cases, support replies, private queues, forbidden cross-role API attempts, information handoff, approved refund, duplicate-approval rejection, contact approval without OTP, rejection, all judge fixtures, offline/reconnect feedback and independent sign-out. It found and fixed stale connection-error feedback while a scripted scenario was open.

The existing `/chat` contract is still the mock customer channel used by the agent/UI teammates. It uses demo customer tokens, not staff sessions; it is not production customer authentication. Staff can read only their role's case context. No live Paytm provider is integrated.

The 20 fictional judge cases are available in both dashboards. Only the current role's scenarios offer interactive controls; the remaining scenarios are read-only expected outcomes. They do not call the agent/gateway or change financial data. Twelve cases explicitly disclose provider-integration gaps. Tests check the separation, not semantic policy correctness or real Paytm compatibility.

Real browser automation was attempted, but the browser access host was unavailable. DOM tests do not establish visual rendering, mobile layout, keyboard focus or real-browser navigation behavior. The prior 15/15 live Groq and 1/3 Ollama fallback results remain documented in `FINAL_JOINT_CHECK.md`; no extra paid-provider round was used for this access change.

This is a local demonstration with one configured account per role, not an organization-wide SSO/user-management deployment. Sessions are process-local and require a single server process. The additive `case_messages` table preserves existing data; historical session-wide messages that cannot be safely assigned to a case are withheld rather than exposed across roles. Routine AI chats remain outside the human queue; this change does not implement generalized AI/human conversation ownership or a production concurrency architecture.

## Reproduce

Use the test commands in `README.md`. Start a fresh isolated fixture before `scripts/check_ui.cjs`. Run `scripts/check_review_access.cjs` for both login forms/session separation and `scripts/check_demo_catalog.cjs` for both roles' scripted scenarios. Raw transcripts, working SQLite files and `.env` remain excluded from Git.
