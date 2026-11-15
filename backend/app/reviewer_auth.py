"""Separate server-side sessions for support agents and approvers."""
from dataclasses import dataclass
import hmac
import os
import secrets
import time
from pathlib import Path
from threading import RLock

from dotenv import load_dotenv
from fastapi import HTTPException, Request

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
COOKIE = 'resolveai_reviewer'
COOKIES = {'agent': 'resolveai_agent', 'approver': COOKIE}
CONFIG = {'agent': 'AGENT', 'approver': 'REVIEWER'}
_sessions = {}
_attempts = {}
_lock = RLock()


@dataclass(frozen=True)
class Identity:
    username: str
    role: str


def current_identity(request, role):
    token = request.cookies.get(COOKIES[role], '')
    with _lock:
        value = _sessions.get(token)
        if value and value[1] <= time.monotonic():
            _sessions.pop(token, None)
            value = None
    if value and len(value) == 3 and value[2] == role:
        return Identity(value[0], role)
    return None


def current_reviewer(request):
    identity = current_identity(request, 'approver')
    return identity.username if identity else None


def require_role(request, role):
    selected = request.headers.get('X-Workspace-Role')
    if selected and selected != role:
        raise HTTPException(403, 'This action is not available in your workspace')
    identity = current_identity(request, role)
    if not identity:
        other = 'agent' if role == 'approver' else 'approver'
        if current_identity(request, other):
            raise HTTPException(403, 'Sign in with the account for this workspace')
        raise HTTPException(401, 'Workspace login required')
    return identity


def require_reviewer(request: Request):
    return require_role(request, 'approver').username


def require_agent(request: Request):
    return require_role(request, 'agent').username


def require_staff(request: Request):
    selected = request.headers.get('X-Workspace-Role')
    if selected:
        if selected not in COOKIES:
            raise HTTPException(400, 'Unknown workspace role')
        return require_role(request, selected)
    identities = [value for role in COOKIES if (value := current_identity(request, role))]
    if not identities:
        raise HTTPException(401, 'Workspace login required')
    if len(identities) != 1:
        raise HTTPException(400, 'Select X-Workspace-Role for this request')
    return identities[0]


def login(username, password, request, response, role='approver'):
    prefix = CONFIG[role]
    expected_user = os.getenv(prefix + '_USERNAME', '')
    expected_password = os.getenv(prefix + '_PASSWORD', '')
    other_prefix = CONFIG['agent' if role == 'approver' else 'approver']
    if not expected_user or not expected_password:
        raise HTTPException(503, 'Workspace login is not configured')
    if expected_user == os.getenv(other_prefix + '_USERNAME', ''):
        raise HTTPException(503, 'Agent and approver must have different usernames')
    address = request.client.host if request.client else 'local'
    attempt_key = (role, address)
    now = time.monotonic()
    with _lock:
        failures = [t for t in _attempts.get(attempt_key, []) if now-t < 60]
        if len(failures) >= 5:
            raise HTTPException(429, 'Too many attempts. Try again in one minute.')
        if not (hmac.compare_digest(username.encode(), expected_user.encode()) and
                hmac.compare_digest(password.encode(), expected_password.encode())):
            _attempts[attempt_key] = failures + [now]
            raise HTTPException(401, 'Incorrect username or password for this workspace')
        _attempts.pop(attempt_key, None)
        for old in [key for key, value in _sessions.items() if value[1] <= now]:
            _sessions.pop(old, None)
        _sessions.pop(request.cookies.get(COOKIES[role], ''), None)
        token = secrets.token_urlsafe(32)
        _sessions[token] = (username, now+3600, role)
    response.set_cookie(COOKIES[role], token, max_age=3600, httponly=True,
                        samesite='strict', secure=request.url.scheme == 'https', path='/')
    return {'username': username, 'reviewer': username, 'role': role, 'expires_in': 3600}


def logout(request, response, role='approver'):
    with _lock:
        _sessions.pop(request.cookies.get(COOKIES[role], ''), None)
    response.delete_cookie(COOKIES[role], path='/')
    return {'logged_out': True}
