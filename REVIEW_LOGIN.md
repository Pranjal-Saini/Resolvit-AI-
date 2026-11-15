# Demo workspace logins

| Role | Login link | Login ID | Password |
|---|---|---|---|
| Human support | http://127.0.0.1:8010/login/agent | `support` | `DemoSupport!2026` |
| Approver | http://127.0.0.1:8010/login/approver | `approver` | `DemoReview!2026` |

These intentionally shared dummy accounts are for the local hackathon demo. The server reads `AGENT_USERNAME` / `AGENT_PASSWORD` and `REVIEWER_USERNAME` / `REVIEWER_PASSWORD` from the private `.env`; credentials are not embedded in the frontend. `.env.example` leaves these values blank for a fresh checkout.

Support signs in to `/agent`, with escalated chats and completed support work. Approvers sign in to `/review`, with pending approvals and recorded decisions. Each account can enter only its assigned workspace; there is no role-switch control inside either dashboard. Direct API requests also enforce the role. An explicit information handoff shares the relevant case with the receiving team and removes it from the sending team's queue.

You can demonstrate both accounts in two tabs: separate HttpOnly/SameSite Strict cookies prevent login or sign-out from replacing the other role's session. Sessions expire after one hour and are cleared when the server restarts. Five bad logins per role/IP per minute trigger a temporary limit. HTTPS adds Secure to the cookie.

After signing in, choose **Demo cases · 20**. All 20 fictional queries are available; interactive actions are limited to your role and other routes are read-only. These scripted fixtures never execute financial actions. The live queue below them uses the actual backend with mock payment data.

Start the ready-to-show local examples with:

```bash
RESOLVEAI_DEMO_DB=/tmp/resolveai-role-demo.db .venv/bin/python -m scripts.role_demo_server
```

Only a new file is seeded; existing demo activity is preserved. Stop any other server on port 8010 before running this command. No OTP is required. This single-process demo does not provide production SSO, account provisioning or real customer authentication. See `ROLE_ACCESS_CHECK.md` for verification and boundaries.
