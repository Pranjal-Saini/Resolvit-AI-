from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from pathlib import Path

from backend.app import db, gateway, pii, reviewer_auth
from shared.contracts import AgentResponse, CallContext, ChatRequest, ChatResponse, ToolCall


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="ResolveAI Backend", lifespan=lifespan)

@app.middleware('http')
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


CASE_SCOPE = {
    'agent': "(c.status='escalated' OR c.resolution_type='human_support')",
    'approver': "(c.status IN ('awaiting_approval','resolved','rejected') AND EXISTS (SELECT 1 FROM approvals p WHERE p.case_id=c.id))",
}


def visible_case(case_id, role):
    case = db.fetch_one(f'SELECT c.* FROM cases c WHERE c.id=? AND {CASE_SCOPE[role]}', (case_id,))
    if not case:
        raise HTTPException(404, 'case not found in this workspace')
    return case


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/customers')
def customers(identity: reviewer_auth.Identity = Depends(reviewer_auth.require_staff)):
    return db.fetch_all(f'SELECT DISTINCT u.id,u.name FROM customers u JOIN cases c ON c.customer_id=u.id WHERE {CASE_SCOPE[identity.role]} ORDER BY u.id')


class Review(BaseModel):
    reviewer: str | None = Field(default=None, min_length=1, pattern=r'\S')


class Rejection(Review):
    note: str = Field(min_length=1, pattern=r'\S')


class ReviewerLogin(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@app.post('/review/login')
def review_login(body: ReviewerLogin, request: Request, response: Response):
    return reviewer_auth.login(body.username,body.password,request,response)


@app.get('/review/session')
def review_session(identity: str = Depends(reviewer_auth.require_reviewer)):
    return {'reviewer':identity, 'username':identity, 'role':'approver'}


@app.post('/review/logout')
def review_logout(request: Request, response: Response):
    return reviewer_auth.logout(request,response)


@app.post('/agent/login')
def agent_login(body: ReviewerLogin, request: Request, response: Response):
    return reviewer_auth.login(body.username, body.password, request, response, 'agent')


@app.get('/agent/session')
def agent_session(identity: str = Depends(reviewer_auth.require_agent)):
    return {'username': identity, 'role': 'agent'}


@app.post('/agent/logout')
def agent_logout(request: Request, response: Response):
    return reviewer_auth.logout(request, response, 'agent')


@app.get('/review/queue')
def review_queue(identity: str = Depends(reviewer_auth.require_reviewer)):
    return db.fetch_all(f"SELECT c.id,c.customer_id,u.name AS customer_name,c.status,c.summary,c.created_at FROM cases c JOIN customers u ON u.id=c.customer_id WHERE c.status='awaiting_approval' AND {CASE_SCOPE['approver']} ORDER BY c.created_at")


def get_case(case_id):
    row = db.fetch_one('SELECT * FROM cases WHERE id=?', (case_id,))
    if row is None:
        raise HTTPException(404, 'case not found')
    return row


def append_message(session_id, role, content, case_id):
    masked = pii.mask(content, session_id)
    conn = db.get_conn()
    try:
        with conn:
            history = json.loads(conn.execute('SELECT history_json FROM sessions WHERE id=?', (session_id,)).fetchone()['history_json'])
            history.append({'role': role, 'content': masked})
            conn.execute('UPDATE sessions SET history_json=? WHERE id=?', (json.dumps(history), session_id))
            conn.execute('INSERT INTO case_messages(case_id,role,content,created_at) VALUES(?,?,?,?)', (case_id,role,masked,gateway.now()))
    finally:
        conn.close()


def staff_event(case, actor, action, note):
    db.execute("INSERT INTO audit_log(ts,case_id,actor,tool,tier,args_masked_json,decision,reason) VALUES(?,?,?,?,'staff','{}','executed',?)",
               (gateway.now(),case['id'],actor,action,pii.mask(note,case['session_id'])))


@app.post('/chat', response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.token != 'demo-' + request.customer_id:
        raise HTTPException(401, 'invalid_customer_token')
    with gateway.LOCK:
        if not db.fetch_one('SELECT id FROM customers WHERE id=?', (request.customer_id,)):
            raise HTTPException(404, 'customer not found')
        session = db.fetch_one('SELECT * FROM sessions WHERE id=?', (request.session_id,))
        if session and session['customer_id'] != request.customer_id:
            raise HTTPException(403, 'session belongs to another customer')
        if not session:
            db.execute('INSERT INTO sessions(id,customer_id) VALUES(?,?)', (request.session_id, request.customer_id))
        case = get_case(session['current_case_id']) if session and session['current_case_id'] else None
        if not case or case['status'] not in ('open', 'need_info'):
            conn = db.get_conn()
            try:
                with conn:
                    conn.execute('BEGIN IMMEDIATE')
                    number = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(id,6) AS INTEGER)),0)+1 FROM cases").fetchone()[0]
                    case_id = f'CASE-{number:04d}'
                    conn.execute("INSERT INTO cases(id,session_id,customer_id,status,created_at) VALUES(?,?,?,'open',?)", (case_id, request.session_id, request.customer_id, gateway.now()))
                    conn.execute('UPDATE sessions SET current_case_id=? WHERE id=?', (case_id, request.session_id))
            finally:
                conn.close()
        else:
            case_id = case['id']
        masked = pii.mask(request.message, request.session_id)
        append_message(request.session_id, 'user', masked, case_id)
        history = json.loads(db.fetch_one('SELECT history_json FROM sessions WHERE id=?', (request.session_id,))['history_json'])
        ctx = CallContext(case_id=case_id, session_id=request.session_id, customer_id=request.customer_id)
        try:
            try:
                from engine.agent import run_agent
            except ModuleNotFoundError as exc:
                if exc.name not in ('engine', 'engine.agent'):
                    raise
                def run_agent(message, history, ctx, gateway):
                    return AgentResponse(reply='(stub) received', status='open')
            response = AgentResponse.model_validate(run_agent(masked, history[:-1][-6:], ctx, gateway))
        except Exception:
            response = AgentResponse(reply='Sorry, I could not complete your request. A human will help you.', status='escalated')
        response = AgentResponse.model_validate(pii.mask_obj(response.model_dump(), request.session_id))
        append_message(request.session_id, 'assistant', response.reply, case_id)
        db.execute('UPDATE cases SET status=?,summary=?,resolved_at=?,resolution_type=? WHERE id=?', (response.status, response.case_summary, gateway.now() if response.status == 'resolved' else None, 'auto' if response.status == 'resolved' else None, case_id))
        response.reply = pii.unmask(response.reply, request.session_id)
        return ChatResponse(**response.model_dump(), case_id=case_id)


