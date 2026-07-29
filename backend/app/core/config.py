"""
Application configuration settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

PROJECT_NAME: str = "ChessTrace"
API_V1_STR: str = "/api/v1"

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chesstrace.db")
STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "stockfish")

BACKEND_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "*",
]