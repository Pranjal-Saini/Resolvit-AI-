# UI and joint integration check

## Delivered

A ResolveAI support dashboard based on the supplied reference: blue navigation, light rounded workspace, four live metric cards, a case-outcome chart, recent cases, review queue and audit activity. Customer support, case review, audit and tool-registry pages are connected to the existing FastAPI endpoints. The interface is responsive, uses native labeled controls, and escapes dynamic text.

Start the application with:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. No Streamlit or frontend build process is required. See `ui/README.md` for the repeatable test workflow.

## Verification

- 16 Python regression tests pass, including database, approval, ownership, outage recovery, chat history and UI serving.
- The existing five HTTP/gateway checks pass.
- Engine self-checks, JavaScript syntax and whitespace checks pass.
- Nine deterministic UI DOM integration checks pass. They exercise real event handlers and HTTP calls against a temporary database: dashboard loading, refund, approval, protection/escalation, audit, filters, rejection validation, outage display and reconnect.
- A separate real Groq run through the UI event handlers passed the refund, high-value approval, protective action, rejection and audit flows. This uses jsdom, not a rendered browser.
- All joint tests used separate databases. The shared `backend/resolveai.db` was not reset.

## Failures found and fixed

1. **Provider outage after a successful refund:** Groq's 120B daily quota ran out after the gateway committed a refund. The agent previously reported only escalation. It now reports confirmed refunds factually from gateway data even if the final model call fails. Pending approvals retain their status during an outage.
2. **Premature high-value resolution:** the 20B model initially described a failed ₹5,000 transaction without submitting it to the gateway. A final-response guard now asks it to submit a uniquely matched failed-payment request; continued refusal escalates rather than falsely resolving the case. The gateway retains control of eligibility and amounts.
3. **Duplicate prompt content:** the backend passed the current customer message in history and separately. Only prior messages are now passed in history.
4. **Connection recovery:** Refresh reloads customers as well as dashboard data, so an initial connection failure does not leave the customer selector empty.
5. **Review visibility:** approvals and rejections append the backend's review confirmation to the open customer conversation.

## Local provider configuration

The account's Groq 120B model hit its daily token limit. The available `openai/gpt-oss-20b` model passed the live checks and is selected in the private `.env` for this machine. The local fallback is set to the already-installed `llama3.2:3b` instead of the missing `qwen3:8b`. Ollama reports tool-call support for the installed model, but this run did not validate all workflows through that fallback. No keys were added to source files or sent to the browser.

## Still to verify or add

- Browser access was unavailable. Pixel rendering, mobile layout, keyboard focus and browser-specific behavior need a real-browser pass; DOM tests do not establish those results.
- The demo uses the existing customer-token and reviewer-name contracts. Shared-key reviewer sessions and a demo contact step-up flow are now implemented and tested. They are not a production identity provider or customer-delivered OTP.
- Provider quota and model behavior still vary. The new safeguards report committed actions accurately; they do not guarantee a provider will always be available.
