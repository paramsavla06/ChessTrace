"""
Application configuration settings.
"""

from __future__ import annotations

import os
import shutil
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
if _db_url.startswith("postgresql+psycopg://"):
    _db_url = _db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif _db_url.startswith("postgresql://") and not _db_url.startswith("postgresql+"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
DATABASE_URL: str = _db_url


def resolve_stockfish_path() -> str | None:
    """Intelligently locate the Stockfish binary across dev, docker, and cloud environments."""
    configured = os.getenv("STOCKFISH_PATH")
    candidates: list[Path] = []
    if configured:
        p = Path(configured)
        candidates.extend([
            p,
            BASE_DIR / configured,
            BASE_DIR / "backend" / configured,
            BASE_DIR / "backend" / "app" / "engine" / p.name,
        ])

    # Check system PATH
    for cmd in ["stockfish", "stockfish.exe", "stockfish_bin"]:
        w = shutil.which(cmd)
        if w:
            candidates.append(Path(w))

    # Common development, container, and free-tier Linux locations
    candidates.extend([
        BASE_DIR / "backend" / "app" / "engine" / "stockfish.exe",
        BASE_DIR / "backend" / "stockfish_bin",
        BASE_DIR / "stockfish_bin",
        Path("./stockfish_bin"),
        Path("./backend/stockfish_bin"),
        Path("./app/engine/stockfish.exe"),
        Path("/usr/games/stockfish"),
        Path("/usr/bin/stockfish"),
        Path("/usr/local/bin/stockfish"),
    ])

    for c in candidates:
        try:
            if c and c.is_file():
                return str(c.resolve())
        except Exception:
            continue
    return None


STOCKFISH_PATH: str | None = resolve_stockfish_path()
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