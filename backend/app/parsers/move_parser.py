"""
Move parsing utilities.

Responsible for converting the moves of a python-chess PGN game into Move ORM objects.

This parser is completely stateless.

Responsibilities
----------------
- Traverse the mainline only
- Generate SAN
- Generate UCI
- Generate FEN after every move
- Detect captures
- Detect checks
- Detect checkmates
- Detect promotions
- Extract clock annotations (if available)

Non-responsibilities
--------------------
- Database commits
- Engine analysis
- Feature extraction
"""

from __future__ import annotations

import re

import chess
import chess.pgn

from app.models import Move
from app.models.move import MoveColor
from app.utils.chess_utils import parse_clock


_CLOCK_PATTERN = re.compile(r"\[%clk ([^\]]+)\]")


def parse_moves(game: chess.pgn.Game,) -> list[Move]:
    """
    Parse all moves from the PGN.

    Parameters
    ----------
    game:
        python-chess PGN object.

    Returns
    -------
    list[Move]
        List of ORM Move objects.

    Notes
    -----
    Only the mainline is imported.

    Variations are intentionally ignored.
    """

    board = game.board()

    moves: list[Move] = []
    previous_white_clock: int | None = None
    previous_black_clock: int | None = None

    for ply, node in enumerate(game.mainline(), start=1):

        chess_move = node.move

        if chess_move is None:
            continue

        turn = board.turn
        color = (
            MoveColor.WHITE
            if turn == chess.WHITE
            else MoveColor.BLACK
        )

        move_number = (ply + 1) // 2

        san = board.san(chess_move)

        uci = chess_move.uci()

        is_capture = board.is_capture(chess_move)

        promotion = (
            chess.piece_name(chess_move.promotion)
            if chess_move.promotion
            else None
        )

        board.push(chess_move)

        fen = board.fen()

        is_check = board.is_check()

        is_checkmate = board.is_checkmate()

        clock_after = _extract_clock(node)

        prev_clock = previous_white_clock if turn == chess.WHITE else previous_black_clock
        time_spent = None

        if prev_clock is not None and clock_after is not None:
            time_spent = max(0, prev_clock - clock_after)

        if turn == chess.WHITE:
            previous_white_clock = clock_after
        else:
            previous_black_clock = clock_after

        move = Move(
            move_number=move_number,
            ply=ply,
            color=color,
            san=san,
            uci=uci,
            fen=fen,
            is_capture=is_capture,
            is_check=is_check,
            is_checkmate=is_checkmate,
            promotion=promotion,
            clock_before=prev_clock,
            clock_after=clock_after,
            time_spent=time_spent,
        )

        moves.append(move)

    return moves


def _extract_clock(node: chess.pgn.ChildNode,) -> int | None:
    """
    Extract the remaining clock time from a PGN comment.

    Example comment

        [%clk 1:28:14]

    Returns
    -------
    int | None
        Remaining clock time in milliseconds.
    """

    comment = node.comment

    if not comment:
        return None

    match = _CLOCK_PATTERN.search(comment)

    if match is None:
        return None

    return parse_clock(match.group(1))