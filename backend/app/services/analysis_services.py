"""
Analysis service.

Responsible for orchestrating game engine analysis and persisting
Evaluation ORM objects into the database.

Responsibilities
----------------
- Query games needing analysis
- Orchestrate Analyzer and EvaluationMapper
- Batch transaction management (add, flush, commit, rollback)
- Logging and error handling
- Return AnalysisSummary

Non-responsibilities
--------------------
- Running Stockfish UCI directly
- Parsing PGN
- Feature extraction
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.engine.analyzer import Analyzer
from app.engine.stockfish import StockfishEngine
from app.mappers.evaluation_mapper import EvaluationMapper
from app.models.evaluation import Evaluation
from app.models.game import Game
from app.schemas.analysis_summary import AnalysisSummary

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


class AnalysisService:
    """
    Service responsible for analyzing games using Stockfish.
    """

    def __init__(
        self,
        session: Session,
        analyzer: Analyzer,
        engine: StockfishEngine,
    ) -> None:
        self.session = session
        self.analyzer = analyzer
        self.engine = engine

    def analyze_game(self, game: Game) -> int:
        """
        Analyze all moves for a single game and persist evaluations.

        Parameters
        ----------
        game
            Game ORM instance containing loaded moves.

        Returns
        -------
        int
            Number of evaluations persisted.
        """
        if not game.moves:
            logger.warning("Game ID=%d has no moves to analyze.", game.id)
            return 0

        # Run analyzer across game moves
        evaluated_pairs = self.analyzer.analyze(game.moves)

        evaluations: list[Evaluation] = []
        for move, eval_result in evaluated_pairs:
            # Check if evaluation for move already exists
            existing_eval = (
                self.session.query(Evaluation.id)
                .filter(
                    Evaluation.move_id == move.id,
                    Evaluation.depth == eval_result.depth,
                    Evaluation.engine_version == self.engine.version,
                )
                .first()
            )

            if existing_eval is not None:
                continue

            eval_model = EvaluationMapper.to_model(
                eval_result,
                move,
                engine_version=self.engine.version,
            )
            evaluations.append(eval_model)

        if evaluations:
            self.session.add_all(evaluations)
            self.session.flush()

        return len(evaluations)

    def analyze_unprocessed_games(
        self,
        *,
        limit: int | None = None,
    ) -> AnalysisSummary:
        """
        Analyze games in the database that lack move evaluations.

        Parameters
        ----------
        limit
            Maximum number of games to analyze in this batch.

        Returns
        -------
        AnalysisSummary
            Summary of analysis processing statistics.
        """
        processed = 0
        analyzed = 0
        skipped = 0
        failed = 0
        total_positions = 0
        total_evaluations = 0

        query = self.session.query(Game)

        if limit is not None:
            query = query.limit(limit)

        games: Sequence[Game] = query.all()

        for game in games:
            processed += 1
            num_positions = len(game.moves)
            total_positions += num_positions

            try:
                eval_count = self.analyze_game(game)
                if eval_count > 0:
                    analyzed += 1
                    total_evaluations += eval_count
                else:
                    skipped += 1

                if analyzed > 0 and analyzed % BATCH_SIZE == 0:
                    self.session.commit()
                    logger.info(
                        "Processed=%d Analyzed=%d TotalEvals=%d",
                        processed,
                        analyzed,
                        total_evaluations,
                    )

            except Exception as exc:
                failed += 1
                self.session.rollback()
                logger.exception(
                    "Failed analyzing Game ID=%d: %s",
                    game.id,
                    exc,
                )

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

        logger.info("Analysis complete.")
        return AnalysisSummary(
            processed=processed,
            analyzed=analyzed,
            skipped=skipped,
            failed=failed,
            total_positions=total_positions,
            total_evaluations=total_evaluations,
        )
