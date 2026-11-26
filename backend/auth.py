from fastapi import Header, Depends, HTTPException
import secrets
import hashlib
from datetime import datetime
from db import get_db, insert_session_to_db, select_session_by_token_hash

SESSION_DAYS = 7

def hash_token(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token_hash

def get_current_user(
    authorization: str | None = Header(None),
    conn = Depends(get_db)
):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")
    
    raw_token = authorization[7:]
    # hash the token with SHA-256
    token_hash = hash_token(raw_token)
    # find session with the hash and expires_at > now 
    now = int(datetime.now().timestamp())
    session = select_session_by_token_hash(token_hash, now, conn)
    # if none raise 401, else return user_id
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired")

    return session["user_id"]

def create_session(user_id, conn):
    rand_token = secrets.token_urlsafe(32)
    # turn text to bytes, hash it (sha256), return 64char str
    token_hash = hash_token(rand_token)
    now = int(datetime.now().timestamp())
    expires_at = now + (SESSION_DAYS * 86400)
    
    insert_session_to_db(user_id, token_hash, expires_at, conn)
    # return raw token
    return rand_token