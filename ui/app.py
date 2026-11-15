"""ResolveAI UI: customer chat + support dashboard. Run: streamlit run ui/app.py  (backend at API_BASE)"""
import json
import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
BADGE = {"resolved": "green", "awaiting_approval": "orange", "escalated": "red", "rejected": "gray",
         "need_info": "blue", "open": "blue"}
AUDIT_COLS = ["ts", "case_id", "actor", "tool", "tier", "decision", "reason", "policy_ref"]


def api(method, path, **kw):
    try:
        r = requests.request(method, API + path, timeout=180, **kw)
    except requests.ConnectionError:
        st.error(f"Backend unreachable at {API}. Start it with: python -m uvicorn backend.app.main:app --port 8000")
        st.stop()
    if not r.ok:
        st.error(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


@st.cache_data(ttl=60)
def tool_tiers():
    try:
        reg = requests.get(API + "/tools", timeout=10).json()
        return {t["name"]: t["tier"] for t in reg.get("tools", [])}
    except Exception:
        return {}


def badge(status):
    st.badge(status.replace("_", " "), color=BADGE.get(status, "gray"))


def flash(msg):
    st.session_state.flash = msg
    st.rerun()


# ---------------------------------------------------------------- customer chat
def agent_details(resp):
    badge(resp["status"])
    if resp["actions"] or resp["citations"]:
        with st.expander("Actions taken & policy cited"):
            for a in resp["actions"]:
                st.markdown(f"- `{a['tool']}` → **{a['status']}**  \n  <small>{a['summary']}</small>", unsafe_allow_html=True)
            for c in resp["citations"]:
                st.markdown(f"**{c['source']}#{c['section']}** · score {c['score']:.2f}"
                            + (" · low confidence" if c["low_confidence"] else ""))
                st.caption(c["rule_text"])


def customer_chat():
    customers = api("GET", "/customers") or []
    names = {c["id"]: f"{c['id']} · {c['name']}" for c in customers}
    with st.sidebar:
        cid = st.selectbox("Customer", list(names), format_func=names.get)
        new = st.button("New conversation", width="stretch")
    if new or st.session_state.get("chat_cid") != cid:
        st.session_state.update(chat_cid=cid, chat_sid=f"ui-{uuid.uuid4().hex[:8]}", chat=[], chat_case=None)

    st.title("Paytm Help")
    st.caption(f"Signed in as {names.get(cid, cid)} · session `{st.session_state.chat_sid}`")
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("resp"):
                agent_details(m["resp"])

    if st.session_state.chat_case and st.button("Check for updates from support"):
        case = api("GET", f"/cases/{st.session_state.chat_case}")
        if case:  # approvals and support replies are appended to the session server-side
            st.session_state.chat += [{"role": m["role"], "content": m["content"]}
                                      for m in case["messages"][len(st.session_state.chat):]]
            st.rerun()

    if prompt := st.chat_input("Describe your payment issue"):
        with st.chat_message("user"):
            st.write(prompt)
        with st.spinner("ResolveAI is checking your account…"):
            resp = api("POST", "/chat", json={"session_id": st.session_state.chat_sid, "customer_id": cid,
                                              "token": f"demo-{cid}", "message": prompt})
        if resp:
            st.session_state.chat += [{"role": "user", "content": prompt},
                                      {"role": "assistant", "content": resp["reply"], "resp": resp}]
            st.session_state.chat_case = resp["case_id"]
            st.rerun()


# ---------------------------------------------------------------- support dashboard
def audit_table(rows):
    if rows:
        st.dataframe([{c: r.get(c) for c in AUDIT_COLS} for r in rows], hide_index=True, width="stretch")
    else:
        st.caption("No tool calls logged.")


def case_card(case_id, reviewer, actions=False, where="q"):
    case = api("GET", f"/cases/{case_id}")
    if not case:
        return
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(f"**{case['id']}** · customer `{case['customer_id']}` · {case['created_at'][:19]}")
        with top[1]:
            badge(case["status"])
        if case.get("summary"):
            st.markdown("**Case summary**")
            st.text(case["summary"])
        pending = case.get("pending_approval")
        if pending:
            args = json.loads(pending["args_json"])
            st.markdown("**Pending action**")
            cols = st.columns(3)
            cols[0].metric("Tool", pending["tool"])
            cols[1].metric("Amount", f"₹{args['amount']:,.0f}" if "amount" in args else "—")
            cols[2].metric("Transaction", args.get("txn_id", "—"))
            st.caption(f"Policy cited: `{pending.get('policy_ref') or 'none'}` · args: `{args}`")
        with st.expander("Conversation"):
            for m in case.get("messages", []):
                with st.chat_message(m["role"]):
                    st.write(m["content"])
        with st.expander(f"Audit trail ({len(case.get('audit', []))} tool calls)"):
            audit_table(case.get("audit", []))

        if actions and pending:
            # The gateway deliberately refuses reviewer approval for sensitive tools: the customer must pass step-up.
            sensitive = tool_tiers().get(pending["tool"]) == "sensitive"
            if sensitive:
                st.warning("Sensitive change: needs the customer's step-up verification (OTP). Reviewer approval "
                           "cannot execute it. Reject it, or message the customer to verify.")
            note = st.text_input("Rejection note (required to reject)", key=f"note-{where}-{case_id}")
            a, b = st.columns(2)
            if a.button("Approve", key=f"ok-{where}-{case_id}", type="primary", width="stretch", disabled=sensitive):
                res = api("POST", f"/cases/{case_id}/approve", json={"reviewer": reviewer})
                if res:
                    r = res["result"]
                    flash(f"{case_id}: {r['status']}" + (f" — {r.get('reason')}" if r.get("reason") else "")
                          + f" → case {res['status']}")
            if b.button("Reject", key=f"no-{where}-{case_id}", width="stretch", disabled=not note.strip()):
                if api("POST", f"/cases/{case_id}/reject", json={"reviewer": reviewer, "note": note}):
                    flash(f"{case_id}: rejected")

        with st.expander("Message customer"):
            text = st.text_area("Reply", key=f"msg-{where}-{case_id}", label_visibility="collapsed",
                                placeholder="Write to the customer…")
            if st.button("Send", key=f"send-{where}-{case_id}", disabled=not text.strip()):
                if api("POST", f"/cases/{case_id}/message", json={"reviewer": reviewer, "message": text}):
                    flash(f"{case_id}: message sent to customer")


def dashboard():
    with st.sidebar:
        reviewer = st.text_input("Reviewer name", "support-agent-1").strip() or "support-agent-1"
        st.button("Refresh", width="stretch")

    m = api("GET", "/metrics") or {}
    cols = st.columns(5)
    cols[0].metric("Total cases", m.get("total", 0))
    cols[1].metric("Auto-resolution", f"{m.get('auto_resolution_rate', 0):.0%}")
    cols[2].metric("Resolved", m.get("resolved", 0))
    cols[3].metric("Awaiting approval", m.get("awaiting_approval", 0))
    cols[4].metric("Escalated", m.get("escalated", 0))

    queue = api("GET", "/cases", params={"status": "awaiting_approval"}) or []
    escalated = api("GET", "/cases", params={"status": "escalated"}) or []
    t_queue, t_esc, t_all, t_audit, t_tools = st.tabs(
        [f"Review queue ({len(queue)})", f"Escalated ({len(escalated)})", "All cases", "Audit log", "Tool registry"])

    with t_queue:
        if not queue:
            st.info("No cases waiting for approval.")
        for c in queue:
            case_card(c["id"], reviewer, actions=True)

    with t_esc:
        if not escalated:
            st.info("No escalated cases.")
        for c in escalated:
            case_card(c["id"], reviewer, where="esc")

    with t_all:
        status = st.selectbox("Status", ["all", *BADGE])
        rows = api("GET", "/cases", params=None if status == "all" else {"status": status}) or []
        st.dataframe(rows, hide_index=True, width="stretch")
        if rows:
            pick = st.selectbox("Open case", [r["id"] for r in rows])
            case_card(pick, reviewer, actions=True, where="all")

    with t_audit:
        case_filter = st.text_input("Filter by case id (e.g. CASE-0001)").strip()
        audit_table(api("GET", "/audit", params={"case_id": case_filter} if case_filter else None) or [])

    with t_tools:
        reg = api("GET", "/tools") or {}
        st.dataframe([{"name": t["name"], "tier": t["tier"], "cap_inr": t.get("cap_inr"),
                       "eligible_status": ", ".join(t.get("eligible_status", [])), "description": t.get("description")}
                      for t in reg.get("tools", [])], hide_index=True, width="stretch")


st.set_page_config(page_title="ResolveAI", page_icon="🛟", layout="wide")
page = st.navigation([st.Page(customer_chat, title="Customer chat", icon="💬"),
                      st.Page(dashboard, title="Support dashboard", icon="🛟")])
with st.sidebar:
    st.caption(f"Backend: {API}")
if msg := st.session_state.pop("flash", None):
    st.success(msg)
page.run()
