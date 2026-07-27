"""
Game analyzer.

Responsible for analyzing an entire chess game by evaluating every
position reached after each played move.

Responsibilities
----------------
- Iterate through every move of a game
- Evaluate each stored position
- Return a list of EvaluationResult objects

Non-responsibilities
--------------------
- Database operations
- Stockfish process management
- Feature extraction
- Machine learning
"""

from __future__ import annotations

from collections.abc import Sequence

import chess

from app.engine.evaluator import Evaluator
from app.models.move import Move
from app.schemas.evaluation_result import EvaluationResult


class Analyzer:
    """
    Analyze an entire chess game.

    This class evaluates every stored position in a game using a
    Position Evaluator.
    """

    def __init__(self, evaluator: Evaluator) -> None:
        """
        Parameters
        ----------
        evaluator
            Position evaluator used for each board state.
        """
        self._evaluator = evaluator

    def analyze(
        self,
        moves: Sequence[Move],
    ) -> list[tuple[Move, EvaluationResult]]:
        """
        Analyze every move in a chess game.

        Parameters
        ----------
        moves
            Game moves in chronological order.

        Returns
        -------
        list[tuple[Move, EvaluationResult]]
            Engine evaluation paired with each move.
        """

        results: list[tuple[Move, EvaluationResult]] = []

        for move in moves:

            board = chess.Board(move.fen)

            result = self._evaluator.evaluate(
                board,
                move_number=move.move_number,
                played_move=chess.Move.from_uci(move.uci),
            )

            results.append((move, result))

        return results

