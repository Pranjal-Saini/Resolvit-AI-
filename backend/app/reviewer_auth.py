"""Local-demo reviewer sessions; access secrets stay in the server environment."""
import hmac
import os
import secrets
import time
from threading import RLock
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

_sessions = {}
_lock = RLock()


def login(name, access_key):
    expected = os.getenv('REVIEWER_ACCESS_KEY', '')
    if not expected:
        raise HTTPException(503, 'Reviewer access is not configured on the server')
    if not hmac.compare_digest(access_key, expected):
        raise HTTPException(401, 'Invalid reviewer access key')
    token = secrets.token_urlsafe(32)
    with _lock:
        now = time.monotonic()
        for old in [key for key, value in _sessions.items() if value[1] <= now]:
            del _sessions[old]
        _sessions[token] = (name, now + 3600)
    return {'access_token':token, 'reviewer':name, 'expires_in':3600}


def require_reviewer(authorization: str | None = Header(default=None)):
    token = authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
    with _lock:
        session = _sessions.get(token)
    if not session or session[1] <= time.monotonic():
        raise HTTPException(401, 'Reviewer sign-in required')
    return session[0]
