"""
Model Training Script for ChessTrace.

Loads processed feature Parquet datasets from data/processed/, fits the
WinCollapsePredictor general XGBoost model, fits 7 rating-bracket XGBoost models for
the ELO simulation matrix, and saves all model artifacts to app/ml/weights/.

Usage:
    python scripts/train_models.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.core.constants import ELO_BUCKETS
from app.ml.collapse_model import WinCollapsePredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train_models")

BASE_PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_PROJECT_DIR / "data/processed"
WEIGHTS_DIR = BASE_PROJECT_DIR / "backend/app/ml/weights"
MODEL_OUTPUT_PATH = WEIGHTS_DIR / "collapse_xgboost.json"


def train():
    logger.info("Locating processed feature files in %s...", PROCESSED_DIR.absolute())

    parquet_files = list(PROCESSED_DIR.glob("*.parquet"))
    if not parquet_files:
        logger.error("No parquet files found in %s! Run prepare_dataset.py first.", PROCESSED_DIR)
        return

    logger.info("Found %d parquet feature files. Loading into DataFrame...", len(parquet_files))

    dfs = [pd.read_parquet(f) for f in parquet_files]
    dataset = pd.concat(dfs, ignore_index=True)

    logger.info("Dataset loaded successfully! Total move samples (plies): %d", len(dataset))
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Train General Win/Collapse XGBoost Model
    logger.info("Initializing and training General WinCollapsePredictor (XGBoost)...")
    general_predictor = WinCollapsePredictor()
    general_metrics = general_predictor.train_on_dataframe(dataset)
    general_predictor.save(MODEL_OUTPUT_PATH)
    logger.info("Saved general trained model artifact to %s (RMSE: %.4f)", MODEL_OUTPUT_PATH.name, general_metrics.get("rmse", 0))

    # 2. Train 7 ELO Bracket Models for ELO Simulation Matrix
    if "elo_bucket" in dataset.columns:
        logger.info("Training ELO-Bracket Segmented XGBoost Models...")
        for bucket in ELO_BUCKETS:
            elo_df = dataset[dataset["elo_bucket"] == bucket]
            if len(elo_df) < 100:
                logger.warning("Not enough samples for ELO bucket %s (count: %d), skipping.", bucket, len(elo_df))
                continue

            logger.info("Training XGBoost model for ELO bucket '%s' (%d samples)...", bucket, len(elo_df))
            elo_predictor = WinCollapsePredictor()
            elo_metrics = elo_predictor.train_on_dataframe(elo_df)

            safe_bucket_name = bucket.replace("<", "under_").replace("+", "_plus").replace("-", "_to_")
            elo_weights_path = WEIGHTS_DIR / f"elo_xgboost_{safe_bucket_name}.json"
            elo_predictor.save(elo_weights_path)
            logger.info("Saved ELO model artifact '%s' (RMSE: %.4f)", elo_weights_path.name, elo_metrics.get("rmse", 0))


if __name__ == "__main__":
    train()
