"""
XGBoost Win Probability & Collapse Predictor.

Trains and evaluates XGBoost models predicting White-relative win probability
and computing time-pressure-weighted collapse risk metrics from positional
and clock feature vectors.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    # Position features (White-relative integers)
    "material_balance",
    "white_material",
    "black_material",
    "white_mobility",
    "black_mobility",
    "white_center_control",
    "black_center_control",
    "white_pawn_shield",
    "black_pawn_shield",
    "white_passed_pawns",
    "black_passed_pawns",
    "white_isolated_pawns",
    "black_isolated_pawns",
    "white_doubled_pawns",
    "black_doubled_pawns",
    # Time features (Seconds and binary flags)
    "think_time",
    "time_remaining",
    "is_time_pressure_120s",
    "is_time_pressure_60s",
    "is_time_pressure_30s",
    "time_usage_ratio",
    "running_avg_think_time",
    "think_time_deviation",
]

DEFAULT_WEIGHTS_PATH = Path(__file__).resolve().parent / "weights" / "collapse_xgboost.json"
_GLOBAL_MODEL: xgb.XGBRegressor | None = None


def get_shared_model() -> xgb.XGBRegressor | None:
    """Return a globally cached XGBoost model instance, loading from weights if available."""
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is not None:
        return _GLOBAL_MODEL
    if DEFAULT_WEIGHTS_PATH.exists():
        try:
            loaded = xgb.XGBRegressor()
            loaded.load_model(str(DEFAULT_WEIGHTS_PATH))
            _GLOBAL_MODEL = loaded
            logger.info("Loaded shared XGBoost model from %s", DEFAULT_WEIGHTS_PATH)
        except Exception as exc:
            logger.warning("Could not load default XGBoost model from %s: %s", DEFAULT_WEIGHTS_PATH, exc)
    return _GLOBAL_MODEL


def set_shared_model(model: xgb.XGBRegressor | None) -> None:
    """Explicitly update the globally cached XGBoost model singleton."""
    global _GLOBAL_MODEL
    _GLOBAL_MODEL = model


@dataclass(slots=True, frozen=True)
class PredictionResult:
    win_probability: float
    collapse_probability: float
    time_pressure_risk_multiplier: float
    black_collapse_probability: float = 0.0


class WinCollapsePredictor:
    """
    Predictor service running XGBoost inference on position + time features.
    
    Target Semantics:
    - win_probability: Data-driven expected outcome from White's perspective (1.0 = White Win).
    - collapse_probability: Analytical risk index derived from position volatility and clock pressure.
    """

    def __init__(self, model: xgb.XGBRegressor | None = None) -> None:
        if model is not None:
            self.model = model
        else:
            self.model = get_shared_model()

    def feature_vector_from_dtos(
        self,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
    ) -> pd.DataFrame:
        """
        Construct single-row pandas DataFrame matching exact XGBoost feature ordering,
        scaling, and units. If no clock data is available, neutral default values are
        injected so time stress is not hallucinated.
        """
        if not time_feats.has_clock_data:
            think_sec = 0.0
            rem_sec = 0.0
            is_120s = 0
            is_60s = 0
            is_30s = 0
            usage_ratio = 0.0
            running_avg = 0.0
            dev = 0.0
        else:
            think_sec = float(time_feats.think_time)
            if think_sec > 18000.0:
                think_sec /= 1000.0

            rem_sec = float(time_feats.time_remaining)
            if rem_sec > 86400.0:
                rem_sec /= 1000.0

            is_120s = int(time_feats.is_time_pressure_120s)
            is_60s = int(time_feats.is_time_pressure_60s)
            is_30s = int(time_feats.is_time_pressure_30s)
            usage_ratio = float(np.clip(time_feats.time_usage_ratio, 0.0, 1.0))
            running_avg = float(time_feats.running_avg_think_time)
            dev = float(time_feats.think_time_deviation)

        data = {
            "material_balance": [int(pos_feats.material_balance)],
            "white_material": [int(pos_feats.white_material)],
            "black_material": [int(pos_feats.black_material)],
            "white_mobility": [int(pos_feats.white_mobility)],
            "black_mobility": [int(pos_feats.black_mobility)],
            "white_center_control": [int(pos_feats.white_center_control)],
            "black_center_control": [int(pos_feats.black_center_control)],
            "white_pawn_shield": [int(pos_feats.white_pawn_shield)],
            "black_pawn_shield": [int(pos_feats.black_pawn_shield)],
            "white_passed_pawns": [int(pos_feats.white_passed_pawns)],
            "black_passed_pawns": [int(pos_feats.black_passed_pawns)],
            "white_isolated_pawns": [int(pos_feats.white_isolated_pawns)],
            "black_isolated_pawns": [int(pos_feats.black_isolated_pawns)],
            "white_doubled_pawns": [int(pos_feats.white_doubled_pawns)],
            "black_doubled_pawns": [int(pos_feats.black_doubled_pawns)],
            "think_time": [think_sec],
            "time_remaining": [rem_sec],
            "is_time_pressure_120s": [is_120s],
            "is_time_pressure_60s": [is_60s],
            "is_time_pressure_30s": [is_30s],
            "time_usage_ratio": [usage_ratio],
            "running_avg_think_time": [running_avg],
            "think_time_deviation": [dev],
        }
        return pd.DataFrame(data, columns=FEATURE_COLUMNS)

    def predict(
        self,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
        eval_cp: float | None = None,
        turn: chess.Color = chess.WHITE,
        is_already_white_pov: bool = True,
    ) -> PredictionResult:
        """
        Run inference to predict win and collapse probability using trained XGBoost.
        Synchronizes eval_cp perspective with ml_prob (White's POV) and computes
        perspective-aware collapse risk for both White and Black.
        """
        X = self.feature_vector_from_dtos(pos_feats, time_feats)

        win_prob: float
        if self.model is not None:
            raw_pred = float(self.model.predict(X)[0])
            ml_prob = float(np.clip(raw_pred, 0.0, 1.0))
        else:
            base_score = 0.5 + (pos_feats.material_balance * 0.05)
            ml_prob = float(np.clip(base_score, 0.05, 0.95))

        if eval_cp is not None:
            # Normalize eval_cp to White POV if provided turn-relative
            if not is_already_white_pov and turn == chess.BLACK:
                white_eval_cp = -eval_cp
            else:
                white_eval_cp = eval_cp

            # Standard Stockfish/Lichess sigmoid mapping centipawns to win probability
            exponent = max(-700.0, min(700.0, -0.00368208 * white_eval_cp))
            sf_prob = float(1.0 / (1.0 + math.exp(exponent)))

            # Blend 60% engine search, 40% XGBoost human cognitive model
            win_prob = float(np.clip(0.6 * sf_prob + 0.4 * ml_prob, 0.02, 0.98))
        else:
            win_prob = ml_prob

        # Compute time pressure risk multiplier (only if genuine clock data exists)
        time_mult = 1.0
        if time_feats.has_clock_data:
            if time_feats.is_time_pressure_30s:
                time_mult = 2.4
            elif time_feats.is_time_pressure_60s:
                time_mult = 1.7
            elif time_feats.is_time_pressure_120s:
                time_mult = 1.3

        # Base volatility / game tension
        tension = 1.0 - abs(win_prob - 0.5) * 2.0

        # Perspective-dependent collapse factors: disadvantaged side is significantly more vulnerable
        white_losing_factor = max(0.15, 1.0 - win_prob)
        black_losing_factor = max(0.15, win_prob)

        white_collapse = float(
            np.clip((0.4 * tension + 0.6 * white_losing_factor) * time_mult, 0.05, 0.95)
        )
        black_collapse = float(
            np.clip((0.4 * tension + 0.6 * black_losing_factor) * time_mult, 0.05, 0.95)
        )

        return PredictionResult(
            win_probability=win_prob,
            collapse_probability=white_collapse,
            time_pressure_risk_multiplier=time_mult,
            black_collapse_probability=black_collapse,
        )

    def train_on_dataframe(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> dict[str, float]:
        """
        Train XGBoost Regressor model on dataset DataFrame with train/test split.
        Automatically updates the cached global model singleton.
        """
        X = df[FEATURE_COLUMNS]
        y = df["game_result_score"].astype(float)

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=random_state, shuffle=True
        )

        model = xgb.XGBRegressor(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            early_stopping_rounds=20,
            eval_metric="rmse",
            random_state=random_state,
        )
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        self.model = model
        set_shared_model(model)

        val_preds = np.clip(model.predict(X_val), 0.0, 1.0)
        train_preds = np.clip(model.predict(X_train), 0.0, 1.0)

        train_rmse = float(np.sqrt(mean_squared_error(y_train, train_preds)))
        val_rmse = float(np.sqrt(mean_squared_error(y_val, val_preds)))
        val_mae = float(mean_absolute_error(y_val, val_preds))

        logger.info(
            "XGBoost trained successfully. Train RMSE: %.4f | Val RMSE: %.4f | Val MAE: %.4f",
            train_rmse,
            val_rmse,
            val_mae,
        )
        return {
            "train_rmse": train_rmse,
            "val_rmse": val_rmse,
            "val_mae": val_mae,
            "rmse": val_rmse,
        }

    def save(self, path: Path) -> None:
        """Save model artifact to disk and update global cache."""
        if self.model is None:
            raise ValueError("No model to save.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path))
        set_shared_model(self.model)

    @classmethod
    def load(cls, path: Path, set_as_shared: bool = False) -> WinCollapsePredictor:
        """
        Load model artifact from disk and return new predictor instance.
        Only updates the shared global model if set_as_shared is True.
        """
        model = xgb.XGBRegressor()
        model.load_model(str(path))
        if set_as_shared:
            set_shared_model(model)
        return cls(model=model)