@app.get('/cases')
def cases(status: str | None = None, identity: reviewer_auth.Identity = Depends(reviewer_auth.require_staff)):
    sql = f'SELECT c.id,c.customer_id,u.name AS customer_name,c.status,c.summary,c.created_at FROM cases c JOIN customers u ON u.id=c.customer_id WHERE {CASE_SCOPE[identity.role]}'
    return db.fetch_all(sql + (' AND c.status=?' if status else '') + ' ORDER BY c.created_at DESC', (status,) if status else ())


@app.get('/audit')
def audit(case_id: str | None = None, identity: reviewer_auth.Identity = Depends(reviewer_auth.require_staff)):
    if case_id:
        visible_case(case_id, identity.role)
    columns = 'a.*' if identity.role == 'approver' else 'a.id,a.ts,a.case_id,a.tool,a.decision,a.reason,a.policy_ref'
    return db.fetch_all(f'SELECT {columns} FROM audit_log a JOIN cases c ON c.id=a.case_id WHERE {CASE_SCOPE[identity.role]}' + (' AND c.id=?' if case_id else '') + ' ORDER BY a.id DESC', (case_id,) if case_id else ())


@app.get('/cases/{case_id}')
def case_detail(case_id: str, identity: reviewer_auth.Identity = Depends(reviewer_auth.require_staff)):
    case = visible_case(case_id, identity.role)
    case['customer_name'] = db.fetch_one('SELECT name FROM customers WHERE id=?', (case['customer_id'],))['name']
    approval = db.fetch_one("SELECT * FROM approvals WHERE case_id=? AND status='pending' ORDER BY id LIMIT 1", (case_id,))
    case['pending_approval'] = approval if identity.role == 'approver' else None
    case['review_requested'] = bool(approval)
    case['audit'] = audit(case_id, identity)
    # Another case in the same session may belong to the other role.
    case['messages'] = db.fetch_all('SELECT role,content,created_at FROM case_messages WHERE case_id=? ORDER BY id', (case_id,))
    case.pop('session_id', None)
    return case


