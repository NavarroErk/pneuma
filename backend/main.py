from fastapi import FastAPI, Depends, HTTPException, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from typing import Literal
from datetime import datetime
import os
import uuid
import mimetypes
import asyncio

from config import init_directories, MAX_FILE_SIZE_MB, MAX_TEXT_LENGTH, DEFAULT_TTL_MINUTES, MAX_TTL_MINUTES, UPLOADS_DIR, FRONTEND_DIR
from db import init_db, get_db, cleanup_loop, cleanup_expired
from auth import get_current_user
from pathlib import Path



@asynccontextmanager
async def lifespan(app:FastAPI):
    init_directories()
    init_db()
    get_current_user()

    task = asyncio.create_task(cleanup_loop())
    
    yield
    # shutdown logic (as necessary)
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def get_health():
  return {"status": "ok"}

@app.get("/config")
def get_config():
  return {
    "max_file_size_mb": MAX_FILE_SIZE_MB,
    "max_text_length": MAX_TEXT_LENGTH,
    "default_ttl_minutes": DEFAULT_TTL_MINUTES,
    "max_ttl_minutes": MAX_TTL_MINUTES
  }

@app.get("/entries")
def get_entries(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
  rows = conn.execute("""
      SELECT id, type, name, mime_type, size, created_at, expires_at
      FROM entries WHERE user_id = ? AND expires_at > ? ORDER BY created_at DESC
    """, [user_id, int(datetime.now().timestamp())]).fetchall()
  return rows
  
@app.get("/entries/{entry_id}")
def get_entry_by_id(entry_id: str, user_id: str = Depends(get_current_user), conn = Depends(get_db)):
  row = conn.execute("""
    SELECT *
    FROM entries WHERE id = ? AND user_id = ? AND expires_at > ?
  """, [entry_id, user_id, int(datetime.now().timestamp())]).fetchone()
  
  # No entry exists for this entry_id
  if not row:
    raise HTTPException(status_code=404, detail="Entry not found")
  
  if row["type"] == "file":
    file_path = UPLOADS_DIR / row["id"]
    
    if file_path.exists():
      # nosniff tells browser to use the type as given
      return FileResponse(file_path, filename=row["name"], media_type=row["mime_type"],
                          headers={"X-Content-Type-Options": "nosniff"})
    else:
      raise HTTPException(status_code=404, detail="Entry not found. Was it removed?")
  elif row["type"] == "text":
    return row["text_content"]
  
  raise HTTPException(status_code=500, detail="Invalid entry type")
    

@app.post("/entries")
async def post_entries(
  type: Literal["text", "file"] = Form(...),
  file: UploadFile | None = File(None),
  text: str | None = Form(None),
  user_id: str = Depends(get_current_user),
  conn = Depends(get_db)
  ):
  
  entry_id = str(uuid.uuid4())
  mime_type = None
  stored_path = None
  size = None
  text_content = None
  name = None
  
  if type == "file":
    if file is None:
      raise HTTPException(400, "No file provided")
    
    stored_path = str(UPLOADS_DIR / entry_id)
    size = 0
    name = file.filename or "untitled"
    # work out the filetype from the file name, else use fallback
    mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    
    too_big = False
    # read file against size limit and write to disk in chunks
    with open(stored_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                too_big = True
                break
            f.write(chunk)
    if too_big:
        os.remove(stored_path)
        raise HTTPException(413, f"File too large. Maximum Size: {MAX_FILE_SIZE_MB}MB")
      
  elif type == "text":
      # form uploads turn \n into \r\n to avoid extra invis chars
      text = (text or "").replace("\r\n", "\n")
      if not text:
          raise HTTPException(400, "No text provided")
      if len(text) > MAX_TEXT_LENGTH:
          raise HTTPException(413, f"Text too long. Maximum: {MAX_TEXT_LENGTH} characters")
      text_content = text
      size = len(text)
      name = text[0:75]
        
  now = int(datetime.now().timestamp())
  created_at = now
  expires_at = (now + (DEFAULT_TTL_MINUTES * 60))
  

  try:
    conn.execute("""
      INSERT INTO entries (id, user_id, type, name, mime_type, stored_path, text_content, size, created_at, expires_at)
      VALUES (:id, :user_id, :type, :name, :mime_type, :stored_path, :text_content, :size, :created_at, :expires_at)
    """, {
      "id": entry_id,
      "user_id": user_id,
      "type": type,
      "name": name,
      "mime_type": mime_type,
      "stored_path": stored_path,
      "text_content": text_content,
      "size": size,
      "created_at": created_at,
      "expires_at": expires_at,
    })
    conn.commit()
  
  except Exception:
    if stored_path:
      os.remove(stored_path)
    raise

  return {"id": entry_id}

@app.delete("/entries/{entry_id}", status_code=204)
def delete_entry_by_id(entry_id: str, user_id: str = Depends(get_current_user), conn = Depends(get_db)):
  row = conn.execute("""
    SELECT id, type FROM entries WHERE id = ? AND user_id = ?
  """, [entry_id, user_id]).fetchone()

  if row is None:
    raise HTTPException(status_code=404, detail="Entry not found")

  # remove the file from disk; skips quietly if it's already gone
  if row["type"] == "file":
    (UPLOADS_DIR / entry_id).unlink(missing_ok=True)

  conn.execute("DELETE FROM entries WHERE id = ?", [entry_id])
  conn.commit()
  
@app.delete("/entries", status_code=204)
def delete_entries(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
  files = conn.execute(
    "SELECT id FROM entries WHERE user_id = ? AND type = 'file'", [user_id]
  ).fetchall()
  for f in files:
    (UPLOADS_DIR / f["id"]).unlink(missing_ok=True)

  conn.execute("DELETE FROM entries WHERE user_id = ?", [user_id])
  conn.commit()
  

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True))