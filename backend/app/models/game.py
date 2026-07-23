from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.move import Move

from datetime import date
import enum

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin

# Enums
class Variant(enum.Enum):
    STANDARD = "Standard"
    CHESS960 = "Chess960"
    ANTICHESS = "Antichess"
    ATOMIC = "Atomic"
    HORDE = "Horde"
    CRAZYHOUSE = "Crazyhouse"
    KING_OF_THE_HILL = "King of the Hill"
    THREE_CHECK = "Three-check"
    RACING_KINGS = "Racing Kings"
    

class GameResult(enum.Enum):
    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "1/2-1/2"
    ONGOING = "*"

# Model
class Game(Base, TimestampMixin):
    __tablename__ = "games"
    
    __table_args__ = (
        CheckConstraint("white_elo >= 0", name="ck_white_elo_positive"),
        CheckConstraint("black_elo >= 0", name="ck_black_elo_positive"),
    )
    
    id: Mapped[int] = mapped_column(
		Integer,
		primary_key=True,
		autoincrement=True,
	)
    
    site: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    event: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    game_round: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    game_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    white_player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        nullable=False,
        index=True,
    )

    black_player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        nullable=False,
        index=True,
    )

    white_elo: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    black_elo: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    result: Mapped[GameResult] = mapped_column(
        Enum(GameResult, name="game_result_enum"),
        nullable=False,
        index=True,
    )

    eco: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
    )

    opening: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    variation: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    time_control: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    termination: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    rated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        default=True,
        server_default="true",
    )

    variant: Mapped[Variant] = mapped_column(
        Enum(Variant, name="variant_enum"),
        nullable=False,
        default=Variant.STANDARD,
        index=True,
    )

    initial_fen: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    pgn_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    white_player: Mapped["Player"] = relationship(
        "Player",
        foreign_keys=[white_player_id],
        back_populates="white_games",
        lazy="selectin",
    )

    black_player: Mapped["Player"] = relationship(
        "Player",
        foreign_keys=[black_player_id],
        back_populates="black_games",
        lazy="selectin",
    )

    moves: Mapped[list["Move"]] = relationship(
        "Move",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return (
            f"<Game("
            f"id={self.id}, "
            f"white_player_id={self.white_player_id}, "
            f"black_player_id={self.black_player_id}, "
            f"result={self.result.value}"
            f")>"
        )