def pending_approval(case_id):
    case = get_case(case_id)
    approval = db.fetch_one("SELECT * FROM approvals WHERE case_id=? AND status='pending' ORDER BY id LIMIT 1", (case_id,))
    if not approval:
        raise HTTPException(409, 'no pending approval')
    return case, approval


@app.post('/cases/{case_id}/approve')
def approve(case_id: str, review: Review, identity: str = Depends(reviewer_auth.require_reviewer)):
    review.reviewer = identity
    with gateway.LOCK:
        visible_case(case_id, 'approver')
        case, approval = pending_approval(case_id)
        ctx = CallContext(case_id=case_id, session_id=case['session_id'], customer_id=case['customer_id'], approved_by=review.reviewer)
        result = gateway.execute(ToolCall(name=approval['tool'], args=json.loads(approval['args_json']), policy_ref=approval['policy_ref']), ctx)
        if result.status == 'ok':
            db.execute("UPDATE approvals SET status='approved',reviewer=? WHERE id=?", (review.reviewer, approval['id']))
            remaining = db.fetch_one("SELECT id FROM approvals WHERE case_id=? AND status='pending'", (case_id,))
            status = 'awaiting_approval' if remaining else 'resolved'
            db.execute('UPDATE cases SET status=?,resolution_type=?,resolved_at=? WHERE id=?', (status, 'human_approved' if not remaining else None, gateway.now() if not remaining else None, case_id))
            message = f"Your refund of ₹{result.data['amount']:g} has been approved and processed. Ref: {result.data['refund_ref']}" if approval['tool'] == 'trigger_reversal' else 'Your requested change has been approved and processed.'
            append_message(case['session_id'], 'assistant', message, case_id)
        return {'case_id': case_id, 'status': get_case(case_id)['status'], 'result': result}


@app.post('/cases/{case_id}/reject')
def reject(case_id: str, review: Rejection, identity: str = Depends(reviewer_auth.require_reviewer)):
    review.reviewer = identity
    with gateway.LOCK:
        visible_case(case_id, 'approver')
        case, approval = pending_approval(case_id)
        db.execute("UPDATE approvals SET status='rejected',reviewer=?,note=? WHERE case_id=? AND status='pending'", (review.reviewer, pii.mask(review.note, case['session_id']), case_id))
        db.execute("UPDATE cases SET status='rejected' WHERE id=?", (case_id,))
        append_message(case['session_id'], 'assistant', 'Sorry, your requested action was not approved. ' + review.note, case_id)
        return {'case_id': case_id, 'status': 'rejected'}


class AgentMessage(Review):
    message: str = Field(min_length=1, pattern=r'\S')


@app.post('/cases/{case_id}/message')
def message_customer(case_id: str, body: AgentMessage, identity: str = Depends(reviewer_auth.require_agent)):
    """A human support agent replies to the customer; shows up in the case conversation."""
    with gateway.LOCK:
        case = visible_case(case_id, 'agent')
        if case['status'] != 'escalated':
            raise HTTPException(409, 'Only escalated conversations accept human replies')
        append_message(case['session_id'], 'assistant', f'[Support · {identity}] {body.message}', case_id)
        staff_event(case,identity,'human_message','Support replied to the customer.')
        return {'case_id': case_id, 'status': case['status']}


@app.post('/cases/{case_id}/request-info')
def request_info(case_id: str, body: Rejection, identity: str = Depends(reviewer_auth.require_reviewer)):
    with gateway.LOCK:
        visible_case(case_id, 'approver')
        case, _ = pending_approval(case_id)
        note = pii.mask(body.note, case['session_id'])
        db.execute("UPDATE cases SET status='escalated',summary=? WHERE id=?", ('Reviewer requested information: ' + note, case_id))
        staff_event(case,identity,'request_information',note)
        return {'case_id': case_id, 'status': 'escalated'}


