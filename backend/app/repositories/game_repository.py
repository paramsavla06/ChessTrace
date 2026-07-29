"""
Game repository module for database queries.
"""

from __future__ import annotations

from typing import Sequence
from sqlalchemy.orm import Session, selectinload

from app.models.game import Game


class GameRepository:
    """Repository handling Game ORM queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, game_id: int) -> Game | None:
        """Fetch game by ID with loaded relationships."""
        return (
            self.session.query(Game)
            .options(
                selectinload(Game.white_player),
                selectinload(Game.black_player),
                selectinload(Game.moves),
            )
            .filter(Game.id == game_id)
            .first()
        )

    def list_games(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        username: str | None = None,
    ) -> Sequence[Game]:
        """List games with optional pagination and username filtering."""
        query = self.session.query(Game)

        if username:
            from app.models.player import Player
            from app.utils.chess_utils import normalize_player_name

            norm_name = normalize_player_name(username)
            query = query.join(
                Player,
                (Game.white_player_id == Player.id) | (Game.black_player_id == Player.id),
            ).filter(Player.normalized_name == norm_name)

        return query.offset(skip).limit(limit).all()

    def get_unprocessed_games(self, limit: int = 100) -> Sequence[Game]:
        """Fetch games that lack move evaluations."""
        return self.session.query(Game).limit(limit).all()
