# ResolveAI · Paytm hackathon demo

ResolveAI combines a mocked payment database, deterministic tool gateway, policy retrieval, an AI support agent, a live support dashboard and a separate two-persona judge prototype. No real Paytm payment APIs are connected.

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
| http://127.0.0.1:8010/ | Live backend-connected dashboard |
| http://127.0.0.1:8010/judges | Existing two-persona design with the 20-case judge panel open |
| http://127.0.0.1:8010/review | Review-queue sign-in for the prototype |
| http://127.0.0.1:8010/docs | Backend API documentation |

The **judge panel is scripted UI testing**, not a live AI or Paytm test. It has a Load case action, expected behavior, compatibility notes and Run 20 UI checks. Twelve cases explicitly flag missing provider integrations. It makes no real financial changes. The two-persona prototype's human takeover/return actions are simulated, not implemented as live backend ownership controls.

Reviewer login is enforced by the server for `/review/queue`, the awaiting-approval filter and approval/rejection APIs. Prototype review navigation also requires login. The server session is separate from the UI's simulated scenario state. The demo assumes trusted local access for human-agent case data; it is not production authentication for every API.

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
- `FINAL_JOINT_CHECK.md`: latest final verification and remaining limitations.
- `TWO_PERSONA_UI_PLAN.md`: previously researched proposal; not a claim that the prototype is fully backend-connected.

Secrets, SQLite files, generated policy indexes and raw query transcripts are excluded from Git. The legacy Streamlit file `ui/app.py` is retained but is not the supported entry point for this final HTML-dashboard verification.