@app.post('/cases/{case_id}/return-review')
def return_review(case_id: str, body: Rejection, identity: str = Depends(reviewer_auth.require_agent)):
    with gateway.LOCK:
        case = visible_case(case_id, 'agent')
        if case['status'] != 'escalated':
            raise HTTPException(409, 'Case is no longer escalated')
        pending_approval(case_id)
        db.execute("UPDATE cases SET status='awaiting_approval',summary=? WHERE id=?", ('Support information: ' + pii.mask(body.note, case['session_id']), case_id))
        staff_event(case,identity,'return_to_review',body.note)
        return {'case_id': case_id, 'status': 'awaiting_approval'}


@app.post('/cases/{case_id}/resolve')
def resolve_case(case_id: str, body: Rejection, identity: str = Depends(reviewer_auth.require_agent)):
    with gateway.LOCK:
        case = visible_case(case_id, 'agent')
        if case['status'] != 'escalated':
            raise HTTPException(409, 'Case is no longer escalated')
        if db.fetch_one("SELECT id FROM approvals WHERE case_id=? AND status='pending'", (case_id,)):
            raise HTTPException(409, 'Return this case to the approver for its pending decision')
        db.execute("UPDATE cases SET status='resolved',resolution_type='human_support',resolved_at=? WHERE id=?", (gateway.now(), case_id))
        append_message(case['session_id'], 'assistant', f'[Support · {identity}] {body.note}', case_id)
        staff_event(case,identity,'resolve_support_case','Support completed the investigation.')
        return {'case_id': case_id, 'status': 'resolved'}


@app.get('/metrics')
def metrics(identity: reviewer_auth.Identity = Depends(reviewer_auth.require_staff)):
    rows = db.fetch_all(f'SELECT c.status,c.resolution_type FROM cases c WHERE {CASE_SCOPE[identity.role]}')
    return {'total': len(rows), **{status: sum(row['status'] == status for row in rows) for status in ('resolved', 'escalated', 'awaiting_approval')}, 'auto_resolution_rate': sum(row['status'] == 'resolved' and row['resolution_type'] == 'auto' for row in rows) / len(rows) if rows else 0}


@app.get('/tools')
def tools(identity: str = Depends(reviewer_auth.require_reviewer)):
    return gateway.load_registry()


UI_DIR = Path(__file__).resolve().parents[2] / 'ui'


@app.get('/ui/{filename}', include_in_schema=False)
def ui_asset(filename: str, request: Request):
    if filename in ('index.html', 'design-preview.html', 'role-workspace.html'):
        return RedirectResponse('/judges' if request.query_params.get('demo') else '/')
    public = {'access.css', 'login.js'}
    private = {'role-workspace.js', 'demo-scenarios.js'}
    if filename not in public | private:
        raise HTTPException(404, 'asset not found')
    if filename in private:
        # Assets contain no private records; select a valid session even with both tabs signed in.
        if not any(reviewer_auth.current_identity(request, role) for role in reviewer_auth.COOKIES):
            raise HTTPException(401, 'Workspace login required')
    return FileResponse(UI_DIR / filename)


@app.get('/login/{role}', include_in_schema=False)
def login_page(role: str):
    if role not in reviewer_auth.COOKIES:
        raise HTTPException(404, 'workspace not found')
    label = 'Human support' if role == 'agent' else 'Approver'
    html = (UI_DIR / 'login.html').read_text().replace('__ROLE__', role).replace('__LABEL__', label)
    return HTMLResponse(html)


@app.get('/', include_in_schema=False)
def workspace():
    return FileResponse(UI_DIR / 'login-choice.html')


def role_workspace(request, role):
    if not reviewer_auth.current_identity(request, role):
        return RedirectResponse('/login/' + role + ('?demo=1' if request.query_params.get('demo') else ''))
    label = 'Human support' if role == 'agent' else 'Approver'
    html = (UI_DIR / 'role-workspace.html').read_text().replace('__ROLE__', role).replace('__LABEL__', label)
    return HTMLResponse(html)


@app.get('/agent', include_in_schema=False)
def agent_dashboard(request: Request):
    return role_workspace(request, 'agent')


@app.get('/judges', include_in_schema=False)
def judges_dashboard(request: Request):
    selected = request.query_params.get('role')
    if selected not in reviewer_auth.COOKIES:
        return RedirectResponse('/?judges=1')
    return RedirectResponse(('/agent' if selected == 'agent' else '/review') + '?demo=1')


@app.get('/review', include_in_schema=False)
def reviewer_dashboard(request: Request):
    return role_workspace(request, 'approver')
