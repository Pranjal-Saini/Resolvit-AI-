"""Server-side login sessions for the local review queue demo."""
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
_sessions = {}
_attempts = {}
_lock = RLock()


def current_reviewer(request):
    token=request.cookies.get(COOKIE,'')
    with _lock:
        value=_sessions.get(token)
    return value[0] if value and value[1]>time.monotonic() else None


def require_reviewer(request: Request):
    name=current_reviewer(request)
    if not name:raise HTTPException(401,'Review queue login required')
    return name


def login(username,password,request,response):
    expected_user=os.getenv('REVIEWER_USERNAME','')
    expected_password=os.getenv('REVIEWER_PASSWORD','')
    if not expected_user or not expected_password:raise HTTPException(503,'Reviewer login is not configured')
    address=request.client.host if request.client else 'local'
    now=time.monotonic()
    with _lock:
        failures=[t for t in _attempts.get(address,[]) if now-t<60]
        if len(failures)>=5:raise HTTPException(429,'Too many attempts. Try again in one minute.')
        if not (hmac.compare_digest(username.encode(),expected_user.encode()) and hmac.compare_digest(password.encode(),expected_password.encode())):
            _attempts[address]=failures+[now]
            raise HTTPException(401,'Incorrect username or password')
        _attempts.pop(address,None)
        for old in [key for key,value in _sessions.items() if value[1]<=now]:_sessions.pop(old,None)
        token=secrets.token_urlsafe(32)
        _sessions[token]=(username,now+3600)
    response.set_cookie(COOKIE,token,max_age=3600,httponly=True,samesite='strict',secure=request.url.scheme=='https',path='/')
    return {'reviewer':username,'expires_in':3600}


def logout(request,response):
    with _lock:_sessions.pop(request.cookies.get(COOKIE,''),None)
    response.delete_cookie(COOKIE,path='/')
    return {'logged_out':True}
