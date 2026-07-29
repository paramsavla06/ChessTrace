"""
Database dependency injection helpers.
"""

from __future__ import annotations

from collections.abc import Generator
from sqlalchemy.orm import Session

from app.database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a database session context per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
