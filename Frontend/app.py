import html
import json
import os
from datetime import datetime
from typing import Any

import requests
import streamlit as st


API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 5
PRODUCT_NAME = "Resolvit.ai"

st.set_page_config(
    page_title="Resolvit.ai | Review console",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #0F1222;
        --muted: #555B6E;
        --subtle: #8A90A2;
        --line: #E4E7EC;
        --line-strong: #CDD2DA;
        --accent: #4A3C8C;
        --accent-dark: #3A2E73;
        --attention: #C25E0E;
        --attention-tint: #FFF3E6;
        --success: #17744C;
        --success-tint: #E8F6EF;
        --danger: #B8312D;
        --danger-tint: #FDEDEC;
        --info: #2859C5;
        --info-tint: #EAF0FE;
        --brand-tint: #F1EEFB;
        --canvas: #F6F7F9;
        --panel: #FFFFFF;
        --sunken: #F0F2F5;
        --sidebar: #12142B;
        --sidebar-text: #C9CCE0;
    }
    html, body, [class*="css"] { font-family: Inter, "Segoe UI", Arial, sans-serif; }
    .stApp { background: var(--canvas); color: var(--ink); }
    [data-testid="stHeader"] { background: var(--canvas); }
    [data-testid="stSidebar"] {
        background: var(--sidebar);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] * { color: var(--sidebar-text); }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--sidebar-text); }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 9px 10px;
        margin: 2px 0;
        border-radius: 7px;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(255,255,255,.08); }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--sidebar-text); }
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] { background: rgba(255,255,255,.08); }
    .block-container { max-width: 1400px; padding: 24px 32px 48px; }
    h1, h2, h3 { font-family: Inter, "Segoe UI", Arial, sans-serif !important; color: var(--ink); }
    h1 { font-size: 1.85rem !important; letter-spacing: -.035em; font-weight: 700 !important; }
    h2 { font-size: 1.15rem !important; letter-spacing: -.02em; font-weight: 650 !important; }
    h3 { font-size: .98rem !important; font-weight: 650 !important; }
    p, [data-testid="stMarkdownContainer"] { color: var(--ink); }
    [data-testid="stCaptionContainer"] { color: var(--muted); }
    div[data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: none;
    }
    div[data-testid="stMetricLabel"] { color: var(--muted); font-weight: 600; }
    div[data-testid="stMetricValue"] { color: var(--ink); font-weight: 650; }
    div[data-testid="stMetricDelta"] { font-size: .75rem; }
    div[data-testid="stButton"] > button {
        border-radius: 7px;
        border: 1px solid var(--line-strong);
        color: var(--ink);
        font-weight: 600;
        min-height: 2.35rem;
        transition: .15s ease;
    }
    div[data-testid="stButton"] > button:hover { border-color: var(--accent); color: var(--accent-dark); }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: var(--accent);
        border-color: var(--accent);
        color: #fff;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { background: var(--accent-dark); color: #fff; }
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
        border-radius: 8px;
        border-color: var(--line-strong);
        background: #fff;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div { border-radius: 7px; }
    [data-testid="stExpander"] {
        border: 1px solid var(--line);
        background: #fff;
        border-radius: 9px;
    }
    .brand {
        display: flex; align-items: center; gap: 10px;
        padding: 4px 0 22px;
        font-size: 1.04rem; font-weight: 750; letter-spacing: -.025em;
    }
    .brand-mark {
        width: 32px; height: 32px; border-radius: 8px;
        display: grid; place-items: center;
        background: var(--accent);
        color: white; font-weight: 800;
    }
    .eyebrow {
        color: var(--accent-dark); font-size: .7rem; text-transform: uppercase;
        letter-spacing: .1em; font-weight: 700; margin-bottom: 7px;
    }
    .subtitle { color: var(--muted); margin-top: -.5rem; }
    .section-heading {
        display: flex; align-items: center; justify-content: space-between;
        margin: 22px 0 8px;
    }
    .case-tile {
        background: #fff; border: 1px solid var(--line); border-radius: 9px;
        padding: 14px 16px; margin: 8px 0 10px;
        box-shadow: 0 1px 2px rgba(30, 45, 55, .025);
    }
    .case-topline { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
    .case-id { color: #53616c; font-size: .74rem; font-weight: 700; letter-spacing: .035em; }
    .case-summary { color: var(--ink); font-size: .93rem; font-weight: 600; margin: 8px 0 5px; }
    .case-meta { color: var(--muted); font-size: .78rem; }
    .pill {
        display: inline-flex; align-items: center; border-radius: 99px;
        padding: 4px 8px; font-size: .66rem; font-weight: 700;
        letter-spacing: .02em; white-space: nowrap;
    }
    .pill-amber { background: #fff4d8; color: #805500; }
    .pill-red { background: #fdeceb; color: #a6322c; }
    .pill-green { background: #e1f4ec; color: #237555; }
    .pill-blue { background: #edf1f3; color: #53616c; }
    .info-box {
        border: 1px solid var(--line); background: #fff; border-radius: 9px;
        padding: 13px 15px; margin: 8px 0;
    }
    .info-title { color: var(--muted); font-size: .73rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
    .info-value { color: var(--ink); font-size: .94rem; font-weight: 600; margin-top: 5px; word-break: break-word; }
    .empty-state {
        background: #fff; border: 1px solid var(--line); border-radius: 9px;
        padding: 22px 18px; color: var(--muted); margin: 12px 0;
    }
    .workspace-note {
        border-left: 3px solid var(--accent); background: #f1f8f5; border-radius: 0 7px 7px 0;
        padding: 11px 13px; color: #536b62; font-size: .82rem; margin: 12px 0;
    }
    .sidebar-footer { color: var(--muted); font-size: .72rem; line-height: 1.6; margin-top: 22px; }
    [data-testid="stAlert"] { border-radius: 8px; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    .rv-card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; margin:8px 0 14px; }
    .rv-card--attention { border-top:3px solid var(--attention); }
    .rv-card--success { border-top:3px solid var(--success); }
    .rv-card--danger { border-top:3px solid var(--danger); }
    .rv-title { font-size:1.04rem; font-weight:650; color:var(--ink); margin-bottom:8px; }
    .rv-muted { color:var(--muted); font-size:.86rem; }
    .rv-caption { color:var(--muted); font-size:.75rem; font-weight:600; }
    .rv-mono { font-family:"JetBrains Mono",ui-monospace,monospace; font-size:.82rem; }
    .rv-chip { display:inline-block; border-radius:999px; padding:3px 9px; font-size:.75rem; font-weight:600; white-space:nowrap; }
    .rv-chip--attention { color:var(--attention); background:var(--attention-tint); }
    .rv-chip--success { color:var(--success); background:var(--success-tint); }
    .rv-chip--danger { color:var(--danger); background:var(--danger-tint); }
    .rv-chip--info { color:var(--info); background:var(--info-tint); }
    .rv-chip--brand { color:var(--accent); background:var(--brand-tint); }
    .rv-chip--neutral { color:var(--muted); background:var(--sunken); }
    .rv-callout { border-left:3px solid var(--accent); background:var(--brand-tint); padding:10px 12px; border-radius:0 8px 8px 0; margin:10px 0; }
    .rv-callout--attention { border-color:var(--attention); background:var(--attention-tint); }
    .rv-callout--danger { border-color:var(--danger); background:var(--danger-tint); }
    .rv-fact { padding:8px 0; border-bottom:1px solid var(--line); }
    .rv-fact:last-child { border-bottom:0; }
    .rv-case-row { border-bottom:1px solid var(--line); padding:10px 8px; }
    .rv-case-row--selected { background:var(--brand-tint); border-left:3px solid var(--accent); }
    .rv-case-row--attention { border-left:3px solid var(--attention); }
    .rv-status { font-variant-numeric:tabular-nums; }
    @media (max-width: 1023px) {
        .block-container { padding:16px; }
        .rv-mobile-stack { display:block; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


class APIError(Exception):
    """A backend request failed or returned an unusable response."""


def api_request(method: str, path: str, *, params: dict | None = None, payload: dict | None = None) -> Any:
    try:
        response = requests.request(
            method,
            f"{API_BASE}{path}",
            params=params,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise APIError(f"Could not reach the ResolveAI API at {API_BASE}: {exc}") from exc

    if not response.ok:
        detail = response.text[:400] or response.reason
        raise APIError(f"{method} {path} failed ({response.status_code}): {detail}")

    try:
        return response.json()
    except ValueError as exc:
        raise APIError(f"{method} {path} returned invalid JSON.") from exc


def api_get(path: str, *, params: dict | None = None) -> Any:
    return api_request("GET", path, params=params)


def api_post(path: str, payload: dict) -> Any:
    return api_request("POST", path, payload=payload)


def is_preview_mode() -> bool:
    return bool(st.session_state.get("preview-mode", True))


def ensure_preview_data() -> None:
    if "preview_cases" in st.session_state:
        return

    st.session_state["preview_cases"] = [
        {
            "id": "CASE-0002",
            "customer_id": "C001",
            "status": "awaiting_approval",
            "summary": "₹5,000 flight booking failed but the amount was debited",
            "created_at": "2026-11-15T09:10:00",
        },
        {
            "id": "CASE-0003",
            "customer_id": "C002",
            "status": "escalated",
            "summary": "Customer reports a compromised account; wallet frozen",
            "created_at": "2026-11-15T08:42:00",
        },
    ]
    st.session_state["preview_case_details"] = {
        "CASE-0002": {
            "case": st.session_state["preview_cases"][0],
            "pending_approval": {
                "tool": "reverse_payment",
                "args": {"txn_id": "T1002", "amount": 5000},
                "policy_ref": "paytm_escalation.md#High-value reversals",
            },
            "messages": [
                {"role": "customer", "content": "₹5000 flight booking failed but money was deducted."},
                {
                    "role": "assistant",
                    "content": "I’ve sent this transaction for specialist review. The amount is above the automatic reversal limit.",
                },
            ],
            "audit": [
                {
                    "ts": "2026-11-15T09:10:05",
                    "case_id": "CASE-0002",
                    "actor": "agent",
                    "tool": "reverse_payment",
                    "tier": "money_moving",
                    "decision": "needs_approval",
                    "reason": "Amount exceeds the automatic reversal limit.",
                    "policy_ref": "paytm_escalation.md#High-value reversals",
                }
            ],
        },
        "CASE-0003": {
            "case": st.session_state["preview_cases"][1],
            "pending_approval": None,
            "messages": [
                {"role": "customer", "content": "Someone hacked my account."},
                {"role": "assistant", "content": "Your wallet has been frozen to protect your account. A specialist will follow up."},
            ],
            "audit": [
                {
                    "ts": "2026-11-15T08:42:04",
                    "case_id": "CASE-0003",
                    "actor": "agent",
                    "tool": "freeze_wallet",
                    "tier": "protective",
                    "decision": "executed",
                    "reason": "Protective wallet freeze completed.",
                    "policy_ref": None,
                },
                {
                    "ts": "2026-11-15T08:42:06",
                    "case_id": "CASE-0003",
                    "actor": "agent",
                    "tool": "escalate_to_human",
                    "tier": "platform",
                    "decision": "escalated",
                    "reason": "Customer reports a compromised account.",
                    "policy_ref": None,
                },
            ],
        },
    }


def preview_cases(status: str | None = None) -> list[dict]:
    ensure_preview_data()
    cases = st.session_state["preview_cases"]
    if status:
        cases = [case for case in cases if case.get("status") == status]
    return cases


def preview_review_case(case_id: str, decision: str, reviewer: str, note: str = "") -> None:
    detail = st.session_state["preview_case_details"][case_id]
    new_status = "resolved" if decision == "approved" else "rejected"
    detail["case"]["status"] = new_status
    detail["pending_approval"] = None
    detail["audit"].append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "case_id": case_id,
            "actor": reviewer,
            "tool": "reverse_payment",
            "tier": "money_moving",
            "decision": decision,
            "reason": note or "Demo approval simulated locally; no payment was processed.",
            "policy_ref": "paytm_escalation.md#High-value reversals",
        }
    )
    st.session_state["action_notice"] = (
        "Demo approval recorded locally; no real payment was processed."
        if decision == "approved"
        else "Demo rejection recorded locally; no backend action was taken."
    )


def preview_tools() -> list[dict]:
    return [
        {"name": "get_customer_profile", "tier": "read_only", "description": "View the verified customer profile."},
        {"name": "list_recent_transactions", "tier": "read_only", "description": "Review recent customer transactions."},
        {"name": "get_payment_status", "tier": "read_only", "description": "Check the status of a transaction."},
        {"name": "get_wallet_balance", "tier": "read_only", "description": "View the current wallet balance."},
        {"name": "reverse_payment", "tier": "money_moving", "description": "Reverse eligible failed payments; amounts above ₹2,000 need approval."},
        {"name": "freeze_wallet", "tier": "protective", "description": "Freeze a wallet when account compromise is suspected."},
        {"name": "update_registered_phone", "tier": "sensitive", "description": "Change a registered phone number after review."},
        {"name": "schedule_followup", "tier": "platform", "description": "Schedule a transaction follow-up."},
        {"name": "escalate_to_human", "tier": "platform", "description": "Route a case to a human specialist."},
    ]


def safe_text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def status_pill(status: str) -> str:
    styles = {
        "awaiting_approval": ("pill-amber", "Awaiting approval"),
        "escalated": ("pill-red", "Escalated"),
        "resolved": ("pill-green", "Resolved"),
        "rejected": ("pill-red", "Rejected"),
        "open": ("pill-blue", "Open"),
        "need_info": ("pill-blue", "Needs information"),
    }
    css_class, label = styles.get(status, ("pill-blue", status.replace("_", " ").title()))
    return f'<span class="pill {css_class}">{html.escape(label)}</span>'


def parse_object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def format_amount(value: Any) -> str:
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return safe_text(value)


def format_date(value: Any) -> str:
    if not value:
        return "Date unavailable"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y · %I:%M %p")
    except ValueError:
        return str(value)


def case_identifier(case: dict) -> str:
    return safe_text(case.get("id") or case.get("case_id"), "Unknown case")


def case_summary(case: dict) -> str:
    return safe_text(case.get("summary"), "No case summary has been added yet.")


def show_case_tile(case: dict, key_prefix: str) -> None:
    case_id = case_identifier(case)
    customer_id = safe_text(case.get("customer_id"))
    status = safe_text(case.get("status"), "open")
    created = format_date(case.get("created_at"))
    safe_id = html.escape(case_id)
    safe_summary = html.escape(case_summary(case))
    safe_customer = html.escape(customer_id)
    safe_created = html.escape(created)
    with st.container(border=True):
        case_header, case_status = st.columns([4, 1])
        case_header.markdown(f'<div class="case-id">{safe_id}</div>', unsafe_allow_html=True)
        case_status.markdown(f"<div style='text-align:right'>{status_pill(status)}</div>", unsafe_allow_html=True)
        st.markdown(f'<div class="case-summary">{safe_summary}</div>', unsafe_allow_html=True)
        meta_col, action_col = st.columns([3, 1])
        meta_col.markdown(
            f'<div class="case-meta">Customer {safe_customer} &nbsp;·&nbsp; {safe_created}</div>',
            unsafe_allow_html=True,
        )
        action_col.button(
            "Review case",
            key=f"{key_prefix}-{case_id}",
            use_container_width=True,
            on_click=open_case,
            args=(case_id,),
        )


def open_case(case_id: str) -> None:
    st.session_state["selected_case_id"] = case_id
    st.session_state["active_view"] = "Case review"
    st.session_state["workspace-navigation"] = "Case review"


def show_empty(message: str) -> None:
    st.markdown(
        f'<div class="empty-state">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def load_cases(status: str) -> list[dict]:
    if is_preview_mode():
        return preview_cases(status)
    result = api_get("/cases", params={"status": status})
    if not isinstance(result, list):
        raise APIError(f"GET /cases?status={status} returned an unexpected response.")
    return [case for case in result if isinstance(case, dict)]


def load_metrics() -> dict:
    if is_preview_mode():
        return {
            "total": 18,
            "resolved": 12,
            "escalated": 3,
            "awaiting_approval": len(preview_cases("awaiting_approval")),
            "auto_resolution_rate": 0.67,
        }
    result = api_get("/metrics")
    if not isinstance(result, dict):
        raise APIError("GET /metrics returned an unexpected response.")
    return result


def load_case_detail(case_id: str) -> dict:
    if is_preview_mode():
        ensure_preview_data()
        try:
            return st.session_state["preview_case_details"][case_id]
        except KeyError as exc:
            raise APIError(f"No preview case exists with ID {case_id}.") from exc
    result = api_get(f"/cases/{case_id}")
    if not isinstance(result, dict):
        raise APIError(f"GET /cases/{case_id} returned an unexpected response.")
    return result


def load_audit(case_id: str = "") -> list[dict]:
    if is_preview_mode():
        ensure_preview_data()
        details = st.session_state["preview_case_details"].values()
        rows = [row for detail in details for row in detail["audit"]]
        if case_id:
            rows = [row for row in rows if row.get("case_id") == case_id]
        return rows
    params = {"case_id": case_id} if case_id else None
    result = api_get("/audit", params=params)
    if not isinstance(result, list):
        raise APIError("GET /audit returned an unexpected response.")
    return result


def load_tools() -> Any:
    if is_preview_mode():
        return preview_tools()
    return api_get("/tools")


def render_case_detail(case_id: str) -> None:
    try:
        detail = load_case_detail(case_id)
    except APIError as exc:
        st.error(str(exc))
        return
    if not isinstance(detail, dict):
        st.error("The case endpoint returned an unexpected response.")
        return

    case = detail.get("case", detail)
    if not isinstance(case, dict):
        case = detail
    status = safe_text(case.get("status"), "open")
    pending = parse_object(detail.get("pending_approval"))
    audit = detail.get("audit") if isinstance(detail.get("audit"), list) else []
    messages = detail.get("messages") if isinstance(detail.get("messages"), list) else []

    st.button(
        "Back to workspace",
        key="back-to-workspace",
        on_click=return_to_workspace,
    )

    st.markdown(f'<div class="eyebrow">Case workspace · {html.escape(case_id)}</div>', unsafe_allow_html=True)
    title_col, status_col = st.columns([4, 1])
    with title_col:
        st.title(case_summary(case))
        st.markdown(
            f'<div class="subtitle">Customer {html.escape(safe_text(case.get("customer_id")))}'
            f' &nbsp;·&nbsp; Opened {html.escape(format_date(case.get("created_at")))}</div>',
            unsafe_allow_html=True,
        )
    with status_col:
        st.markdown(f"<br>{status_pill(status)}", unsafe_allow_html=True)

    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.subheader("Case overview")
        overview_cols = st.columns(3)
        overview_items = [
            ("Case ID", case_id),
            ("Customer", safe_text(case.get("customer_id"))),
            ("Opened", format_date(case.get("created_at"))),
        ]
        for column, (label, value) in zip(overview_cols, overview_items):
            column.markdown(
                f'<div class="info-box"><div class="info-title">{html.escape(label)}</div>'
                f'<div class="info-value">{html.escape(value)}</div></div>',
                unsafe_allow_html=True,
            )
        if pending:
            args = parse_object(pending.get("args_json")) or parse_object(pending.get("args"))
            amount = args.get("amount", pending.get("amount"))
            txn_id = args.get("txn_id", pending.get("txn_id"))
            policy_ref = pending.get("policy_ref")
            st.markdown("#### Proposed action")
            action_cols = st.columns(3)
            action_cols[0].markdown(
                f'<div class="info-box"><div class="info-title">Action</div><div class="info-value">{html.escape(safe_text(pending.get("tool")))}</div></div>',
                unsafe_allow_html=True,
            )
            action_cols[1].markdown(
                f'<div class="info-box"><div class="info-title">Amount</div><div class="info-value">{html.escape(format_amount(amount))}</div></div>',
                unsafe_allow_html=True,
            )
            action_cols[2].markdown(
                f'<div class="info-box"><div class="info-title">Transaction</div><div class="info-value">{html.escape(safe_text(txn_id))}</div></div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Policy reference: {safe_text(policy_ref)}")
        else:
            st.markdown(
                '<div class="workspace-note">No pending approval is attached to this case. Review its history and audit trail before taking further action.</div>',
                unsafe_allow_html=True,
            )

        with st.expander(f"Conversation · {len(messages)} messages", expanded=bool(messages)):
            if not messages:
                st.caption("No conversation messages were returned.")
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = safe_text(message.get("role") or message.get("actor"), "message").title()
                content = safe_text(message.get("content") or message.get("message"))
                st.markdown(f"**{html.escape(role)}**")
                st.write(content)

        with st.expander(f"Audit trail · {len(audit)} events", expanded=True):
            if audit:
                st.dataframe(audit, use_container_width=True, hide_index=True)
            else:
                st.caption("No audit events are available for this case.")

    with right:
        st.subheader("Human review")
        reviewer = st.text_input(
            "Reviewer name",
            value=st.session_state.get("reviewer_name", ""),
            placeholder="Your name",
            key="case-reviewer",
        )
        st.session_state["reviewer_name"] = reviewer

        if status == "awaiting_approval" and pending:
            st.markdown(
                '<div class="workspace-note">Confirm the transaction, amount, and cited policy before approving. The backend gateway remains the final authority.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Approve action", type="primary", use_container_width=True, disabled=not reviewer.strip()):
                try:
                    if is_preview_mode():
                        preview_review_case(case_id, "approved", reviewer.strip())
                    else:
                        api_post(f"/cases/{case_id}/approve", {"reviewer": reviewer.strip()})
                    st.success("Approval submitted.")
                    st.rerun()
                except APIError as exc:
                    st.error(str(exc))
            with st.form(f"reject-{case_id}"):
                note = st.text_area("Reason for rejection", placeholder="Add a short reason for the case record.")
                submitted = st.form_submit_button(
                    "Reject action",
                    use_container_width=True,
                    disabled=not reviewer.strip() or not note.strip(),
                )
                if submitted:
                    try:
                        if is_preview_mode():
                            preview_review_case(case_id, "rejected", reviewer.strip(), note.strip())
                        else:
                            api_post(f"/cases/{case_id}/reject", {"reviewer": reviewer.strip(), "note": note.strip()})
                        st.success("Rejection submitted.")
                        st.rerun()
                    except APIError as exc:
                        st.error(str(exc))
        else:
            st.info("This case has no pending approval to approve or reject.")

        st.markdown("#### Intervene in this case")
        st.markdown(
            """
            <div class="workspace-note">
                Case intervention tools are not available in the current backend contract. Review the conversation
                and audit trail, then use the team’s existing support process for any additional follow-up.
            </div>
            """,
            unsafe_allow_html=True,
        )
    notice = st.session_state.pop("action_notice", None)
    if notice:
        st.info(notice)


def return_to_workspace() -> None:
    st.session_state["active_view"] = "Command center"
    st.session_state["workspace-navigation"] = "Command center"
    st.session_state.pop("selected_case_id", None)


def render_command_center() -> None:
    st.markdown('<div class="eyebrow">Support operations</div>', unsafe_allow_html=True)
    st.title("Command center")
    st.markdown('<div class="subtitle">A clear view of cases that need a human decision.</div>', unsafe_allow_html=True)
    if is_preview_mode():
        st.info("Preview mode: sample cases are shown. Approve/reject actions are simulated locally only.")
    try:
        metrics = load_metrics()
        approvals = load_cases("awaiting_approval")
        escalated = load_cases("escalated")
    except APIError as exc:
        st.error(str(exc))
        st.info("Check that the ResolveAI API is running and that API_BASE points to its base URL.")
        return

    resolution_rate = metrics.get("auto_resolution_rate", 0)
    try:
        resolution_rate = float(resolution_rate)
        if resolution_rate <= 1:
            resolution_rate *= 100
    except (TypeError, ValueError):
        resolution_rate = 0

    metric_cols = st.columns(4)
    metric_cols[0].metric("Cases handled", safe_text(metrics.get("total"), "0"))
    metric_cols[1].metric("Auto-resolved", f"{resolution_rate:.0f}%")
    metric_cols[2].metric("Awaiting approval", len(approvals))
    metric_cols[3].metric("Escalated", len(escalated))

    approval_col, escalation_col = st.columns([1.15, 1], gap="large")
    with approval_col:
        st.subheader("Needs your decision")
        if approvals:
            for case in approvals[:4]:
                show_case_tile(case, "dashboard-approval")
            if len(approvals) > 4:
                st.caption(f"{len(approvals) - 4} additional cases are in the approval queue.")
        else:
            show_empty("The approval queue is clear.")
    with escalation_col:
        st.subheader("Escalated for review")
        if escalated:
            for case in escalated[:4]:
                show_case_tile(case, "dashboard-escalated")
            if len(escalated) > 4:
                st.caption(f"{len(escalated) - 4} additional cases are escalated.")
        else:
            show_empty("No escalated cases need attention.")


def render_case_list(status: str) -> None:
    is_approval = status == "awaiting_approval"
    title = "Approval queue" if is_approval else "Escalations"
    description = (
        "Review policy-backed actions that need a human decision."
        if is_approval
        else "Investigate cases that require human judgment or specialist follow-up."
    )
    st.markdown('<div class="eyebrow">Case management</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="subtitle">{description}</div>', unsafe_allow_html=True)
    if is_preview_mode():
        st.info("Preview mode: sample cases are shown. Actions are simulated locally only.")
    try:
        cases = load_cases(status)
    except APIError as exc:
        st.error(str(exc))
        return
    query = st.text_input("Search cases", placeholder="Search by case ID, customer, or summary")
    if query.strip():
        query = query.strip().casefold()
        cases = [
            case
            for case in cases
            if query in case_identifier(case).casefold()
            or query in safe_text(case.get("customer_id"), "").casefold()
            or query in case_summary(case).casefold()
        ]
    if not cases:
        show_empty("No cases match your search." if query.strip() else "Nothing is waiting in this queue.")
        return
    st.caption(f"{len(cases)} case{'s' if len(cases) != 1 else ''} · oldest first")
    for case in cases:
        show_case_tile(case, f"queue-{status}")


def render_audit_and_tools() -> None:
    st.markdown('<div class="eyebrow">Governance</div>', unsafe_allow_html=True)
    st.title("Audit & tools")
    st.markdown('<div class="subtitle">Trace decisions and inspect the read-only tool registry.</div>', unsafe_allow_html=True)
    audit_tab, tools_tab = st.tabs(["Audit trail", "Tool registry"])
    if is_preview_mode():
        st.info("Preview mode: audit records and tools are sample data.")
    with audit_tab:
        case_filter = st.text_input("Filter by case ID", placeholder="e.g. CASE-0001")
        try:
            audit = load_audit(case_filter.strip())
            if audit:
                st.dataframe(audit, use_container_width=True, hide_index=True)
            else:
                show_empty("No audit records match this filter.")
        except APIError as exc:
            st.error(str(exc))
    with tools_tab:
        st.caption("Registry is read-only. Actions are executed through the governed backend gateway.")
        try:
            tools = load_tools()
            if isinstance(tools, dict):
                tools = tools.get("tools", tools)
            if isinstance(tools, list):
                if tools:
                    st.dataframe(tools, use_container_width=True, hide_index=True)
                else:
                    show_empty("The tool registry is empty.")
            else:
                st.json(tools)
        except APIError as exc:
            st.error(str(exc))


STATUS_LABELS = {
    "awaiting_approval": "Needs approval",
    "escalated": "Escalated",
    "open": "AI working",
    "need_info": "Waiting on customer",
    "resolved": "Resolved",
    "rejected": "Rejected",
}
STATUS_STYLES = {
    "awaiting_approval": "attention",
    "escalated": "brand",
    "open": "info",
    "need_info": "neutral",
    "resolved": "success",
    "rejected": "danger",
}
TIER_LABELS = {
    "read_only": "Read",
    "reversible": "Reversible",
    "money_moving": "Money",
    "sensitive": "Sensitive",
    "protective": "Protective",
    "platform": "Platform",
}
TIER_STYLES = {
    "read_only": "neutral",
    "reversible": "info",
    "money_moving": "attention",
    "sensitive": "attention",
    "protective": "brand",
    "platform": "neutral",
}
DECISION_LABELS = {
    "executed": "Executed",
    "needs_approval": "Needs approval",
    "blocked": "Blocked",
    "error": "Error",
    "escalated": "Escalated",
}
DECISION_STYLES = {
    "executed": "success",
    "needs_approval": "attention",
    "blocked": "danger",
    "error": "danger",
    "escalated": "brand",
}


def display_text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "" or str(value).lower() in {"none", "null", "nan", "undefined"}:
        return fallback
    return str(value)


def chip_markup(label: str, style: str = "neutral") -> str:
    return f'<span class="rv-chip rv-chip--{html.escape(style)}">{html.escape(label)}</span>'


def status_markup(status: str) -> str:
    return chip_markup(STATUS_LABELS.get(status, status.replace("_", " ").title()), STATUS_STYLES.get(status, "neutral"))


def tier_markup(tier: str) -> str:
    return chip_markup(TIER_LABELS.get(tier, tier.replace("_", " ").title()), TIER_STYLES.get(tier, "neutral"))


def decision_markup(decision: str) -> str:
    return chip_markup(DECISION_LABELS.get(decision, decision.replace("_", " ").title()), DECISION_STYLES.get(decision, "neutral"))


def money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return display_text(value)
    whole, _, fraction = f"{amount:.2f}".partition(".")
    if fraction == "00":
        fraction = ""
    tail = whole[-3:]
    head = whole[:-3]
    first_group = len(head) % 2 or min(len(head), 2)
    grouped_head = head[:first_group]
    grouped_head += "".join("," + head[index:index + 2] for index in range(first_group, len(head), 2))
    grouped = (grouped_head + "," if head else "") + tail
    return f"₹{grouped}" + (f".{fraction.rstrip('0')}" if fraction else "")


def relative_time(value: Any) -> str:
    if not value:
        return "Time unavailable"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo:
            now = datetime.now(timestamp.tzinfo)
        else:
            now = datetime.now()
        seconds = max(0, int((now - timestamp).total_seconds()))
    except (TypeError, ValueError):
        return display_text(value)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def load_all_cases() -> list[dict]:
    if is_preview_mode():
        return preview_cases()
    result = api_get("/cases")
    if not isinstance(result, list):
        raise APIError("GET /cases returned an unexpected response.")
    return [case for case in result if isinstance(case, dict)]


def load_customers() -> list[dict]:
    if is_preview_mode():
        return [
            {"id": "C001", "name": "Rahul Sharma"},
            {"id": "C002", "name": "Priya Verma"},
        ]
    result = api_get("/customers")
    if not isinstance(result, list):
        raise APIError("GET /customers returned an unexpected response.")
    return [customer for customer in result if isinstance(customer, dict)]


def get_case_id(case: dict) -> str:
    return display_text(case.get("id") or case.get("case_id"), "")


def get_case_status(case: dict) -> str:
    return display_text(case.get("status"), "open")


def get_pending_data(pending: Any) -> tuple[dict, str | None]:
    if not isinstance(pending, dict):
        return {}, None
    args = parse_object(pending.get("args_json")) or parse_object(pending.get("args"))
    return args, display_text(pending.get("policy_ref"), "") or None


def render_case_workspace(case_id: str, customer_names: dict[str, str]) -> None:
    try:
        detail = load_case_detail(case_id)
    except APIError as exc:
        st.error(f"Could not load this case. {exc}")
        return
    case = detail.get("case", detail)
    if not isinstance(case, dict):
        case = {}
    status = get_case_status(case)
    customer_id = display_text(case.get("customer_id"))
    customer_name = customer_names.get(customer_id, customer_id)
    pending = detail.get("pending_approval")
    args, policy_ref = get_pending_data(pending)
    audit = detail.get("audit") if isinstance(detail.get("audit"), list) else []
    messages = detail.get("messages") if isinstance(detail.get("messages"), list) else []
    amount = args.get("amount")
    txn_id = args.get("txn_id")
    action = display_text(pending.get("tool"), "Proposed action") if isinstance(pending, dict) else ""
    case_changed = st.session_state.get("reviewed_case_id") == case_id and status != "awaiting_approval"

    st.markdown(
        f'<div class="rv-mono">{html.escape(case_id)} &nbsp; {status_markup(status)}'
        f' <span class="rv-muted" title="{html.escape(format_date(case.get("created_at")))}">Opened {html.escape(relative_time(case.get("created_at")))}</span></div>'
        f'<div class="rv-title" style="margin-top:8px">{html.escape(customer_name)} · {html.escape(customer_id)}</div>',
        unsafe_allow_html=True,
    )

    if status == "awaiting_approval":
        if not pending or not amount:
            st.markdown(
                '<div class="rv-callout rv-callout--danger">Approval details unavailable. Do not act from here.</div>',
                unsafe_allow_html=True,
            )
        else:
            title_amount = money(amount)
            st.markdown(
                f'<div class="rv-card rv-card--attention"><div class="rv-title">Approve {html.escape(title_amount)} reversal to {html.escape(customer_name)}&#39;s wallet?</div>',
                unsafe_allow_html=True,
            )
            reason = next(
                (
                    row.get("reason")
                    for row in audit
                    if isinstance(row, dict) and row.get("decision") == "needs_approval" and row.get("reason")
                ),
                None,
            )
            cap = None
            try:
                tools = load_tools()
                tool_list = tools.get("tools", []) if isinstance(tools, dict) else tools
                if isinstance(tool_list, list):
                    tool = next((item for item in tool_list if isinstance(item, dict) and item.get("name") == action), {})
                    cap = tool.get("cap_inr")
            except APIError:
                pass
            if not reason and cap is not None:
                reason = f"This amount is {money(float(amount) - float(cap))} above the {money(cap)} auto-approval limit." if float(amount) > float(cap) else None
            if reason:
                st.markdown(f'<div class="rv-callout rv-callout--attention">⚠ {html.escape(display_text(reason))}</div>', unsafe_allow_html=True)
            facts = [("Action", action), ("Amount", title_amount), ("Customer", customer_name)]
            if txn_id:
                facts.append(("Transaction", str(txn_id)))
            if policy_ref:
                facts.append(("Policy", policy_ref))
            fact_columns = st.columns(min(3, len(facts)))
            for index, (label, value) in enumerate(facts):
                fact_columns[index % len(fact_columns)].markdown(
                    f'<div class="rv-fact"><div class="rv-caption">{html.escape(label)}</div><div>{html.escape(value)}</div></div>',
                    unsafe_allow_html=True,
                )
            with st.expander("Safety checks", expanded=False):
                for row in audit:
                    if isinstance(row, dict) and row.get("decision") == "needs_approval":
                        st.markdown("⚠ Amount is above the automatic approval limit; human approval is required.")
                        break
                if policy_ref:
                    st.markdown("✓ A policy reference is attached.")
            is_money_action = action in {"reverse_payment", "refund_payment", "trigger_reversal"}
            if not policy_ref and is_money_action:
                st.markdown('<div class="rv-callout rv-callout--danger">No policy cited, review carefully.</div>', unsafe_allow_html=True)
            elif policy_ref:
                ref_parts = policy_ref.split("#", 1)
                ref_label = f"{ref_parts[0]} › {ref_parts[1]}" if len(ref_parts) == 2 else policy_ref
                st.markdown(
                    f'<div class="rv-callout"><strong>Policy applied</strong><br><span class="rv-mono">{html.escape(ref_label)}</span></div>',
                    unsafe_allow_html=True,
                )
            if case_changed:
                st.warning("This case was just resolved. No further action is available.")
            else:
                reviewer = st.session_state.get("reviewer_name", "").strip()
                approve_col, reject_col = st.columns([1, 2])
                with approve_col:
                    if st.button(
                        f"Approve {title_amount} & execute",
                        type="primary",
                        disabled=not reviewer or not pending or amount is None,
                        help="Enter your name in the sidebar to continue" if not reviewer else None,
                        key=f"approve-{case_id}",
                    ):
                        st.session_state["confirm_case_id"] = case_id
                        st.rerun()
                with reject_col:
                    if st.button("Reject", disabled=not reviewer, help="Enter your name in the sidebar to continue" if not reviewer else None, key=f"reject-toggle-{case_id}"):
                        st.session_state["rejecting_case_id"] = case_id
                        st.session_state["busy"] = True
                        st.rerun()
                if st.session_state.get("rejecting_case_id") == case_id:
                    with st.form(f"reject-form-{case_id}"):
                        st.caption("Reason for rejecting (shown to the customer politely)")
                        quick_reasons = ["Duplicate request", "Transaction already settled", "Policy doesn't allow this", "Needs more verification"]
                        quick_cols = st.columns(2)
                        for index, quick_reason in enumerate(quick_reasons):
                            if quick_cols[index % 2].form_submit_button(quick_reason, key=f"quick-{case_id}-{index}"):
                                st.session_state["reject-note"] = quick_reason
                        note = st.text_area("Reason", key="reject-note", placeholder="Add a short, polite reason.")
                        cancel, submit = st.columns(2)
                        if cancel.form_submit_button("Cancel"):
                            st.session_state.pop("rejecting_case_id", None)
                            st.session_state["busy"] = False
                            st.rerun()
                        submitted = submit.form_submit_button("Reject case", disabled=len(note.strip()) < 3)
                        if submitted:
                            try:
                                if is_preview_mode():
                                    preview_review_case(case_id, "rejected", reviewer, note.strip())
                                else:
                                    api_post(f"/cases/{case_id}/reject", {"reviewer": reviewer, "note": note.strip()})
                                select_next_approval(case_id)
                                st.session_state.pop("rejecting_case_id", None)
                                st.session_state["busy"] = False
                                st.toast("Case rejected")
                                st.rerun()
                            except APIError as exc:
                                st.error(f"Could not reject this case. {exc}")
            st.markdown("</div>", unsafe_allow_html=True)
    elif status == "escalated":
        reason = next((row.get("reason") for row in audit if isinstance(row, dict) and row.get("tool") == "escalate_to_human" and row.get("reason")), case.get("summary"))
        st.markdown(
            f'<div class="rv-card"><div class="rv-title">Handed to a human</div><div class="rv-muted">Reason: {html.escape(display_text(reason))}</div>'
            '<div style="margin-top:10px">Suggested next step: Review the conversation and follow up with the customer.</div></div>',
            unsafe_allow_html=True,
        )
    elif status in {"resolved", "rejected"}:
        resolution = display_text(case.get("resolution_type"), "auto")
        style = "danger" if status == "rejected" else "success"
        title = "Rejected" if status == "rejected" else ("Approved by a human" if resolution == "human_approved" else "Resolved automatically")
        st.markdown(f'<div class="rv-card rv-card--{style}"><div class="rv-title">{html.escape(title)}</div><div class="rv-muted">{html.escape(display_text(case.get("resolution_note") or case.get("summary")))}</div></div>', unsafe_allow_html=True)
    elif status != "awaiting_approval":
        st.markdown('<div class="rv-callout">The AI is working on this case. No human action is required right now.</div>', unsafe_allow_html=True)

    summary = display_text(case.get("case_summary") or case.get("summary"), "No summary yet.")
    st.markdown(f'<div class="rv-card"><div class="rv-title">What the AI found</div><div>{html.escape(summary)}</div><div class="rv-muted" style="margin-top:8px">Prepared by the AI agent. You never need to re-ask the customer.</div></div>', unsafe_allow_html=True)
    timeline_tab, conversation_tab, audit_tab = st.tabs(["Timeline", "Conversation", "Audit"])
    with timeline_tab:
        if not audit:
            st.caption("No timeline events are available yet.")
        for row in reversed(audit):
            if not isinstance(row, dict):
                continue
            tool = display_text(row.get("tool"), "unknown tool")
            decision = display_text(row.get("decision"), "")
            text = display_text(row.get("reason"), f"Ran {tool}")
            if tool in {"reverse_payment", "trigger_reversal"} and decision == "needs_approval":
                text = f"Asked for human approval: {money(amount)} is above the automatic limit" if amount else "Asked for human approval."
            elif tool == "freeze_wallet" and decision == "executed":
                text = "Froze wallet to protect the account"
            elif tool == "escalate_to_human":
                text = f"Handed to a human reviewer: {display_text(row.get('reason'))}"
            st.markdown(f"• {html.escape(text)} &nbsp; {tier_markup(display_text(row.get('tier'), ''))} {decision_markup(decision)} <span class='rv-muted'>{html.escape(relative_time(row.get('ts') or row.get('created_at')))}</span>", unsafe_allow_html=True)
    with conversation_tab:
        if not messages:
            st.caption("No conversation messages were returned.")
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = display_text(message.get("role"), "message").title()
            content = display_text(message.get("content") or message.get("message"), "")
            st.markdown(f"**{html.escape(role)}**")
            st.write(content)
    with audit_tab:
        if audit:
            st.dataframe(audit, use_container_width=True, hide_index=True)
        else:
            st.caption("No audit events are available.")


@st.dialog("Confirm approval")
def confirm_approval_dialog() -> None:
    case_id = st.session_state.get("confirm_case_id")
    if not case_id:
        return
    try:
        detail = load_case_detail(case_id)
    except APIError as exc:
        st.error(f"Could not load approval details. {exc}")
        return
    pending = detail.get("pending_approval")
    args, _ = get_pending_data(pending)
    amount = args.get("amount")
    reviewer = st.session_state.get("reviewer_name", "").strip()
    case = detail.get("case", detail)
    customer_id = display_text(case.get("customer_id") if isinstance(case, dict) else None, "")
    customer_name = st.session_state.get("customer_names", {}).get(customer_id, customer_id)
    st.write(f"Action: {display_text(pending.get('tool') if isinstance(pending, dict) else None, 'Reverse payment')}")
    st.write(f"Amount: {money(amount)}")
    st.write(f"To: {customer_name}'s wallet")
    if args.get("txn_id"):
        st.write(f"Transaction: {args['txn_id']}")
    st.write(f"Approving as: {reviewer}")
    st.warning("This will move money immediately and is recorded in the audit log. It cannot be undone.")
    cancel, confirm = st.columns(2)
    if cancel.button("Cancel", use_container_width=True):
        st.session_state.pop("confirm_case_id", None)
        st.rerun()
    if confirm.button("Approve & execute", type="primary", use_container_width=True, disabled=not reviewer or amount is None):
        try:
            st.session_state["busy"] = True
            with st.spinner("Executing…"):
                result = preview_review_case(case_id, "approved", reviewer) if is_preview_mode() else api_post(
                    f"/cases/{case_id}/approve", {"reviewer": reviewer}
                )
            tool_result = result.get("result", {}) if isinstance(result, dict) else {}
            if not is_preview_mode() and isinstance(tool_result, dict) and tool_result.get("status") != "ok":
                st.error(display_text(tool_result.get("reason"), "The action could not be completed. Try again."))
                st.session_state["busy"] = False
                return
            receipt = None
            if isinstance(tool_result, dict):
                data = tool_result.get("data") if isinstance(tool_result.get("data"), dict) else {}
                receipt = data.get("refund_ref")
            select_next_approval(case_id)
            st.session_state.pop("confirm_case_id", None)
            st.session_state["busy"] = False
            st.toast(f"Approved. {money(args.get('amount'))} reversed" + (f" ({receipt})" if receipt else ""))
            st.rerun()
        except APIError as exc:
            st.session_state["busy"] = False
            st.error(f"Could not complete the approval. {exc}")


def select_next_approval(current_case_id: str) -> None:
    try:
        remaining = [
            case for case in load_all_cases()
            if get_case_status(case) == "awaiting_approval" and get_case_id(case) != current_case_id
        ]
    except APIError:
        remaining = []
    remaining.sort(key=lambda case: display_text(case.get("created_at"), ""))
    if remaining:
        st.session_state["selected_case_id"] = get_case_id(remaining[0])
        st.session_state.pop("reviewed_case_id", None)
    else:
        st.session_state["selected_case_id"] = current_case_id
        st.session_state["reviewed_case_id"] = current_case_id


@st.fragment(
    run_every=None
    if st.session_state.get("busy") or st.session_state.get("confirm_case_id")
    else "5s"
)
def render_queue(customer_names: dict[str, str]) -> None:
    st.title("Review queue")
    st.caption("The cases that need your judgment, with the evidence to decide safely.")
    try:
        cases = load_all_cases()
        st.session_state["last_good_cases"] = cases
        st.session_state["api_online"] = True
        awaiting_by_id = {
            get_case_id(case): case
            for case in cases
            if get_case_status(case) == "awaiting_approval"
        }
        previous_ids = set(st.session_state.get("last_seen_awaiting_ids", []))
        new_arrivals = [case for case_id, case in awaiting_by_id.items() if case_id not in previous_ids]
        if "last_seen_awaiting_ids" in st.session_state:
            for arrival in new_arrivals:
                customer_id = display_text(arrival.get("customer_id"), "Customer")
                customer_name = customer_names.get(customer_id, customer_id)
                st.toast(f"New case needs approval: {customer_name}", icon="??")
        st.session_state["last_seen_awaiting_ids"] = list(awaiting_by_id)
    except APIError as exc:
        cases = st.session_state.get("last_good_cases", [])
        st.session_state["api_online"] = False
        st.error(f"Can't reach the server. Retrying… {exc}")
    try:
        metrics = load_metrics()
    except APIError:
        metrics = {}
    approvals = [case for case in cases if get_case_status(case) == "awaiting_approval"]
    escalated = [case for case in cases if get_case_status(case) == "escalated"]
    resolved = [case for case in cases if get_case_status(case) in {"resolved", "rejected"}]
    rate = metrics.get("auto_resolution_rate")
    try:
        rate = float(rate)
        rate = rate * 100 if rate <= 1 else rate
        rate_text = f"{rate:.0f}%"
    except (TypeError, ValueError):
        rate_text = "—"
    counters = st.columns(4)
    counters[0].metric("Needs approval", len(approvals))
    counters[1].metric("Escalated", len(escalated))
    counters[2].metric("Resolved", len([case for case in resolved if get_case_status(case) == "resolved"]))
    counters[3].metric("AI resolution rate", rate_text)

    selected_tab = st.radio(
        "Queue filter",
        ["Needs you", "Escalated", "Resolved", "All"],
        format_func=lambda tab: f"{tab} ({len(approvals if tab == 'Needs you' else escalated)})" if tab in {"Needs you", "Escalated"} else tab,
        horizontal=True,
        key="queue_tab",
    )
    if selected_tab == "Needs you":
        visible = approvals
    elif selected_tab == "Escalated":
        visible = escalated
    elif selected_tab == "Resolved":
        visible = resolved
    else:
        visible = cases
    reverse = selected_tab in {"Resolved", "All"}
    visible = sorted(visible, key=lambda item: display_text(item.get("created_at"), ""), reverse=reverse)
    if not st.session_state.get("selected_case_id"):
        preferred = sorted(approvals, key=lambda item: display_text(item.get("created_at"), "")) or escalated
        if preferred:
            st.session_state["selected_case_id"] = get_case_id(preferred[0])
    left, right = st.columns([0.72, 1.28], gap="large")
    with left:
        for case in visible:
            case_id = get_case_id(case)
            status = get_case_status(case)
            customer_id = display_text(case.get("customer_id"))
            customer_name = customer_names.get(customer_id, customer_id)
            summary = display_text(case.get("summary"), "No summary yet.")
            if status == "awaiting_approval":
                try:
                    details = load_case_detail(case_id)
                    args, _ = get_pending_data(details.get("pending_approval"))
                    if args.get("amount") is not None:
                        summary = f"{display_text(args.get('txn_id'), 'Payment')} · {money(args['amount'])} reversal"
                except APIError:
                    pass
            selected = case_id == st.session_state.get("selected_case_id")
            st.markdown(
                f'<div class="rv-case-row {"rv-case-row--selected" if selected else ("rv-case-row--attention" if status == "awaiting_approval" else "")}">'
                f'<strong>{html.escape(customer_name)}</strong><span style="float:right" class="rv-muted">{html.escape(relative_time(case.get("created_at")))}</span><br>'
                f'<span class="rv-muted">{html.escape(summary[:90])}</span><span style="float:right">{status_markup(status)}</span><br>'
                f'<span class="rv-mono rv-muted">{html.escape(case_id)}</span></div>',
                unsafe_allow_html=True,
            )
            if st.button("Open case", key=f"select-{case_id}", use_container_width=True):
                st.session_state["selected_case_id"] = case_id
                st.session_state.pop("reviewed_case_id", None)
                st.rerun()
        if not visible:
            if selected_tab == "Needs you":
                st.markdown('<div class="rv-card"><strong>All clear.</strong><br><span class="rv-muted">The AI is handling everything else. New cases that need you will appear here automatically.</span></div>', unsafe_allow_html=True)
            elif selected_tab == "Escalated":
                st.info("No escalated cases.")
            elif not cases:
                st.info("No cases yet. Start a conversation from the Customer chat page.")
            else:
                st.info("No resolved cases yet.")
    with right:
        case_id = st.session_state.get("selected_case_id")
        if case_id and any(get_case_id(case) == case_id for case in cases):
            render_case_workspace(case_id, customer_names)
        elif visible:
            st.session_state["selected_case_id"] = get_case_id(visible[0])
            render_case_workspace(st.session_state["selected_case_id"], customer_names)
        else:
            st.markdown('<div class="rv-card"><div class="rv-title">Nothing needs your attention</div><div class="rv-muted">You can review completed cases or return when a new case arrives.</div></div>', unsafe_allow_html=True)


def audit_sentence(row: dict) -> str:
    tool = display_text(row.get("tool"), "unknown tool")
    decision = row.get("decision")
    args = parse_object(row.get("args_masked_json"))
    txn = args.get("txn_id")
    amount = args.get("amount")
    if tool in {"reverse_payment", "trigger_reversal"} and decision == "executed":
        return f"Reversed {money(amount)}" + (f" for {txn}" if txn else "")
    if tool in {"reverse_payment", "trigger_reversal"} and decision == "needs_approval":
        return f"Requested human approval for {money(amount)}" if amount else "Requested human approval for a reversal"
    if tool == "freeze_wallet":
        return "Froze wallet to protect the account"
    if tool == "escalate_to_human":
        return "Handed the case to a human reviewer"
    return display_text(row.get("reason"), f"Ran {tool}")


def render_audit_page() -> None:
    st.title("Audit")
    st.caption("Every action the AI attempted, and what the gateway decided.")
    try:
        rows = load_audit()
    except APIError as exc:
        st.error(f"Can't load audit events. {exc}")
        return
    rows = [row for row in rows if isinstance(row, dict)][:200]
    if not rows:
        st.info("No audit events yet. Every action the AI takes will be recorded here.")
        return
    cases = sorted({display_text(row.get("case_id")) for row in rows})
    decisions = sorted({display_text(row.get("decision")) for row in rows})
    tiers = sorted({display_text(row.get("tier")) for row in rows})
    case_filter, decision_filter, tier_filter, search = st.columns([1, 1, 1, 1.5])
    case_choice = case_filter.selectbox("Case", ["All"] + cases)
    decision_choice = decision_filter.selectbox("Decision", ["All"] + decisions)
    tier_choice = tier_filter.selectbox("Tier", ["All"] + tiers)
    query = search.text_input("Search tool")
    filtered = [
        row for row in rows
        if (case_choice == "All" or row.get("case_id") == case_choice)
        and (decision_choice == "All" or row.get("decision") == decision_choice)
        and (tier_choice == "All" or row.get("tier") == tier_choice)
        and query.casefold() in display_text(row.get("tool"), "").casefold()
    ]
    st.caption(f"{len(filtered)} events" + (" · Showing latest 200" if len(rows) == 200 else ""))
    table = []
    for row in filtered:
        tier = display_text(row.get("tier"), "")
        decision = display_text(row.get("decision"), "")
        policy = display_text(row.get("policy_ref"), "—")
        missing_policy = tier == "money_moving" and decision == "executed" and policy == "—"
        table.append({
            "Time": relative_time(row.get("ts")),
            "Case": display_text(row.get("case_id")),
            "Actor": display_text(row.get("actor"), "agent"),
            "Tool": display_text(row.get("tool")),
            "Tier": TIER_LABELS.get(tier, tier.replace("_", " ").title()),
            "Decision": DECISION_LABELS.get(decision, decision.replace("_", " ").title()),
            "Policy": "Missing policy" if missing_policy else policy,
        })
    st.dataframe(table, use_container_width=True, hide_index=True)
    options = [f"{index}: {display_text(row.get('case_id'))} · {display_text(row.get('tool'))}" for index, row in enumerate(filtered)]
    if options:
        selected = st.selectbox("Event details", options, index=None, placeholder="Select an audit event")
        if selected:
            index = int(selected.split(":", 1)[0])
            row = filtered[index]
            st.markdown(f'<div class="rv-card"><div class="rv-title">{html.escape(audit_sentence(row))}</div>', unsafe_allow_html=True)
            st.write({
                "Time": format_date(row.get("ts")),
                "Actor": display_text(row.get("actor")),
                "Tool": display_text(row.get("tool")),
                "Tier": TIER_LABELS.get(display_text(row.get("tier"), ""), display_text(row.get("tier"))),
                "Decision": DECISION_LABELS.get(display_text(row.get("decision"), ""), display_text(row.get("decision"))),
                "Reason": display_text(row.get("reason")),
                "Policy reference": display_text(row.get("policy_ref")),
                "Audit ID": display_text(row.get("id")),
            })
            with st.expander("Arguments (masked)"):
                st.json(parse_object(row.get("args_masked_json")))
            with st.expander("Result"):
                st.json(parse_object(row.get("result_json")))
            st.markdown("</div>", unsafe_allow_html=True)


def render_overview(customer_names: dict[str, str]) -> None:
    st.title("Overview")
    st.caption("Is the AI earning its keep?")
    try:
        metrics = load_metrics()
        cases = load_all_cases()
    except APIError as exc:
        st.error(f"Can't load overview data. {exc}")
        return
    total = int(metrics.get("total", 0) or 0)
    resolved = int(metrics.get("resolved", 0) or 0)
    escalated = int(metrics.get("escalated", 0) or 0)
    awaiting = int(metrics.get("awaiting_approval", 0) or 0)
    rate = metrics.get("auto_resolution_rate")
    try:
        rate = float(rate)
        rate = rate * 100 if rate <= 1 else rate
        rate_label = f"{rate:.0f}%" if total else "—"
    except (TypeError, ValueError):
        rate_label = "—"
    hero, tiles = st.columns([1.5, 1])
    with hero:
        st.markdown(f'<div class="rv-card"><div class="rv-caption">AI resolution rate</div><div style="font-size:2rem;font-weight:700">{rate_label}</div><div class="rv-muted">Handled end to end without a human</div></div>', unsafe_allow_html=True)
    with tiles:
        stat_cols = st.columns(2)
        for col, label, value in [
            (stat_cols[0], "Total cases", total),
            (stat_cols[1], "Resolved", resolved),
            (stat_cols[0], "Escalated", escalated),
            (stat_cols[1], "Awaiting approval", awaiting),
        ]:
            col.metric(label, value)
    st.subheader("Case outcomes")
    outcome_total = max(total, 1)
    st.markdown(
        f'<div style="display:flex;height:14px;border-radius:99px;overflow:hidden;background:var(--sunken)">'
        f'<span style="width:{resolved / outcome_total * 100:.2f}%;background:var(--success)"></span>'
        f'<span style="width:{awaiting / outcome_total * 100:.2f}%;background:var(--attention)"></span>'
        f'<span style="width:{escalated / outcome_total * 100:.2f}%;background:var(--accent)"></span></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Resolved {resolved} · Awaiting approval {awaiting} · Escalated {escalated}")
    st.subheader(f"Needs you now ({awaiting})")
    needs_you = [case for case in cases if get_case_status(case) == "awaiting_approval"][:3]
    if needs_you:
        for case in needs_you:
            display_case = dict(case)
            customer_id = display_text(case.get("customer_id"))
            display_case["customer_id"] = f"{customer_names.get(customer_id, customer_id)} ({customer_id})"
            show_case_tile(display_case, "overview")
    else:
        st.info("All clear. No cases need your decision.")


TIER_ORDER = ["read_only", "reversible", "platform", "protective", "sensitive", "money_moving"]
TIER_GUIDANCE = {
    "read_only": "Looks up data only. It does not change anything.",
    "reversible": "Can be undone.",
    "platform": "Internal workflow, such as routing a case.",
    "protective": "Runs immediately to protect the customer.",
    "sensitive": "Requires step-up verification or human approval.",
    "money_moving": "Capped and policy-bound. Above the cap, a human must approve.",
}


def render_tools_page() -> None:
    st.title("Tools")
    st.caption("The AI can only use these tools, and the gateway enforces each limit. Policies can narrow what the AI does, never widen it.")
    try:
        result = load_tools()
    except APIError as exc:
        st.error(f"Can't load the tool registry. {exc}")
        return
    tools = result.get("tools", result) if isinstance(result, dict) else result
    if not isinstance(tools, list):
        st.json(result)
        return
    tools = [tool for tool in tools if isinstance(tool, dict)]
    for tier in TIER_ORDER:
        group = [tool for tool in tools if display_text(tool.get("tier"), "") == tier]
        if not group:
            continue
        st.subheader(TIER_LABELS[tier])
        st.caption(TIER_GUIDANCE[tier])
        for tool in group:
            with st.container(border=True):
                st.markdown(f'<span class="rv-mono">{html.escape(display_text(tool.get("name")))}</span> &nbsp; {tier_markup(tier)}', unsafe_allow_html=True)
                guardrail = TIER_GUIDANCE[tier]
                cap = tool.get("cap_inr")
                eligible = tool.get("eligible_status")
                if tier == "money_moving" and cap is not None:
                    guardrail = f"Capped at {money(cap)}. Above the cap, a human must approve."
                    if eligible:
                        guardrail += f" Eligible when payment status is {display_text(eligible)}."
                    guardrail += " A policy citation is required."
                st.write(display_text(tool.get("description"), "Description unavailable."))
                st.caption(guardrail)
                details = {key: value for key, value in tool.items() if key not in {"name", "tier", "description"}}
                if details:
                    st.json(details)
    unknown = [tool for tool in tools if display_text(tool.get("tier"), "") not in TIER_ORDER]
    if unknown:
        st.subheader("Other tools")
        for tool in unknown:
            with st.container(border=True):
                st.write(tool)


def render_customer_chat() -> None:
    st.title("Customer chat")
    st.caption("A minimal demo harness for triggering customer cases.")
    try:
        customers = load_customers()
    except APIError as exc:
        st.error(f"Can't load customers. {exc}")
        return
    customer_by_id = {display_text(customer.get("id")): customer for customer in customers}
    if not customer_by_id:
        st.info("No demo customers are available.")
        return
    customer_ids = list(customer_by_id)
    chosen = st.selectbox(
        "Customer",
        customer_ids,
        format_func=lambda customer_id: f"{display_text(customer_by_id[customer_id].get('name'))} ({customer_id})",
        key="chat_customer_id",
    )
    st.session_state.setdefault("chat_session_id", f"demo-{os.urandom(8).hex()}")
    if st.button("New conversation"):
        import uuid
        st.session_state["chat_session_id"] = str(uuid.uuid4())
        st.session_state["chat_messages"] = []
        st.rerun()
    st.caption(f"Chatting as {display_text(customer_by_id[chosen].get('name'))} ({chosen})")
    for message in st.session_state.get("chat_messages", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("actions"):
                st.caption(" · ".join(
                    f"✓ {display_text(action.get('tool'))} · {display_text(action.get('summary'))}"
                    for action in message["actions"] if isinstance(action, dict)
                ))
            if message.get("citations"):
                st.caption("Policy: " + " · ".join(
                    f"{display_text(citation.get('source'))} › {display_text(citation.get('section'))}"
                    if isinstance(citation, dict) else display_text(citation)
                    for citation in message["citations"]
                ))
            status = message.get("status")
            status_copy = {
                "awaiting_approval": "Sent to a specialist",
                "escalated": "A specialist will follow up",
                "resolved": "This case has been resolved",
            }.get(status)
            if status_copy:
                st.info(status_copy)
    prompt_examples = [
        "₹499 debited for my electricity bill but it failed",
        "₹5000 flight booking failed, money deducted",
        "Someone hacked my account",
        "Is my grocery payment done?",
    ]
    prompt_cols = st.columns(2)
    for index, prompt in enumerate(prompt_examples):
        if prompt_cols[index % 2].button(prompt, key=f"prompt-{index}"):
            st.session_state["chat_prompt"] = prompt
    prompt = st.chat_input("Describe your payment issue")
    if not prompt and st.session_state.get("chat_prompt"):
        prompt = st.session_state.pop("chat_prompt")
    if prompt:
        st.session_state.setdefault("chat_messages", []).append({"role": "user", "content": prompt})
        try:
            if is_preview_mode():
                reply = {"reply": "Preview mode is active. Connect to the backend to run this customer request.", "status": "open"}
            else:
                reply = api_post("/chat", {
                    "session_id": st.session_state["chat_session_id"],
                    "customer_id": chosen,
                    "token": f"demo-{chosen}",
                    "message": prompt,
                })
            answer = display_text(reply.get("reply"), "The assistant returned no reply.")
            st.session_state["chat_messages"].append({
                "role": "assistant",
                "content": answer,
                "actions": reply.get("actions", []),
                "citations": reply.get("citations", []),
                "status": reply.get("status"),
            })
            if reply.get("status") in {"awaiting_approval", "escalated", "resolved"}:
                st.toast({"awaiting_approval": "Sent to a specialist", "escalated": "Sent to a specialist", "resolved": "Case resolved"}[reply["status"]])
        except APIError as exc:
            if "401" in str(exc) or "need_otp" in str(exc):
                st.error("Session expired. Please sign in again.")
            else:
                st.session_state["chat_messages"].pop()
                st.error(f"Message could not be sent. {exc}")
        st.rerun()


ensure_preview_data()
st.session_state.setdefault("preview-mode", os.getenv("USE_MOCK", "0") == "1")

st.sidebar.markdown(
    f'<div class="brand"><span class="brand-mark">R</span><span>{PRODUCT_NAME}</span></div>',
    unsafe_allow_html=True,
)
with st.sidebar:
    st.caption("HUMAN REVIEW CONSOLE")
    st.toggle("Explore with sample data", key="preview-mode")
    customer_names = {}
    try:
        customer_names = {
            display_text(customer.get("id")): display_text(customer.get("name"))
            for customer in load_customers()
        }
    except APIError:
        pass
    st.session_state["customer_names"] = customer_names
    route = st.radio(
        "Workspace",
        ["Queue", "Audit", "Overview", "Tools", "Customer chat"],
        key="active_view",
        label_visibility="collapsed",
    )
    reviewer = st.text_input("Your name", value=st.session_state.get("reviewer_name", "Asha"), key="reviewer_name")
    @st.fragment(run_every="5s")
    def sidebar_live_status():
        try:
            current_cases = load_all_cases()
            st.session_state["last_good_cases"] = current_cases
            live = True
        except APIError:
            current_cases = st.session_state.get("last_good_cases", [])
            live = False
        count = sum(get_case_status(case) == "awaiting_approval" for case in current_cases)
        status_text = "Live" if live else "Offline"
        st.markdown(
            f'<div class="sidebar-footer">● {status_text} · {count} need approval<br>Reviewer: {html.escape(reviewer or "Name required")}</div>',
            unsafe_allow_html=True,
        )
    sidebar_live_status()
    st.divider()
    if is_preview_mode():
        st.caption("Sample actions are simulated locally; no payment is processed.")
    else:
        st.caption("Connected to the configured API.")

if st.session_state.get("confirm_case_id"):
    confirm_approval_dialog()

if route.startswith("Queue"):
    render_queue(customer_names)
elif route == "Audit":
    render_audit_page()
elif route == "Overview":
    render_overview(customer_names)
elif route == "Tools":
    render_tools_page()
else:
    render_customer_chat()
