"""
Database schema initialization script.
"""

from __future__ import annotations

import logging
from sqlalchemy.engine import Engine

from app.database.base import Base
# Ensure all models are imported before creating tables
from app.models import Game, Move, Evaluation, Player  # noqa: F401

logger = logging.getLogger(__name__)


def init_db(engine: Engine) -> None:
    """Initialize database tables."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
