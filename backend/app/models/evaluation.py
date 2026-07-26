from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.move import Move

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"
    
    __table_args__ = (
        UniqueConstraint(
            "move_id",
            "depth",
            "multipv",
            "engine_version",
            name="uq_move_depth_multipv_engine",
        ),
        CheckConstraint(
            "depth > 0",
            name="ck_depth_positive",
        ),
        CheckConstraint(
            "multipv >= 1",
            name="ck_multipv_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    move_id: Mapped[int] = mapped_column(
        ForeignKey(
            "moves.id",
            ondelete="CASCADE",
            name="fk_evaluations_move",
        ),
        nullable=False,
        index=True,
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    
    multipv: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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

    engine_version: Mapped[str] = mapped_column(
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
