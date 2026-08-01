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


_GLOBAL_ELO_MODELS: dict[str, WinCollapsePredictor] = {}
_MODELS_LOADED: bool = False


class EloSimulatorManager:
    """
    Manager for rating-bucket segmented human move prediction.
    """

    def __init__(self) -> None:
        self.elo_buckets = ELO_BUCKETS
        self.elo_models: dict[str, WinCollapsePredictor] = _GLOBAL_ELO_MODELS
        self._load_elo_models()

    def _load_elo_models(self) -> None:
        """Load trained XGBoost weights for each ELO bucket globally."""
        global _MODELS_LOADED, _GLOBAL_ELO_MODELS
        if _MODELS_LOADED:
            return
            
        if not WEIGHTS_DIR.exists():
            _MODELS_LOADED = True
            return

        for bucket in self.elo_buckets:
            safe_bucket_name = bucket.replace("<", "under_").replace("+", "_plus").replace("-", "_to_")
            weights_file = WEIGHTS_DIR / f"elo_xgboost_{safe_bucket_name}.json"
            if weights_file.exists():
                try:
                    predictor = WinCollapsePredictor.load(weights_file)
                    _GLOBAL_ELO_MODELS[bucket] = predictor
                    logger.info("Loaded trained ELO model artifact for bucket '%s'", bucket)
                except Exception as exc:
                    logger.warning("Could not load ELO model for %s: %s", bucket, exc)
                    
        _MODELS_LOADED = True

    def predict_for_elo(
        self,
        board: chess.Board,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
        target_elo_bucket: str = "1600-1800",
        best_move_uci: str | None = None,
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

        # Skip evaluating with Stockfish if we already know the best move from the DB timeline!
        if not best_move_uci:
            # Evaluate legal moves using Stockfish 18 at fast depth=12 (150ms)
            from app.core.config import STOCKFISH_PATH
            if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
                try:
                    from app.engine.stockfish import StockfishEngine

                    with StockfishEngine(Path(STOCKFISH_PATH)) as engine:
                        info = engine.analyse(board, depth=12)
                        if info.get("pv"):
                            best_move_uci = info["pv"][0].uci()
                except Exception as exc:
                    logger.warning("Stockfish ELO analysis failed: %s", exc)

        def move_quality_score(m: chess.Move) -> float:
            score = 0.0
            if best_move_uci and m.uci() == best_move_uci:
                score += 500.0

            # Main line central pawn pushes priority: d5 > e5 > c5 > d4 > e4 > c4
            if m.to_square == chess.D5:
                score += 35.0
            elif m.to_square == chess.E5:
                score += 32.0
            elif m.to_square in (chess.C5, chess.D4, chess.E4, chess.C4):
                score += 25.0

            # Piece development (Knights & Bishops)
            piece = board.piece_at(m.from_square)
            if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                score += 25.0
                # Reward pinning bishop move (Bg4 / Bg5)
                if piece.piece_type == chess.BISHOP and m.to_square in (chess.G4, chess.G5, chess.B4, chess.B5):
                    score += 30.0

            # Captures: only reward safe captures, penalize hanging piece captures (like Nxe5 into defended pawn)
            if board.is_capture(m):
                board.push(m)
                is_defender_present = any(board.is_capture(op) and op.to_square == m.to_square for op in board.legal_moves)
                board.pop()
                if is_defender_present and piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    score -= 80.0
                else:
                    score += 15.0

            # Penalize queen checks that hang pieces
            if board.gives_check(m):
                if piece and piece.piece_type == chess.QUEEN:
                    score -= 100.0
                else:
                    score += 5.0

            return score

        legal_moves_sorted = sorted(legal_moves, key=move_quality_score, reverse=True)

        candidates: list[CandidateMovePrediction] = []
        elo_idx = self.elo_buckets.index(target_elo_bucket) if target_elo_bucket in self.elo_buckets else 3

        base_think = 3.0 + (time_feats.time_remaining / 30.0)
        if time_feats.is_time_pressure_30s:
            base_think = max(0.5, base_think * 0.3)

        # Probabilities distribution per ELO tier
        if target_elo_bucket == "2000+":
            probs = [0.75, 0.15, 0.06, 0.03, 0.01]
        elif target_elo_bucket == "1800-2000":
            probs = [0.65, 0.20, 0.09, 0.04, 0.02]
        elif target_elo_bucket == "1600-1800":
            probs = [0.55, 0.25, 0.12, 0.05, 0.03]
        else:
            probs = [0.45, 0.28, 0.15, 0.08, 0.04]

        num_cand = min(len(legal_moves_sorted), 5)
        probs = probs[:num_cand]
        total_p = sum(probs)
        normalized_probs = [p / total_p for p in probs]

        for idx, m in enumerate(legal_moves_sorted[:num_cand]):
            san_str = board.san(m)
            is_top = (idx == 0)
            candidates.append(
                CandidateMovePrediction(
                    san=san_str,
                    uci=m.uci(),
                    probability=round(normalized_probs[idx], 4),
                    expected_think_time_sec=round(base_think * (1.0 + idx * 0.15), 1),
                    is_engine_top_choice=is_top,
                )
            )

        return EloSimulationResult(
            elo_bucket=target_elo_bucket,
            fen=board.fen(),
            top_candidate_moves=candidates,
            engine_recommendation=candidates[0].san if candidates else "",
        )
