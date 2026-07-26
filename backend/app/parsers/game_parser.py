"""
Game parsing utilities.

Responsible for converting a python-chess PGN Game into a Game ORM object.

This module performs:

- PGN header extraction
- Header normalization
- Metadata parsing
- Game object construction

It does NOT:

- Commit transactions
- Detect duplicate games
- Insert into the database
"""

from __future__ import annotations

import chess.pgn

from app.models import Game
from app.utils.chess_utils import (
	clean_header,
	normalize_eco,
	normalize_time_control,
	parse_game_date,
	parse_int,
	parse_result,
)

def parse_game(game: chess.pgn.Game) -> Game:
    
	headers = game.headers
 
	return Game(
		site=clean_header(headers.get("Site")),
		source=clean_header(headers.get("Source")),
		event=clean_header(headers.get("Event")),
		game_round=clean_header(headers.get("Round")),
		game_date=parse_game_date(headers.get("Date")),
		white_elo=parse_int(headers.get("WhiteElo")),
		black_elo=parse_int(headers.get("BlackElo")),
		result=parse_result(headers.get("Result", "*")),
        eco=normalize_eco(headers.get("ECO")),
        opening=clean_header(headers.get("Opening")),
        variation=clean_header(headers.get("Variation")),
        annotator=clean_header(headers.get("Annotator")),
        time_control=normalize_time_control(headers.get("TimeControl")),
        termination=clean_header(headers.get("Termination")),
        rated=_parse_rated(headers),
        variant=_parse_variant(headers),
        initial_fen=_parse_initial_fen(headers),
	)
 
def _parse_rated(headers: chess.pgn.Headers) -> bool:
    """
    Determine whether the game is rated.

    Missing values default to True.
    """

    value = headers.get("Rated")

    if value is None:
        return True

    value = value.strip().lower()

    if value in {
        "false",
        "no",
        "0",
        "unrated",
    }:
        return False

    return True


def _parse_variant(headers: chess.pgn.Headers):
    """
    Convert Variant header into Variant enum.

    Missing values default to STANDARD.
    """

    from app.models.game import Variant

    value = headers.get("Variant")

    if value is None:
        return Variant.STANDARD

    normalized = value.strip().casefold()

    mapping = {
        "standard": Variant.STANDARD,
        "chess960": Variant.CHESS960,
        "atomic": Variant.ATOMIC,
        "antichess": Variant.ANTICHESS,
        "crazyhouse": Variant.CRAZYHOUSE,
        "horde": Variant.HORDE,
        "king of the hill": Variant.KING_OF_THE_HILL,
        "three-check": Variant.THREE_CHECK,
        "racing kings": Variant.RACING_KINGS,
    }

    return mapping.get(
        normalized,
        Variant.STANDARD,
    )


def _parse_initial_fen(headers: chess.pgn.Headers,) -> str | None:
    """
    Return initial FEN if supplied.

    Standard games return None.
    """

    fen = headers.get("FEN")

    if fen is None:
        return None

    fen = fen.strip()

    if not fen:
        return None

    return fen