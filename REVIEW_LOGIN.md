# Review queue demo login

Open http://127.0.0.1:8010/review

- **Username:** `approver`
- **Password:** `DemoReview!2026`

These are intentionally shared dummy credentials for the local demo, not production credentials. The server reads the configured values from private `.env` (`REVIEWER_USERNAME`, `REVIEWER_PASSWORD`); they are not embedded in the frontend.

Selecting Review queue prompts for login. Human escalation chat remains separately accessible. Approval/rejection and the dedicated review-queue API require a server-side session. The cookie is HttpOnly and SameSite Strict, expires after one hour, and is invalidated on Sign out. Five incorrect attempts in one minute trigger a temporary rate limit.

The standalone design preview still uses sample cases and simulated decisions. Its login talks to the real local server, but its payment actions remain prototype-only. The live backend's approval/rejection endpoints are also protected. The agent-visible case history is not intended to become a separate privacy boundary from its approver colleagues.

Use individual accounts/SSO and deployment access controls before production. Do not reuse the dummy password for real customer data.
