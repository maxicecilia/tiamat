"""Runtime settings for the Tiamat API, read from the environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TIAMAT_DATA_DIR", ROOT_DIR / "data"))
DATABASE_URL = os.getenv("TIAMAT_DATABASE_URL", f"sqlite:///{DATA_DIR / 'tiamat.db'}")
CORS_ORIGINS = [
    o for o in os.getenv("TIAMAT_CORS_ORIGINS", "http://localhost:5173").split(",") if o
]
ALLOWED_HOSTS = [
    h for h in os.getenv("TIAMAT_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h
]
