from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app import db, gateway, pii, reviewer_auth
from shared.contracts import AgentResponse, CallContext, ChatRequest, ChatResponse, ToolCall


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="ResolveAI Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/customers')
def customers():
    return db.fetch_all('SELECT id, name FROM customers ORDER BY id')


class Review(BaseModel):
    reviewer: str = Field(min_length=1, pattern=r'\S')


class Rejection(Review):
    note: str = Field(min_length=1)


class ReviewerLogin(BaseModel):
    reviewer: str = Field(min_length=1, pattern=r'\S')
    access_key: str = Field(min_length=1)


@app.post('/reviewer/login')
def reviewer_login(body: ReviewerLogin):
    return reviewer_auth.login(body.reviewer, body.access_key)


def get_case(case_id):
    row = db.fetch_one('SELECT * FROM cases WHERE id=?', (case_id,))
    if row is None:
        raise HTTPException(404, 'case not found')
    return row


def append_message(session_id, role, content):
    session = db.fetch_one('SELECT history_json FROM sessions WHERE id=?', (session_id,))
    history = json.loads(session['history_json'])
    history.append({'role': role, 'content': pii.mask(content, session_id)})
    db.execute('UPDATE sessions SET history_json=? WHERE id=?', (json.dumps(history), session_id))


@app.post('/chat', response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.token != 'demo-' + request.customer_id:
        raise HTTPException(401, 'need_otp')
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
        append_message(request.session_id, 'user', masked)
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
        append_message(request.session_id, 'assistant', response.reply)
        db.execute('UPDATE cases SET status=?,summary=?,resolved_at=?,resolution_type=? WHERE id=?', (response.status, response.case_summary, gateway.now() if response.status == 'resolved' else None, 'auto' if response.status == 'resolved' else None, case_id))
        response.reply = pii.unmask(response.reply, request.session_id)
        return ChatResponse(**response.model_dump(), case_id=case_id)


@app.get('/cases')
def cases(status: str | None = None):
    sql = 'SELECT id,customer_id,status,summary,created_at FROM cases'
    return db.fetch_all(sql + (' WHERE status=?' if status else '') + ' ORDER BY created_at DESC', (status,) if status else ())


@app.get('/audit')
def audit(case_id: str | None = None):
    return db.fetch_all('SELECT * FROM audit_log' + (' WHERE case_id=?' if case_id else '') + ' ORDER BY id DESC', (case_id,) if case_id else ())


@app.get('/cases/{case_id}')
def case_detail(case_id: str):
    case = get_case(case_id)
    case['pending_approval'] = db.fetch_one("SELECT * FROM approvals WHERE case_id=? AND status='pending' ORDER BY id LIMIT 1", (case_id,))
    case['audit'] = audit(case_id)
    case['messages'] = json.loads(db.fetch_one('SELECT history_json FROM sessions WHERE id=?', (case['session_id'],))['history_json'])
    return case


def pending_approval(case_id):
    case = get_case(case_id)
    approval = db.fetch_one("SELECT * FROM approvals WHERE case_id=? AND status='pending' ORDER BY id LIMIT 1", (case_id,))
    if not approval:
        raise HTTPException(409, 'no pending approval')
    return case, approval


@app.post('/cases/{case_id}/approve')
def approve(case_id: str, review: Review, identity: str = Depends(reviewer_auth.require_reviewer)):
    if review.reviewer != identity:
        raise HTTPException(403, 'Reviewer identity mismatch')
    with gateway.LOCK:
        case, approval = pending_approval(case_id)
        ctx = CallContext(case_id=case_id, session_id=case['session_id'], customer_id=case['customer_id'], approved_by=review.reviewer)
        result = gateway.execute(ToolCall(name=approval['tool'], args=json.loads(approval['args_json']), policy_ref=approval['policy_ref']), ctx)
        if result.status == 'ok':
            db.execute("UPDATE approvals SET status='approved',reviewer=? WHERE id=?", (review.reviewer, approval['id']))
            remaining = db.fetch_one("SELECT id FROM approvals WHERE case_id=? AND status='pending'", (case_id,))
            status = 'awaiting_approval' if remaining else 'resolved'
            db.execute('UPDATE cases SET status=?,resolution_type=?,resolved_at=? WHERE id=?', (status, 'human_approved' if not remaining else None, gateway.now() if not remaining else None, case_id))
            message = f"Your refund of ₹{result.data['amount']:g} has been approved and processed. Ref: {result.data['refund_ref']}" if approval['tool'] == 'trigger_reversal' else 'Your requested change has been approved and processed.'
            append_message(case['session_id'], 'assistant', message)
        return {'case_id': case_id, 'status': get_case(case_id)['status'], 'result': result}


@app.post('/cases/{case_id}/reject')
def reject(case_id: str, review: Rejection, identity: str = Depends(reviewer_auth.require_reviewer)):
    if review.reviewer != identity:
        raise HTTPException(403, 'Reviewer identity mismatch')
    with gateway.LOCK:
        case, approval = pending_approval(case_id)
        db.execute("UPDATE approvals SET status='rejected',reviewer=?,note=? WHERE case_id=? AND status='pending'", (review.reviewer, pii.mask(review.note, case['session_id']), case_id))
        db.execute("UPDATE cases SET status='rejected' WHERE id=?", (case_id,))
        append_message(case['session_id'], 'assistant', 'Sorry, your requested action was not approved. ' + review.note)
        return {'case_id': case_id, 'status': 'rejected'}


class AgentMessage(Review):
    message: str = Field(min_length=1, pattern=r'\S')


@app.post('/cases/{case_id}/message')
def message_customer(case_id: str, body: AgentMessage, identity: str = Depends(reviewer_auth.require_reviewer)):
    if body.reviewer != identity:
        raise HTTPException(403, 'Reviewer identity mismatch')
    """A human support agent replies to the customer; shows up in the case conversation."""
    with gateway.LOCK:
        case = get_case(case_id)
        append_message(case['session_id'], 'assistant', f'[Support · {body.reviewer}] {body.message}')
        return {'case_id': case_id, 'status': case['status']}


@app.get('/metrics')
def metrics():
    rows = db.fetch_all('SELECT status,resolution_type FROM cases')
    return {'total': len(rows), **{status: sum(row['status'] == status for row in rows) for status in ('resolved', 'escalated', 'awaiting_approval')}, 'auto_resolution_rate': sum(row['status'] == 'resolved' and row['resolution_type'] == 'auto' for row in rows) / len(rows) if rows else 0}


@app.get('/tools')
def tools():
    return gateway.load_registry()


# Serve the support workspace alongside the API, with no separate frontend server.
UI_DIR = Path(__file__).resolve().parents[2] / 'ui'
app.mount('/ui', StaticFiles(directory=UI_DIR), name='ui')


@app.get('/', include_in_schema=False)
def workspace():
    return FileResponse(UI_DIR / 'index.html')
