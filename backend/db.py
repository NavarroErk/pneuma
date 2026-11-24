import sqlite3
import asyncio
from datetime import datetime
from contextlib import closing
from config import DB_PATH, UPLOADS_DIR



def init_db():
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
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
                expires_at INTEGER NOT NULL
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
        conn.row_factory = sqlite3.Row

        # delete expired files from disk
        files = conn.execute(
            "SELECT id FROM entries WHERE type = 'file' AND expires_at <= ?", [now]
        ).fetchall()
        for f in files:
            (UPLOADS_DIR / f["id"]).unlink(missing_ok=True)

        # delete all expired rows
        conn.execute("DELETE FROM entries WHERE expires_at <= ?", [now])
        conn.commit()