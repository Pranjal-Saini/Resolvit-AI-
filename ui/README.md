# ResolveAI support workspace

A buildless HTML/CSS/JavaScript dashboard served by the existing FastAPI application. The visual reference is adapted into a blue navigation rail, light workspace, metric cards, case-outcome chart and review/activity column. Every metric comes from the backend; no synthetic activity or growth percentages are displayed.

## Run

From the repository root:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. UI and API share an origin; there is no frontend build or second server. Keep provider configuration in the ignored `.env` file. Initialize the schema with `db.init_db()`; only run `python -m backend.app.seed` when intentionally resetting demo activity.

## Flows

- Overview: live case counts, automatic-resolution rate, outcomes, pending reviews and recent audit events.
- Customer support: choose any of the ten customers, start a conversation, or fill a demo scenario. Messages are sent only when you press Send. Actions, policy citations and current case details are inspectable.
- Cases & approvals: filter cases, inspect conversations and audit records, approve or reject pending requests. Rejection requires a reviewer and reason. Support review messages are reflected in the customer conversation.
- Audit trail: inspect real gateway decisions and filter by case.
- Tool registry: inspect the seven tools and their input requirements.

No API keys are sent to the browser. Customer identity uses the existing demo-token API contract. This is a hackathon demo; reviewer actions require a one-hour shared-key session. Contact changes additionally require the demo step-up code. This demonstrates the workflow; it is not production identity verification.

## Joint regression checks

Python/API checks:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m scripts.demo_check
.venv/bin/python -m engine.test_engine
node --check ui/app.js
```

UI DOM checks use jsdom and an isolated backend, not a rendered browser:

```bash
# Terminal 1: a fresh temporary database and deterministic agent; no API charges.
.venv/bin/python -m scripts.ui_fixture_server

# Terminal 2: test-only dependency kept outside the repository.
npm install --prefix /tmp/resolveai-ui-qa jsdom
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_ui.cjs
```

Restart the fixture server before rerunning; the check expects a fresh seed. `UI_TEST_BASE` can explicitly target another isolated server for a real-agent run. These checks execute real UI event handlers, API requests and database mutations, but do not verify pixel rendering, mobile layout or browser-specific behavior.

## Reviewer controls

Set `REVIEWER_ACCESS_KEY` and `DEMO_STEP_UP_CODE` in the private `.env` file. The local setup has generated these values there. Enter the reviewer name and access key in a case's review form. For contact changes, enter the verification code before approving. The server rejects unsigned reviews, mismatched session names and contact changes during account compromise. Neither secret is embedded in JavaScript.

The demo verification code is a server-configured test factor, not a delivered customer OTP. Production needs individual reviewer accounts and a customer-bound verification channel.
