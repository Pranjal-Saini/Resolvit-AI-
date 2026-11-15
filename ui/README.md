# ResolveAI staff workspaces

Buildless HTML/CSS/JavaScript served by FastAPI. `/` is a role chooser. `/login/agent` signs in to the human-support workspace at `/agent`; `/login/approver` signs in to the approver workspace at `/review`. Dummy credentials and the ready-to-show server command are in `REVIEW_LOGIN.md`.

Human support sees escalated cases, replies to customers and completes investigations. Approvers see pending exceptions, inspect relevant case evidence and approve/reject/request information. A handoff moves the case between private role-scoped queues. Completed work remains in the corresponding role's history. There is no in-dashboard role switch.

Each role uses its own server-side session and cookie. Direct API access is restricted too: case details, messages, audit/customer lists, metrics and decision actions are checked by role. Case-specific message storage prevents unrelated cases in a session from sharing private history. Unassignable historical session history is withheld. Authenticated identity supplies attribution.

Both workspaces include the twenty-case judge catalogue. These are scripted fictional examples; other-role routes are read-only and every interactive simulation is labelled. They make no payment or provider calls. The live queues are backend-connected with mock financial data; no Paytm API is connected. Legacy shared UI sources remain in the repository but are not served as alternative dashboards.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m scripts.demo_check
.venv/bin/python -m engine.test_engine
node --check ui/role-workspace.js
node --check ui/login.js
```

For DOM/HTTP checks, start a fresh isolated fixture in another terminal:

```bash
.venv/bin/python -m scripts.ui_fixture_server
```

Then run:

```bash
npm install --prefix /tmp/resolveai-ui-qa jsdom
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_ui.cjs
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_review_access.cjs
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_demo_catalog.cjs
```

Restart the fixture before rerunning the mutation workflows. It uses a temporary database and deterministic agent, so it consumes no provider tokens. DOM checks do not verify real-browser rendering, navigation, mobile layout or keyboard focus. The latest observed results and limits are in `ROLE_ACCESS_CHECK.md`.
