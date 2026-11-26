import time

import main
import db
import sqlite3

# helper - upload text and return the response
def post_text(client, text, **extra):
    return client.post("/entries", data={"type": "text", "text": text, **extra})


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_text_upload_shows_in_list(client):
    # add entry, confirm 200, confirm the list holds only that entry, confirm fetching it returns the same text
    res = post_text(client, "test text")
    assert res.status_code == 200
    entry_id = res.json()["id"]

    entries = client.get("/entries").json()
    assert [e["id"] for e in entries] == [entry_id]
    assert client.get(f"/entries/{entry_id}").json() == "test text"


def test_empty_text_is_rejected(client):
    assert post_text(client, "   ").status_code == 400


def test_text_too_long_is_rejected(client, monkeypatch):
    # set custom max length, confirm status codes on input entry length
    monkeypatch.setattr(main, "MAX_TEXT_LENGTH", 5)
    assert post_text(client, "12345").status_code == 200
    assert post_text(client, "123456").status_code == 413


def test_newline_counts_as_one_character(client, monkeypatch):
    # browsers send Enter as \r\n; server should count it as one character
    monkeypatch.setattr(main, "MAX_TEXT_LENGTH", 5)
    assert post_text(client, "test\r\n").status_code == 200
    assert client.get("/entries").json()[0]["size"] == 5


def test_custom_ttl_sets_expiry(client):
    # add entry with custom TTL, confirm TTL within 5sec (buffer) of 10min from now
    post_text(client, "test text", ttl_minutes=10)
    entry = client.get("/entries").json()[0]
    assert abs(entry["expires_at"] - (time.time() + 10 * 60)) < 5


def test_ttl_out_of_range_is_rejected(client):
    # confirm inability to set TTL below min and above max
    assert post_text(client, "test text", ttl_minutes=0).status_code == 422
    assert post_text(client, "test text", ttl_minutes=main.MAX_TTL_MINUTES + 1).status_code == 422


def test_file_upload_and_download(client):
    # add file entry, retrieve same entry, confirm success code and matching contents
    res = client.post(
        "/entries",
        data={"type": "file"},
        files={"file": ("note.txt", b"file contents")},
    )
    entry_id = res.json()["id"]

    download = client.get(f"/entries/{entry_id}")
    assert download.status_code == 200
    assert download.content == b"file contents"


def test_file_too_large_is_rejected(client, monkeypatch):
    # any non-empty file is too big
    monkeypatch.setattr(main, "MAX_FILE_SIZE_MB", 2) # temp limit=0 
    res = client.post(
        "/entries",
        data={"type": "file"},
        files={"file": ("file.txt", b"xxx" * (1024 * 1024))}, # 3 MB
    )
    assert res.status_code == 413
    assert client.get("/entries").json() == []

def test_entry_is_expired(client):
    # add entry, update expiry, confirm that the entry is deleted
    entry_id = post_text(client, "test text", ttl_minutes=1).json()["id"]
    
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute("UPDATE entries SET expires_at = 0 WHERE id = ?", [entry_id])

    assert client.get("/entries").json() == []
    assert client.get(f"/entries/{entry_id}").status_code == 404


def test_delete_entry(client):
    # add entry, delete entry, confirm deletion
    entry_id = post_text(client, "test text").json()["id"]

    assert client.delete(f"/entries/{entry_id}").status_code == 204
    assert client.get("/entries").json() == []


