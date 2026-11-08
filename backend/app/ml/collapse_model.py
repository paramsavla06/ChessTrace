"""
XGBoost Win Probability & Collapse Predictor.

Trains and evaluates XGBoost models predicting White-relative win probability
and computing time-pressure-weighted collapse risk metrics from positional
and clock feature vectors.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

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
V2_WEIGHTS_PATH = Path(__file__).resolve().parent / "weights" / "v2" / "collapse_xgboost.json"
_GLOBAL_MODEL: xgb.XGBRegressor | None = None


def resolve_model_weights_path() -> Path:
    """
    Resolve active model weights path.
    V2 is the authoritative, permanent model version.
    V1 fallback is ONLY allowed if CHESSTRACE_MODEL_VERSION is explicitly set to 'v1'.
    Automatic/silent fallback to V1 when V2 is missing or corrupt is strictly prohibited.
    """
    pref = os.environ.get("CHESSTRACE_MODEL_VERSION", "v2").lower()
    if pref == "v1":
        if not DEFAULT_WEIGHTS_PATH.exists():
            err_msg = f"Explicitly requested V1 compatibility model artifact not found at: {DEFAULT_WEIGHTS_PATH}"
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)
        logger.warning(
            "Using explicitly requested legacy V1 model artifact: %s (Compatibility mode)",
            DEFAULT_WEIGHTS_PATH,
        )
        return DEFAULT_WEIGHTS_PATH

    # Authoritative V2 resolution
    if not V2_WEIGHTS_PATH.exists():
        err_msg = (
            f"Authoritative ChessTrace V2 model artifact is missing at: {V2_WEIGHTS_PATH}. "
            "Automatic fallback to legacy V1 is strictly prohibited. "
            "Ensure existing V2 trained artifacts are present under weights/v2/."
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    logger.info("Using authoritative ChessTrace V2 model artifact: %s", V2_WEIGHTS_PATH)
    return V2_WEIGHTS_PATH


def get_shared_model() -> xgb.XGBRegressor:
    """Return a globally cached XGBoost model instance, loading from weights."""
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is not None:
        return _GLOBAL_MODEL
    weights_path = resolve_model_weights_path()
    try:
        loaded = xgb.XGBRegressor()
        loaded.load_model(str(weights_path))
        _GLOBAL_MODEL = loaded
        active_version = "V1" if "v2" not in str(weights_path) else "V2"
        logger.info(
            "Loaded shared XGBoost model [Version=%s] from %s",
            active_version,
            weights_path,
        )
    except Exception as exc:
        err_msg = f"Failed to load authoritative model artifact from {weights_path}: {exc}"
        logger.critical(err_msg)
        raise RuntimeError(err_msg) from exc
    return _GLOBAL_MODEL


def set_shared_model(model: xgb.XGBRegressor | None) -> None:
    """Explicitly update the globally cached XGBoost model singleton."""
    global _GLOBAL_MODEL
    _GLOBAL_MODEL = model


def get_model_diagnostics() -> dict[str, Any]:
    """Return runtime diagnostic metadata for model loading and active weights."""
    weights_path = resolve_model_weights_path()
    is_v2 = "v2" in str(weights_path)
    return {
        "active_model_version": "v2" if is_v2 else "v1",
        "authoritative_v2": is_v2,
        "artifact_path": str(weights_path),
        "artifact_exists": weights_path.exists(),
        "model_loaded": _GLOBAL_MODEL is not None,
    }


@dataclass(slots=True, frozen=True)
class PredictionResult:
    """
    Prediction result carrying both statistically accurate expected-score semantics
    and backward-compatible win_probability / collapse_probability aliases.
    
    Target Semantics:
    - expected_score: Expected match points from White's perspective: E[Y] = P(White Win) + 0.5 * P(Draw).
    - black_expected_score: Expected match points from Black's perspective: 1.0 - expected_score.
    - collapse_risk_index: Analytical vulnerability index [0.05, 0.95] for White based on
      game tension, score deficit, and clock stress multiplier.
    - black_collapse_risk_index: Analytical vulnerability index [0.05, 0.95] for Black.
    - win_probability: Backward-compatible alias for expected_score.
    - collapse_probability: Backward-compatible alias for collapse_risk_index.
    - black_collapse_probability: Backward-compatible alias for black_collapse_risk_index.
    """
    win_probability: float
    collapse_probability: float
    time_pressure_risk_multiplier: float
    black_collapse_probability: float = 0.0
    expected_score: float = 0.0
    black_expected_score: float = 0.0
    collapse_risk_index: float = 0.0
    black_collapse_risk_index: float = 0.0


class WinCollapsePredictor:
    """
    Predictor service running XGBoost inference on position + time features.
    
    Target Semantics:
    - Target `game_result_score` in training data is 1.0 for White win, 0.5 for draw, 0.0 for Black win.
    - The model outputs conditional expected score E[Score|X] in [0, 1] from White's perspective.
    - Collapse risk is an analytical heuristic index (not a calibrated probability), capturing
      structural vulnerability under acute time pressure and disadvantage.
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

        white_expected_score = win_prob
        black_expected_score = float(round(1.0 - win_prob, 4))

        return PredictionResult(
            win_probability=win_prob,
            collapse_probability=white_collapse,
            time_pressure_risk_multiplier=time_mult,
            black_collapse_probability=black_collapse,
            expected_score=white_expected_score,
            black_expected_score=black_expected_score,
            collapse_risk_index=white_collapse,
            black_collapse_risk_index=black_collapse,
        )

    def fit_partitions(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        random_state: int = 42,
    ) -> dict[str, Any]:
        """
        Train XGBoost Regressor directly on pre-partitioned train and val sets.
        Enforces strict disjointness assertion and zero leakage.
        """
        if "game_id" in train_df.columns and "game_id" in val_df.columns:
            train_gids = set(train_df["game_id"])
            val_gids = set(val_df["game_id"])
            overlap = train_gids & val_gids
            if overlap:
                raise ValueError(f"DATA LEAKAGE DETECTED: {len(overlap)} games in both train and validation partitions!")
            logger.info(
                "Training with pre-split partitions: %d train rows (%d games) | %d val rows (%d games) | 0 overlapping",
                len(train_df), len(train_gids), len(val_df), len(val_gids)
            )

        X_train = train_df[FEATURE_COLUMNS]
        y_train = train_df["game_result_score"].astype(float)
        X_val = val_df[FEATURE_COLUMNS]
        y_val = val_df["game_result_score"].astype(float)

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

        best_iteration = int(getattr(model, "best_iteration", model.n_estimators))
        val_preds = np.clip(model.predict(X_val), 0.0, 1.0)
        train_preds = np.clip(model.predict(X_train), 0.0, 1.0)

        train_rmse = float(np.sqrt(mean_squared_error(y_train, train_preds)))
        val_rmse = float(np.sqrt(mean_squared_error(y_val, val_preds)))
        val_mae = float(mean_absolute_error(y_val, val_preds))
        val_r2 = float(r2_score(y_val, val_preds))

        logger.info(
            "XGBoost fit complete: Train RMSE: %.4f | Val RMSE: %.4f | Val MAE: %.4f | Val R2: %.4f | Best iter: %d",
            train_rmse, val_rmse, val_mae, val_r2, best_iteration,
        )
        return {
            "train_rmse": train_rmse,
            "val_rmse": val_rmse,
            "val_mae": val_mae,
            "val_r2": val_r2,
            "rmse": val_rmse,
            "best_iteration": best_iteration,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "train_games": int(train_df["game_id"].nunique()) if "game_id" in train_df.columns else -1,
            "val_games": int(val_df["game_id"].nunique()) if "game_id" in val_df.columns else -1,
        }

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
        df = df.reset_index(drop=True)
        X = df[FEATURE_COLUMNS]
        y = df["game_result_score"].astype(float)

        if "game_id" in df.columns:
            gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
            train_idx, val_idx = next(gss.split(X, y, groups=df["game_id"]))
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            train_game_ids = set(df.iloc[train_idx]["game_id"].unique())
            val_game_ids = set(df.iloc[val_idx]["game_id"].unique())
            leakage = train_game_ids & val_game_ids
            if leakage:
                logger.error("DATA LEAKAGE DETECTED: %d game IDs in both train and val!", len(leakage))
            logger.info(
                "Using GroupShuffleSplit on 'game_id' (%d train samples / %d games, %d val samples / %d games, 0 leaking)",
                len(X_train), len(train_game_ids), len(X_val), len(val_game_ids),
            )
        else:
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

        best_iteration = getattr(model, "best_iteration", model.n_estimators)

        val_preds = np.clip(model.predict(X_val), 0.0, 1.0)
        train_preds = np.clip(model.predict(X_train), 0.0, 1.0)

        train_rmse = float(np.sqrt(mean_squared_error(y_train, train_preds)))
        val_rmse = float(np.sqrt(mean_squared_error(y_val, val_preds)))
        val_mae = float(mean_absolute_error(y_val, val_preds))
        val_r2 = float(r2_score(y_val, val_preds))

        logger.info(
            "XGBoost trained successfully. Train RMSE: %.4f | Val RMSE: %.4f | Val MAE: %.4f | Val R2: %.4f | Best iter: %d",
            train_rmse,
            val_rmse,
            val_mae,
            val_r2,
            best_iteration,
        )
        return {
            "train_rmse": train_rmse,
            "val_rmse": val_rmse,
            "val_mae": val_mae,
            "val_r2": val_r2,
            "rmse": val_rmse,
            "best_iteration": best_iteration,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
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
