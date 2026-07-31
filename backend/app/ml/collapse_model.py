"""
XGBoost Win Probability & Collapse Predictor.

Trains and evaluates XGBoost models predicting win probability and time-weighted
collapse probability from position and clock feature vectors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    # Position features
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
    # Time features
    "think_time",
    "time_remaining",
    "is_time_pressure_120s",
    "is_time_pressure_60s",
    "is_time_pressure_30s",
    "time_usage_ratio",
    "running_avg_think_time",
    "think_time_deviation",
]


@dataclass(slots=True, frozen=True)
class PredictionResult:
    win_probability: float
    collapse_probability: float
    time_pressure_risk_multiplier: float


class WinCollapsePredictor:
    """
    Predictor service running XGBoost inference on position + time features.
    """

    def __init__(self, model: xgb.XGBRegressor | None = None) -> None:
        self.model = model

    def feature_vector_from_dtos(
        self,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
    ) -> pd.DataFrame:
        """Construct single-row pandas DataFrame matching XGBoost feature order."""
        data = {
            "material_balance": [pos_feats.material_balance],
            "white_material": [pos_feats.white_material],
            "black_material": [pos_feats.black_material],
            "white_mobility": [pos_feats.white_mobility],
            "black_mobility": [pos_feats.black_mobility],
            "white_center_control": [pos_feats.white_center_control],
            "black_center_control": [pos_feats.black_center_control],
            "white_pawn_shield": [pos_feats.white_pawn_shield],
            "black_pawn_shield": [pos_feats.black_pawn_shield],
            "white_passed_pawns": [pos_feats.white_passed_pawns],
            "black_passed_pawns": [pos_feats.black_passed_pawns],
            "white_isolated_pawns": [pos_feats.white_isolated_pawns],
            "black_isolated_pawns": [pos_feats.black_isolated_pawns],
            "white_doubled_pawns": [pos_feats.white_doubled_pawns],
            "black_doubled_pawns": [pos_feats.black_doubled_pawns],
            "think_time": [time_feats.think_time],
            "time_remaining": [time_feats.time_remaining],
            "is_time_pressure_120s": [int(time_feats.is_time_pressure_120s)],
            "is_time_pressure_60s": [int(time_feats.is_time_pressure_60s)],
            "is_time_pressure_30s": [int(time_feats.is_time_pressure_30s)],
            "time_usage_ratio": [time_feats.time_usage_ratio],
            "running_avg_think_time": [time_feats.running_avg_think_time],
            "think_time_deviation": [time_feats.think_time_deviation],
        }
        return pd.DataFrame(data, columns=FEATURE_COLUMNS)

    def predict(
        self,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
    ) -> PredictionResult:
        """
        Run inference to predict win and collapse probability.
        """
        X = self.feature_vector_from_dtos(pos_feats, time_feats)

        if self.model is not None:
            raw_pred = float(self.model.predict(X)[0])
            win_prob = float(np.clip(raw_pred, 0.0, 1.0))
        else:
            # Baseline mathematical heuristic if un-trained
            base_score = 0.5 + (pos_feats.material_balance * 0.05)
            win_prob = float(np.clip(base_score, 0.05, 0.95))

        # Compute time pressure risk multiplier
        time_mult = 1.0
        if time_feats.is_time_pressure_30s:
            time_mult = 2.4
        elif time_feats.is_time_pressure_60s:
            time_mult = 1.7
        elif time_feats.is_time_pressure_120s:
            time_mult = 1.3

        # Collapse risk is higher when win probability is volatile and time pressure is high
        collapse_prob = float(
            np.clip((1.0 - abs(win_prob - 0.5) * 2.0) * 0.4 * time_mult, 0.05, 0.95)
        )

        return PredictionResult(
            win_probability=win_prob,
            collapse_probability=collapse_prob,
            time_pressure_risk_multiplier=time_mult,
        )

    def train_on_dataframe(self, df: pd.DataFrame) -> dict[str, float]:
        """
        Train XGBoost Regressor model on dataset DataFrame.
        """
        X = df[FEATURE_COLUMNS]
        y = df["game_result_score"]

        model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        model.fit(X, y)
        self.model = model

        train_rmse = float(np.sqrt(np.mean((model.predict(X) - y) ** 2)))
        logger.info("XGBoost trained successfully. Train RMSE: %.4f", train_rmse)
        return {"rmse": train_rmse}

    def save(self, path: Path) -> None:
        """Save model artifact to disk."""
        if self.model is None:
            raise ValueError("No model to save.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path))

    @classmethod
    def load(cls, path: Path) -> WinCollapsePredictor:
        """Load model artifact from disk and return new predictor instance."""
        model = xgb.XGBRegressor()
        model.load_model(str(path))
        return cls(model=model)
