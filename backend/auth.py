import secrets
import hashlib
from datetime import datetime
from db import insert_session_to_db

SESSION_DAYS = 7

def get_current_user() -> str:
    return "default"

def create_session(user_id, conn):
    rand_token = secrets.token_urlsafe(32)
    # turn text to bytes, hash it (sha256), return 64char str
    token_hash = hashlib.sha256(rand_token.encode()).hexdigest()
    now = int(datetime.now().timestamp())
    expires_at = now + (SESSION_DAYS * 86400)
    
    insert_session_to_db(user_id, token_hash, expires_at, conn)
    # return raw token
    return rand_token