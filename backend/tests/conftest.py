import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    # A test client with its own empty database and uploads folder. tmp_path is a temp folder pytest makes for each test; temporarily redirect paths
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)

    # run the app's startup (create the table) and shutdown
    with TestClient(main.app) as c:
        yield c
