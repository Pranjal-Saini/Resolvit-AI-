# ResolveAI · Paytm hackathon demo

ResolveAI combines a mocked payment database, deterministic tool gateway, policy retrieval and an AI support agent with separate, authenticated human-support and approver workspaces. No real Paytm payment APIs are connected.

## Local setup

Requires Python 3.11+ and commands run from the repository root. This checkout was tested with its existing Python 3.15 virtual environment; other platforms have not been certified.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On a fresh checkout, copy `.env.example` to `.env` and configure:

- `GROQ_API_KEY`: required for live Groq conversations; never commit it.
- `GROQ_MODEL`: the model available to your account. The local tested configuration uses `openai/gpt-oss-20b`.
- `OLLAMA_MODEL` / `OLLAMA_BASE_URL`: optional local fallback. The tested `llama3.2:3b` fallback did not reliably complete payment workflows; it is not a guaranteed demo substitute.
- `REVIEWER_USERNAME=approver` and `REVIEWER_PASSWORD=DemoReview!2026`: intentionally shared dummy credentials for the local judge demonstration only.
- `AGENT_USERNAME=support` and `AGENT_PASSWORD=DemoSupport!2026`: a separate dummy human-support account. Each account can enter only its own workspace.

Create fresh demo data only when intentionally starting or resetting a database:

```bash
python -m backend.app.seed
```

This clears existing demo conversations, cases, approvals and audit records. Normal server startup creates missing tables and preserves existing records.

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

## Entry points

| URL | Purpose |
|---|---|
| http://127.0.0.1:8010/ | Choose a role and sign in |
| http://127.0.0.1:8010/login/agent | Human-support sign-in → private escalation workspace |
| http://127.0.0.1:8010/login/approver | Approver sign-in → private review workspace |
| http://127.0.0.1:8010/judges?role=agent | Support sign-in, then open the 20-case panel |
| http://127.0.0.1:8010/judges?role=approver | Approver sign-in, then open the 20-case panel |
| http://127.0.0.1:8010/docs | Backend API documentation |

For a presentation with a pre-created support case and a ₹5,000 approval case, use a separate dedicated database:

```bash
RESOLVEAI_DEMO_DB=/tmp/resolveai-role-demo.db python -m scripts.role_demo_server
```

It seeds only a new file and preserves its activity on restart. Do not run two servers on port 8010 at once. This does not reset `backend/resolveai.db`.

The live queues and actions are backend-connected. Support can reply to escalated cases and complete investigations; approvers can approve/reject or request information. Handoff moves the case between role-scoped queues. Each role has its own HttpOnly session cookie, so separate tabs can stay signed in independently. Case lists, details, customer lists, metrics and audits are scoped by the server. Private case history is stored per case; older session-wide history is not exposed across roles.

The **20-case judge panel is scripted UI testing**, not a live AI or Paytm test. Interactive controls are restricted to the signed-in role; other routes are read-only fictional observations. Twelve scenarios flag provider-integration gaps. These fixtures never mutate a database. Routine AI chats stay outside both staff queues; the customer layer continues to use `/chat` with the existing demo-token contract.

## Automated checks

Using the installed project environment:

```bash
python -m unittest discover -s tests -v
python -m scripts.demo_check
python -m engine.test_engine
```

For UI DOM tests, use a fresh isolated fixture server. It seeds a temporary database and uses a deterministic agent; no provider tokens are consumed:

```bash
# Terminal 1
python -m scripts.ui_fixture_server

# Terminal 2: jsdom is test-only, not a runtime dependency
npm install --prefix /tmp/resolveai-ui-qa jsdom
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_ui.cjs
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_review_access.cjs
NODE_PATH=/tmp/resolveai-ui-qa/node_modules node scripts/check_demo_catalog.cjs
```

Restart the fixture server before rerunning `check_ui.cjs`, which expects fresh data. Browser rendering, responsive behavior and keyboard focus are not established by DOM tests.

## Documentation

- `DEMO.md`: presenter flow for the live payment/approval demonstration.
- `DEMO_CASE_CATALOG.md`: 20 judge scenarios and explicit integration gaps.
- `REVIEW_LOGIN.md`: dummy sign-in and session behavior.
- `ROLE_ACCESS_CHECK.md`: latest role-isolation verification and boundaries.
- `FINAL_JOINT_CHECK.md`: preceding engine verification, including the 15 live Groq conditions and fallback limitations.
- `TWO_PERSONA_UI_PLAN.md`: historical design proposal; the login/workspace behavior is now described above.

Secrets, SQLite files, generated policy indexes and raw query transcripts are excluded from Git. Legacy HTML/prototype and Streamlit sources are retained but are not publicly served as alternate dashboards. This local demo uses one configured account per role and process-local sessions; it is not a production identity provider. Restarting the server expires logins.
