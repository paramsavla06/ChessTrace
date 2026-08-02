"""
Stockfish position evaluator.

Responsible for evaluating a single chess position and converting the
raw Stockfish output into an EvaluationResult.

Responsibilities
----------------
- Evaluate a single chess position
- Parse Stockfish analysis
- Convert InfoDict into EvaluationResult

Non-responsibilities
--------------------
- Database operations
- Iterating over complete games
- Feature extraction
- Machine learning
"""

from __future__ import annotations

from typing import cast

import chess
import chess.engine

from app.engine.limits import DEFAULT_DEPTH
from app.engine.stockfish import StockfishEngine
from app.schemas.evaluation_result import EvaluationResult
from app.engine.exceptions import EvaluationError


class Evaluator:
    """
    Evaluates a single chess position using Stockfish.
    """

    def __init__(self, engine: StockfishEngine) -> None:
        """
        Parameters
        ----------
        engine
            Running Stockfish engine wrapper.
        """
        self._engine = engine

    def evaluate(
        self,
        board: chess.Board,
        *,
        move_number: int,
        played_move: chess.Move | None = None,
        depth: int = DEFAULT_DEPTH,
    ) -> EvaluationResult:
        """
        Evaluate a chess position.

        Parameters
        ----------
        board
            Position to evaluate.

        move_number
            Sequential move number.

        played_move
            Move actually played from this position.

        depth
            Requested Stockfish search depth.

        Returns
        -------
        EvaluationResult
            Parsed engine evaluation.
        """

        try:
            info = self._engine.analyse(
                board,
                depth=depth,
            )
        except chess.engine.EngineError as exc:
            raise EvaluationError("Failed to evaluate chess position.") from exc

        raw_score = cast(chess.engine.PovScore | None, info.get("score"))

        if raw_score is None:
            raise RuntimeError("Stockfish did not return an evaluation score.")

        score = raw_score.relative

        pv = cast(list[chess.Move], info.get("pv", []))
        actual_depth = cast(int, info.get("depth", depth))
        nodes = cast(int, info.get("nodes", 0))
        nps = cast(int, info.get("nps", 0))
        time = cast(float, info.get("time", 0.0))

        if score.is_mate():
            cp_score: int | None = None
            mate_score: int | None = score.mate()
        else:
            cp_score = score.score()
            mate_score = None

        best_move = pv[0].uci() if pv else None

        principal_variation = tuple(
            move.uci()
            for move in pv
        )

        return EvaluationResult(
            move_number=move_number,
            fen=board.fen(),
            depth=actual_depth,
            cp_score=cp_score,
            mate_score=mate_score,
            played_move=(
                played_move.uci()
                if played_move is not None
                else None
            ),
            best_move=best_move,
            principal_variation=principal_variation,
            nodes=nodes,
            nps=nps,
            time_ms=int(time * 1000),
        )
