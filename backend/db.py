import sqlite3
import asyncio
from datetime import datetime
from contextlib import closing
from config import DB_PATH, UPLOADS_DIR



def init_db():
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                )
                """)
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                mime_type TEXT,
                stored_path TEXT,
                text_content TEXT, 
                size INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT NOT NULL,
                token_hash TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)
            conn.commit()
            
    except sqlite3.OperationalError as e:
        print("Failed to open database:", e)
        raise

def get_db():
    try:
        # (=False) -> allow use across threads (sync dependency, async endpoint); one request per connection 
        with closing(sqlite3.connect(DB_PATH, check_same_thread=False)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            yield conn
            
    except sqlite3.OperationalError as e:
        print("Database error:", e)
        raise
    
    
async def cleanup_loop():
    while True:
        try:
            cleanup_expired()
        except Exception as e:
            print("Cleanup failed:", e)
        await asyncio.sleep(30)
    
def cleanup_expired():
    now = int(datetime.now().timestamp())
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row

        # delete expired files from disk
        files = conn.execute(
            "SELECT id FROM entries WHERE type = 'file' AND expires_at <= ?", [now]
        ).fetchall()
        for f in files:
            (UPLOADS_DIR / f["id"]).unlink(missing_ok=True)

        # delete all expired rows
        conn.execute("DELETE FROM entries WHERE expires_at <= ?", [now])
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", [now])
        conn.commit()

def db_has_users(conn):
    return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None        

def setup_admin(user_id: str, username: str, password_hash: str, role: str, conn):
    # insert conditional on check whether a single user exists
    cursor = conn.execute("""
       INSERT INTO users (id, username, password_hash, role)
       SELECT ?, ?, ?, ?
       WHERE NOT EXISTS (SELECT 1 FROM users)
    """, [user_id, username, password_hash, role])
    conn.commit()
    return cursor.rowcount == 1

def insert_session_to_db(user_id, token_hash, expires_at, conn):
    conn.execute("""
       INSERT INTO sessions (user_id, token_hash, expires_at)
       VALUES (?, ?, ?)
    """, [user_id, token_hash, expires_at])
    conn.commit()
    

def select_user_by_username(username: str, conn):
    return conn.execute("""
       SELECT id, password_hash, role
       FROM users
       WHERE username = ?
    """, [username]).fetchone()