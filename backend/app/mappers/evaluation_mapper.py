"""
Evaluation mapper.

Responsible for converting EvaluationResult DTOs into Evaluation ORM
models.

Responsibilities
----------------
- Convert EvaluationResult into Evaluation
- Isolate ORM construction from the service layer

Non-responsibilities
--------------------
- Database operations
- Stockfish interaction
- Feature engineering
- Game analysis
"""

from __future__ import annotations

from app.models.evaluation import Evaluation
from app.models.move import Move
from app.schemas.evaluation_result import EvaluationResult


class EvaluationMapper:
    """
    Maps EvaluationResult objects to Evaluation ORM models.
    """

    @staticmethod
    def to_model(
        result: EvaluationResult,
        move: Move,
        *,
        engine_version: str,
        multipv: int = 1,
    ) -> Evaluation:
        """
        Convert an EvaluationResult into an Evaluation ORM object.

        Parameters
        ----------
        result
            Evaluation returned by the engine.

        move
            Move corresponding to the evaluated position.

        engine_version
            Version of the Stockfish engine.

        multipv
            MultiPV line number.

        Returns
        -------
        Evaluation
            ORM model ready for persistence.
        """

        return Evaluation(
            move=move,
            depth=result.depth,
            multipv=multipv,
            score_cp=result.cp_score,
            mate=result.mate_score,
            best_move=result.best_move,
            pv=" ".join(result.principal_variation)
            if result.principal_variation
            else None,
            nodes=result.nodes,
            nps=result.nps,
            analysis_time_ms=result.time_ms,
            engine_version=engine_version,
        )
