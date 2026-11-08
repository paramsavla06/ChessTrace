"""
ELO Simulation Model Matrix.

Predicts what humans in specific rating tiers (<1000, 1000-1200, ..., 2000+)
would play in a given position + clock state vs Stockfish recommendations.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import xgboost as xgb

from app.core.constants import ELO_BUCKETS
from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures
from app.ml.collapse_model import WinCollapsePredictor

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"


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
    Enforces V2 as the authoritative model suite.
    """

    def __init__(self) -> None:
        self.elo_buckets = ELO_BUCKETS
        self.elo_models: dict[str, WinCollapsePredictor] = _GLOBAL_ELO_MODELS
        self._load_elo_models()

    def _load_elo_models(self) -> None:
        """Load trained XGBoost weights for each ELO bucket. V2 is authoritative by default."""
        global _MODELS_LOADED, _GLOBAL_ELO_MODELS
        if _MODELS_LOADED:
            return

        pref = os.environ.get("CHESSTRACE_MODEL_VERSION", "v2").lower()
        is_v1_explicit = (pref == "v1")
        target_dir = WEIGHTS_DIR if is_v1_explicit else WEIGHTS_DIR / "v2"
        version_label = "V1" if is_v1_explicit else "V2"

        if not target_dir.exists():
            err_msg = (
                f"Authoritative {version_label} ELO weights directory missing at {target_dir}. "
                "Automatic fallback between versions is strictly prohibited."
            )
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        for bucket in self.elo_buckets:
            safe_bucket_name = bucket.replace("<", "under_").replace("+", "_plus").replace("-", "_to_")
            filename = f"elo_xgboost_{safe_bucket_name}.json"
            weights_file = target_dir / filename

            if not weights_file.exists():
                err_msg = (
                    f"Authoritative {version_label} ELO model artifact missing for bucket '{bucket}' at {weights_file}. "
                    "Automatic fallback to legacy versions is strictly prohibited."
                )
                logger.error(err_msg)
                raise FileNotFoundError(err_msg)

            try:
                model = xgb.XGBRegressor()
                model.load_model(str(weights_file))
                predictor = WinCollapsePredictor(model=model)
                _GLOBAL_ELO_MODELS[bucket] = predictor
                logger.info(
                    "Loaded authoritative %s ELO model for bucket '%s' from %s",
                    version_label,
                    bucket,
                    weights_file,
                )
            except Exception as exc:
                err_msg = f"Failed to load {version_label} ELO model for bucket '{bucket}' from {weights_file}: {exc}"
                logger.critical(err_msg)
                raise RuntimeError(err_msg) from exc

        _MODELS_LOADED = True

    def get_model(self, bucket: str) -> WinCollapsePredictor:
        """
        Return the WinCollapsePredictor for a specific ELO bucket.
        If the bucket cannot be matched, falls back to the authoritative General V2 model
        without substituting V1.
        """
        if bucket in self.elo_models:
            return self.elo_models[bucket]
        logger.warning(
            "Requested ELO bucket '%s' not found among %s. Falling back to authoritative General V2 model.",
            bucket,
            list(self.elo_models.keys()),
        )
        return WinCollapsePredictor()

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

        # Get the top candidate moves according to Stockfish
        engine_top_moves = []
        from app.core.config import STOCKFISH_PATH
        if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
            try:
                from app.engine.stockfish import StockfishEngine

                with StockfishEngine(Path(STOCKFISH_PATH)) as engine:
                    infos = engine.analyse_multipv(board, depth=12, multipv=5)
                    for info in infos:
                        if info.get("pv"):
                            engine_top_moves.append(info["pv"][0])
            except Exception as exc:
                logger.warning("Stockfish ELO multipv analysis failed: %s", exc)

        # Fallback to intelligent tactical/positional move ranking if engine is unavailable
        if not engine_top_moves:
            def _rank_move(m: chess.Move) -> float:
                score = 0.0
                if board.is_capture(m):
                    target_p = board.piece_at(m.to_square)
                    attacker_p = board.piece_at(m.from_square)
                    t_val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}.get(target_p.piece_type if target_p else 1, 1)
                    a_val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}.get(attacker_p.piece_type if attacker_p else 1, 1)
                    score += 10.0 + (t_val * 2.0) - (a_val * 0.5)
                if board.gives_check(m):
                    score += 4.0
                if m.to_square in [chess.D4, chess.E4, chess.D5, chess.E5]:
                    score += 3.0
                elif m.to_square in [chess.C3, chess.F3, chess.C6, chess.F6]:
                    score += 2.0
                if m.promotion:
                    score += 15.0
                return score

            sorted_moves = sorted(legal_moves, key=_rank_move, reverse=True)
            engine_top_moves = sorted_moves[:5]

        candidates: list[CandidateMovePrediction] = []
        
        if time_feats.has_clock_data:
            base_think = 3.0 + (time_feats.time_remaining / 30.0)
            if time_feats.is_time_pressure_30s:
                base_think = max(0.5, base_think * 0.3)
        else:
            base_think = 5.0

        # Probabilities distribution per ELO tier
        if target_elo_bucket == "2000+":
            probs = [0.75, 0.15, 0.06, 0.03, 0.01]
        elif target_elo_bucket == "1800-2000":
            probs = [0.65, 0.20, 0.09, 0.04, 0.02]
        elif target_elo_bucket == "1600-1800":
            probs = [0.55, 0.25, 0.12, 0.05, 0.03]
        elif target_elo_bucket == "1400-1600":
            probs = [0.45, 0.28, 0.15, 0.08, 0.04]
        elif target_elo_bucket == "1200-1400":
            probs = [0.35, 0.30, 0.18, 0.10, 0.07]
        elif target_elo_bucket == "1000-1200":
            probs = [0.25, 0.32, 0.20, 0.13, 0.10]
        else: # < 1000
            probs = [0.15, 0.30, 0.25, 0.18, 0.12]

        num_cand = min(len(engine_top_moves), 5)
        probs = probs[:num_cand]
        total_p = sum(probs)
        normalized_probs = [p / total_p for p in probs]

        for idx, m in enumerate(engine_top_moves[:num_cand]):
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
