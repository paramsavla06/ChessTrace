
"""
Player resolution utilities.

Responsible for resolving PGN player information into Player ORM objects.

Lookup priority:

1. FIDE ID
2. Normalized player name

This module never commits transactions.
It only creates ORM objects and flushes the session when required.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Player
from app.utils.chess_utils import (
    clean_header,
    normalize_player_name,
)


def resolve_player(
    session: Session,
    name: str,
    fide_id: int | None = None,
    title: str | None = None,
    federation: str | None = None,
) -> Player:
    """
    Resolve a player from PGN metadata.

    Lookup priority:

    1. FIDE ID
    2. Normalized name

    If the player does not exist, a new Player record
    is created and added to the current session.

    Notes:
        - Does NOT commit the transaction.
        - Flushes the session to obtain the generated ID.

    Args:
        session:
            Active SQLAlchemy session.

        name:
            Player name from the PGN.

        fide_id:
            Optional FIDE identifier.

        title:
            Optional title (GM, IM, FM, ...).

        federation:
            Optional federation code (IND, USA, NOR, ...).

    Returns:
        Player ORM object.
    """

    display_name = clean_header(name)

    if display_name is None:
        raise ValueError("Player name cannot be empty.")

    normalized_name = normalize_player_name(display_name)

    title = clean_header(title)
    federation = clean_header(federation)

    # -------------------------------------------------------------
    # First try FIDE ID
    # -------------------------------------------------------------

    if fide_id is not None:

        player = (
            session.query(Player)
            .filter(Player.fide_id == fide_id)
            .one_or_none()
        )

        if player is not None:

            _update_player_metadata(
                player,
                display_name,
                title,
                federation,
            )

            return player

    # -------------------------------------------------------------
    # Then try normalized name
    # -------------------------------------------------------------

    player = (
        session.query(Player)
        .filter(Player.normalized_name == normalized_name)
        .one_or_none()
    )

    if player is not None:

        _update_player_metadata(
            player,
            display_name,
            title,
            federation,
        )

        if player.fide_id is None:
            player.fide_id = fide_id

        return player

    # -------------------------------------------------------------
    # Create new player
    # -------------------------------------------------------------

    player = Player(
        display_name=display_name,
        normalized_name=normalized_name,
        fide_id=fide_id,
        title=title,
        federation=federation,
    )

    session.add(player)

    # Allocate primary key immediately.
    session.flush()

    return player


def _update_player_metadata(
    player: Player,
    display_name: str,
    title: str | None,
    federation: str | None,
) -> None:
    """
    Update player metadata when new information is available.

    Existing information is never overwritten with None.
    """

    if player.display_name != display_name:
        player.display_name = display_name

    if player.title is None and title is not None:
        player.title = title

    if player.federation is None and federation is not None:
        player.federation = federation
