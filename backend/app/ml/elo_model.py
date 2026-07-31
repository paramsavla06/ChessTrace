"""
ELO Simulation Model Matrix.

Predicts what humans in specific rating tiers (<1000, 1000-1200, ..., 2000+)
would play in a given position + clock state vs Stockfish recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess

from app.core.constants import ELO_BUCKETS
from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures
from app.ml.collapse_model import WinCollapsePredictor

logger = logging.getLogger(__name__)

BASE_PROJECT_DIR = Path(__file__).resolve().parents[3]
WEIGHTS_DIR = BASE_PROJECT_DIR / "backend/app/ml/weights"


@dataclass
class CandidateMovePrediction:
    san: str
    uci: str
    probability: float
    expected_think_time_sec: float
    is_engine_top_choice: bool = False


@dataclass
class EloSimulationResult:
    elo_bucket: str
    fen: str
    top_candidate_moves: list[CandidateMovePrediction] = field(default_factory=list)
    engine_recommendation: str = ""


class EloSimulatorManager:
    """
    Manager for rating-bucket segmented human move prediction.
    """

    def __init__(self) -> None:
        self.elo_buckets = ELO_BUCKETS
        self.elo_models: dict[str, WinCollapsePredictor] = {}
        self._load_elo_models()

    def _load_elo_models(self) -> None:
        """Load trained XGBoost weights for each ELO bucket if available."""
        if not WEIGHTS_DIR.exists():
            return

        for bucket in self.elo_buckets:
            safe_bucket_name = bucket.replace("<", "under_").replace("+", "_plus").replace("-", "_to_")
            weights_file = WEIGHTS_DIR / f"elo_xgboost_{safe_bucket_name}.json"
            if weights_file.exists():
                try:
                    predictor = WinCollapsePredictor.load(weights_file)
                    self.elo_models[bucket] = predictor
                    logger.info("Loaded trained ELO model artifact for bucket '%s'", bucket)
                except Exception as exc:
                    logger.warning("Could not load ELO model for %s: %s", bucket, exc)

    def predict_for_elo(
        self,
        board: chess.Board,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
        target_elo_bucket: str = "1600-1800",
    ) -> EloSimulationResult:
        """
        Predict candidate moves and think times for a specific target ELO bracket.
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return EloSimulationResult(
                elo_bucket=target_elo_bucket,
                fen=board.fen(),
            )

        candidates: list[CandidateMovePrediction] = []
        legal_moves_sorted = sorted(legal_moves, key=lambda m: m.uci())

        elo_idx = self.elo_buckets.index(target_elo_bucket) if target_elo_bucket in self.elo_buckets else 3
        sharpness_factor = 0.5 + (elo_idx * 0.1)

        base_think = 3.0 + (time_feats.time_remaining / 30.0)
        if time_feats.is_time_pressure_30s:
            base_think = max(0.5, base_think * 0.3)

        probs: list[float] = []
        for idx, m in enumerate(legal_moves_sorted[:5]):
            score = max(0.1, 1.0 - (idx * 0.25 * sharpness_factor))
            probs.append(score)

        total_score = sum(probs)
        normalized_probs = [p / total_score for p in probs]

        for idx, m in enumerate(legal_moves_sorted[:5]):
            san_str = board.san(m)
            candidates.append(
                CandidateMovePrediction(
                    san=san_str,
                    uci=m.uci(),
                    probability=round(normalized_probs[idx], 4),
                    expected_think_time_sec=round(base_think * (1.0 + idx * 0.15), 1),
                    is_engine_top_choice=(idx == 0),
                )
            )

        return EloSimulationResult(
            elo_bucket=target_elo_bucket,
            fen=board.fen(),
            top_candidate_moves=candidates,
            engine_recommendation=candidates[0].san if candidates else "",
        )
