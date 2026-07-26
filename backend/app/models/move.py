import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.evaluation import Evaluation

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
    Index,
    UniqueConstraint
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin


class MoveColor(enum.Enum):
    WHITE = "white"
    BLACK = "black"


class Move(Base, TimestampMixin):
    __tablename__ = "moves"
    
    __table_args__ = (
        Index(
            "ix_moves_game_ply",
            "game_id",
            "ply",
        ),
        UniqueConstraint(
            "game_id",
            "ply",
            name="uq_game_ply",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    game_id: Mapped[int] = mapped_column(
        ForeignKey(
            "games.id",
            ondelete="CASCADE",
            name="fk_moves_game",
        ),
        nullable=False,
        index=True,
    )

    move_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ply: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    color: Mapped[MoveColor] = mapped_column(
        Enum(MoveColor, name="move_color_enum"),
        nullable=False,
    )

    san: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    uci: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    fen: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_capture: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_checkmate: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    promotion: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    clock_before: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    clock_after: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    time_spent: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="moves",
        lazy="selectin",
    )

    evaluations: Mapped[list["Evaluation"]] = relationship(
        "Evaluation",
        back_populates="move",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Move("
            f"game={self.game_id}, "
            f"ply={self.ply}, "
            f"uci='{self.uci}'"
            f")>"
        )
