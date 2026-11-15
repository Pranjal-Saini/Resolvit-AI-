# 07: Streamlit Implementation Guide

The PRD specifies **Streamlit** for the hackathon (the deck lists React/TypeScript as the production path). Everything in files 00–06 is designed to be buildable in Streamlit **without looking like Streamlit**. This file says how.

> Scope reminder: the UI workstream edits only `ui/`. Do not touch `backend/` or `shared/`.

## 1. Requirements
- Streamlit **≥ 1.37** (needs `st.fragment(run_every=...)`, `st.dialog`, `st.navigation`/`st.Page`, `st.dataframe(column_config=...)`).
- `requests` for the API. No other UI libraries required. (No custom JS components. Too risky for 4 hours.)

## 2. File structure (inside `ui/`)
```
ui/
  app.py                 # entrypoint: page config, theme injection, sidebar, navigation
  theme.py               # tokens (colors, spacing) + inject_css()
  components.py          # chip, stat_tile, case_row, decision_card, fact_grid,
                         # check_item, timeline_item, policy_callout, empty_state
  api.py                 # all HTTP calls + response normalisation + caching
  format.py              # inr(), rel_time(), mask-safe getters, label maps
  pages/
    1_Queue.py
    2_Audit.py
    3_Overview.py
    4_Tools.py
    5_Customer_Chat.py
```
Keep `app.py` as the single entrypoint (`streamlit run ui/app.py`). Use `st.navigation([...])` with `st.Page` for the ordered sidebar so the order is Queue, Audit, Overview, Tools, Customer chat.

## 3. Page setup
```python
st.set_page_config(page_title="Resolvit.ai Console", page_icon=None, layout="wide",
                   initial_sidebar_state="expanded")
```
Hide default chrome via CSS (see §4): the Streamlit header/footer/menu.

## 4. Theming (this is what makes it look professional)
1. `.streamlit/config.toml` for the base:
```toml
[theme]
base = "light"
primaryColor = "#4A3C8C"
backgroundColor = "#F6F7F9"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#0F1222"
font = "sans serif"
```
2. `theme.inject_css()` injects one `<style>` block with `st.markdown(..., unsafe_allow_html=True)` containing:
   - CSS variables from file 03 on `:root`.
   - Google Font `Inter` import.
   - Hide `#MainMenu`, `footer`, `header[data-testid="stHeader"]`.
   - Page padding: `.block-container { padding: 24px 32px 48px; max-width: 1400px; }`.
   - Sidebar: background `--sidebar`, text `--sidebar-text`; style nav links (selected = white text on `rgba(255,255,255,.08)`, 8px radius).
   - Primary button style (`button[kind="primary"]` → `--brand`), secondary (`kind="secondary"`) with the border style from file 03.
   - Card class `.rv-card` (white, 1px border, 12px radius, 16–20 padding), `.rv-card--attention` (3px orange top border), `.rv-chip`, `.rv-chip--success` etc., `.rv-mono`, `.rv-caption`.
   - Tabs (`.stTabs`) underline style in brand color.
3. Call `inject_css()` at the top of **every page** (Streamlit reruns pages independently).

## 5. Building the components
- **Chips, cards, fact grids, timeline items, callouts** → render with `st.markdown(html, unsafe_allow_html=True)` from functions in `components.py`. All text interpolated into HTML **must be escaped** (`html.escape`), because summaries and messages come from an LLM.
- **Buttons and inputs** → native `st.button`, `st.text_input`, `st.text_area`, `st.tabs`, `st.columns`. Don't fake them in HTML.
- **Case list rows**: use `st.container(border=False)` + one HTML row + one invisible-style `st.button("Open", key=f"open_{id}")` per row. **Better:** use `st.button` with the full label formatted as markdown (`use_container_width=True`, `type="secondary"`) and CSS to make it look like a row; selected row gets `type="primary"` styled as brand-tint. Selection stored in `st.session_state.selected_case_id`.
- **Confirm dialog** → `@st.dialog("Confirm approval")` function, opened from the Approve button.
- **Reject panel** → `st.expander`-like inline block controlled by `st.session_state.rejecting_case_id`, with quick-reason chips as `st.button` (small) that write into the text area's session key.
- **Toasts** → `st.toast(msg, icon=...)`.
- **Tables (Audit)** → `st.dataframe(df, hide_index=True, use_container_width=True, column_config=...)`. For the decision/tier chips, use text with a leading symbol (`● Executed`) since `dataframe` cannot render HTML. Use `on_select="rerun", selection_mode="single-row"` for row selection → open the detail drawer (render as an `st.dialog` or a right column).
- **Stacked status bar (Overview)** → a single HTML flex row with percentage widths; legend below. No charting library needed.
- **Metrics** → build custom `stat_tile` HTML. Avoid `st.metric` default styling unless you restyle it.

