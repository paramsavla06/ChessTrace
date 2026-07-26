"""
PGN parsing orchestrator.

Responsible for coordinating the parsing of a single PGN game.

Responsibilities
----------------
- Parse game metadata
- Extract player names
- Parse moves
- Return parsed ORM objects

Non-responsibilities
--------------------
- Reading PGN files
- Database commits
- Duplicate detection
- Player resolution
- Batch imports
"""

from __future__ import annotations

from dataclasses import dataclass

import chess.pgn

from app.models import Game, Move
from app.parsers.game_parser import parse_game
from app.parsers.move_parser import parse_moves


@dataclass(slots=True)
class ParsedGame:
    """
    Parsed representation of a single PGN game.

    This object contains everything required by ImportService
    to persist the game.
    """

    game: Game
    moves: list[Move]

    white_name: str
    black_name: str


def parse_pgn(pgn_game: chess.pgn.Game,) -> ParsedGame:
    """
    Parse a python-chess PGN object.

    Parameters
    ----------
    pgn_game:
        Parsed PGN game.

    Returns
    -------
    ParsedGame
    """

    headers = pgn_game.headers

    return ParsedGame(
        game=parse_game(pgn_game),
        moves=parse_moves(pgn_game),
        white_name=headers.get("White", "Unknown"),
        black_name=headers.get("Black", "Unknown"),
    )
