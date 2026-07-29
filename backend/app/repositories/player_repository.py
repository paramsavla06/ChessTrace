"""
Player repository module for database queries.
"""

from __future__ import annotations

from typing import Sequence
from sqlalchemy.orm import Session

from app.models.player import Player
from app.utils.chess_utils import normalize_player_name


class PlayerRepository:
    """Repository handling Player ORM queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_name(self, name: str) -> Player | None:
        """Fetch player by name."""
        norm_name = normalize_player_name(name)
        return (
            self.session.query(Player)
            .filter(Player.normalized_name == norm_name)
            .first()
        )

    def list_players(self, skip: int = 0, limit: int = 50) -> Sequence[Player]:
        """List players with pagination."""
        return self.session.query(Player).offset(skip).limit(limit).all()
