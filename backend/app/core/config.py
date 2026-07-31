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

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chesstrace.db")
STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "stockfish")
LICHESS_API_TOKEN: str = os.getenv("LICHESS_API_TOKEN", "")

BACKEND_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "*",
]