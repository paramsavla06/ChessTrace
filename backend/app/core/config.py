"""
Application configuration settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
env_path = BASE_DIR / "backend/.env"
if not env_path.exists():
    env_path = BASE_DIR / ".env"
load_dotenv(env_path)

PROJECT_NAME: str = "ChessTrace"
API_V1_STR: str = "/api/v1"

_db_url = os.getenv("DATABASE_URL", "sqlite:///./chesstrace.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL: str = _db_url
STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "./stockfish_bin")
LICHESS_API_TOKEN: str = os.getenv("LICHESS_API_TOKEN", "")

_extra_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

BACKEND_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "https://chess-trace.vercel.app",
    "https://chesstrace.onrender.com",
    os.getenv("FRONTEND_URL", ""),
    *_extra_origins,
]
BACKEND_CORS_ORIGINS = [o for o in BACKEND_CORS_ORIGINS if o]  # filter empty