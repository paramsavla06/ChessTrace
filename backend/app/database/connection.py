from __future__ import annotations

from sqlalchemy import create_engine
from app.core.config import DATABASE_URL


def normalize_database_url(url: str) -> str:
    """
    Safely normalize database connection URLs for SQLAlchemy.

    Ensures PostgreSQL URLs use the psycopg2 driver (psycopg2-binary) by
    converting 'postgresql://', 'postgresql+psycopg://', and legacy 'postgres://' schemes.
    Preserves all credentials, host, port, database name, and query parameters.
    """
    if not url:
        return url
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


normalized_database_url = normalize_database_url(DATABASE_URL)
engine = create_engine(normalized_database_url, echo=False)
