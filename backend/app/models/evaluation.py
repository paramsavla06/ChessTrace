from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.move import Move

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"
    
    __table_args__ = (
        UniqueConstraint(
            "move_id",
            "depth",
            "engine_version",
            name="uq_move_depth_engine",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    move_id: Mapped[int] = mapped_column(
        ForeignKey("moves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    score_cp: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    mate: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    best_move: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    pv: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    nodes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    nps: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    analysis_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    engine_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=False,
    )

    move: Mapped[Move] = relationship(
        "Move",
        back_populates="evaluations",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Evaluation("
            f"id={self.id}, "
            f"move_id={self.move_id}, "
            f"depth={self.depth}, "
            f"score_cp={self.score_cp}, "
            f"mate={self.mate}"
            f")>"
        )
