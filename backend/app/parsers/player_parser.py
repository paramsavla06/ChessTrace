from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Player


def get_or_create_player(
	session: Session,
	name: str,
	fide_id: int | None = None,
	title: int | None = None,
	federation: str | None = None,
) -> Player:
    """
    Retrieve an existing player by name.
    If the player does not exist, create a new one.

    Args:
        session: Active SQLAlchemy session.
        name: Player's name.
        fide_id: Optional FIDE ID.
        title: Optional chess title (GM, IM, etc.).
        federation: Optional federation code.

    Returns:
        Player ORM object.
    """
    player = (
		session.query(Player)
		.filter(Player.display_name == name)
		.first()
	)
    
    if player:
        return player
    
    player = Player(
		name=name,
		fide_id=fide_id,
		title=title,
		federation=federation,
	)
    
    session.add(Player)
    session.flush() # Assigns primary key immediately
    
    return player