## 6. Live refresh (no flicker, no lost state)
Wrap the data-driven region in a fragment:
```python
@st.fragment(run_every="5s")
def queue_region():
    cases = api.get_cases()           # cached for ~2s to avoid duplicate calls
    ...render list + workspace...
```
Rules:
- All state lives in `st.session_state` (`selected_case_id`, `queue_tab`, `rejecting_case_id`, `reject_note`, `reviewer`, `last_seen_awaiting_ids`).
- Detect new arrivals by diffing `awaiting_approval` ids against `last_seen_awaiting_ids` → `st.toast`.
- **Pause polling while a dialog or reject panel is open:** `run_every=None if st.session_state.get("busy") else "5s"`.
- Sidebar badge: compute `awaiting` count in the sidebar from the same cached `api.get_cases()`.

## 7. API-to-UI mapping and data gaps
`api.py` is the only module that calls HTTP. Read `API_BASE` from env (`http://localhost:8000` default). Timeouts: 5s. On failure raise a `ApiError`; pages catch it and show the offline banner.

| UI need | Endpoint | Notes / gap and fallback |
|---|---|---|
| Customer names | `GET /customers` | Cache for the session. Map `id → name` |
| Case list | `GET /cases?status=` | Returns `{id, customer_id, status, summary, created_at}` only. **No amount/payee.** Fetch `/cases/{id}` for each `awaiting_approval` case to get `pending_approval` for the row's "what" line. For others use `summary` |
| Case detail | `GET /cases/{id}` | `case + pending_approval + audit + messages`. `pending_approval` has `tool, args_json, policy_ref, status` |
| Decision-card facts | `pending_approval.args_json` | Parse JSON. `txn_id`, `amount` available. **Payee, txn date, status, cap are not in the approval row.** Get cap/limit from `GET /tools` (`reverse_payment.cap_inr`). Payee/date: parse from `summary` if present, otherwise omit those cells. Do not guess |
| Why it needs approval | `audit` row with `decision == needs_approval` | Use its `reason`. Fallback: compute "above ₹{cap} limit" from args + tools |
| Safety checks | `audit` rows | Only show checks you can substantiate (see file 04 §3.2) |
| Policy rule text | not stored | Only `policy_ref` (`file.md#Section`) is available in the case. Show reference only. If the case's earlier chat response had citations, it is not persisted. Don't try to fetch policy text |
| Approve / reject | `POST /cases/{id}/approve`, `/reject` | Approve returns `{case_id, status, result: ToolResult}`. Read `result.status`, `result.reason`, `result.data` (`refund_ref`) |
| Audit table | `GET /audit` | Columns as in file 05. `args_masked_json`, `result_json` are JSON strings. Parse defensively |
| Metrics | `GET /metrics` | `auto_resolution_rate` is a 0–1 ratio. Display as a % (guard: if it is already > 1 treat as a percent) |
| Tool viewer | `GET /tools` | Parsed YAML. Read `tools` list defensively |
| Escalated "Mark handled" | none | **No endpoint. Do not build the button.** If wanted, raise it with the backend owner (new `POST /cases/{id}/resolve`) *after telling the whole team*. Contracts are frozen |

**Normalisation rule:** write small getters (`safe(d, "a", "b", default="—")`, `parse_json(s, default={})`) and use them everywhere. The backend is being built in parallel; field names may be nested or absent. **The UI must never crash on a missing field.**

**Dev without a backend:** `api.py` supports `USE_MOCK=1`, returning canned data shaped like §6 of the PRD (3 cases: awaiting, escalated, resolved) so the UI can be built before integration at 2:15.

## 8. Streamlit pitfalls to avoid
- **Duplicate widget keys** → always pass unique `key=` using the case id.
- **Reruns resetting state** → anything that must survive goes in `st.session_state`.
- **Raw LLM text in HTML** → always `html.escape`.
- **Blocking UI** → wrap approve in `with st.spinner("Executing…")` and set `busy` first.
- **Layout jumps** → reserve the workspace height with a skeleton while loading.
- **Over-nesting columns** → max two levels, otherwise it collapses on narrow screens.
- **Don't** use `st.experimental_*` APIs. **Don't** build custom JS components.
