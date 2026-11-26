import os
from pathlib import Path

MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB",2048))
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", 5000))
DEFAULT_TTL_MINUTES = int(os.environ.get("DEFAULT_TTL_MINUTES", 120))
MAX_TTL_MINUTES = int(os.environ.get("MAX_TTL_MINUTES", 120))


BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
LOGS_DIR = BASE_DIR / "logs"
DB_DIR = BASE_DIR / "db"
FRONTEND_DIR = BASE_DIR / "static"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = BASE_DIR.parent / "frontend"

DB_PATH = DB_DIR / "pneuma.db"


def init_directories():
    UPLOADS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)