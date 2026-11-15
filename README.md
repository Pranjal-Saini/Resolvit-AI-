# ResolveAI backend

Requires Python 3.11 or newer. Run commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app.seed
uvicorn backend.app.main:app --reload --port 8000
```

Run `python -m scripts.check_setup` to verify the database, shared models, and
HTTP endpoints using a temporary database. It leaves your demo data untouched.

The seed command resets all local demo data; server startup only creates missing
tables and preserves existing data. The generated SQLite database is not committed.

Available endpoints:

- `GET /health` returns `{"ok": true}`.
- `GET /customers` returns demo customer IDs and names.
- `/docs` provides interactive API documentation.

Shared models are in `shared/contracts.py`, matching the frozen backend spec.
Payment tools, the gateway, chat, approvals, and dashboard endpoints are next.
Agent and UI dependencies can be appended to `requirements.txt` by their owner.
