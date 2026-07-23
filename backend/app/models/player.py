from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.game import Game

from sqlalchemy import String, Integer

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    fide_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        unique=True,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
    )

    federation: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        index=True,
    )

    white_games: Mapped[list["Game"]] = relationship(
        "Game",
        foreign_keys="Game.white_player_id",
        back_populates="white_player",
        lazy="selectin",
    )

    black_games: Mapped[list["Game"]] = relationship(
        "Game",
        foreign_keys="Game.black_player_id",
        back_populates="black_player",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name='{self.name}')>"