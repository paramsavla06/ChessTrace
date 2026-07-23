from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin

class Game(Base, TimestampMixin):
    __tablename__ = "games"
    
    id: Mapped[int] = mapped_column(
		Integer,
		primary_key=True,
		autoincrement=True,
	)
    
    site: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    event: Mapped[str | None] = mapped_column(String(100))
    game_date: Mapped[date | None] = mapped_column(Date)
    
    white_player: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    black_player: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    white_elo: Mapped[int | None] = mapped_column(Integer)
    black_elo: Mapped[int | None] = mapped_column(Integer)

    result: Mapped[str] = mapped_column(String(10), nullable=False)

    eco: Mapped[str | None] = mapped_column(String(10), index=True)
    opening: Mapped[str | None] = mapped_column(String(255), index=True)

    time_control: Mapped[str | None] = mapped_column(String(30))

    termination: Mapped[str | None] = mapped_column(String(50))

    rated: Mapped[bool] = mapped_column(Boolean, nullable=False)

    variant: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Standard",
    )
    
    initial_fen: Mapped[str | None] = mapped_column(Text)
    
    moves = relationship(
		"Move",
		back_populates="game",
		cascade="all, delete-orphan",
	)