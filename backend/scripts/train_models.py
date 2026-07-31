"""
Model Training Script for ChessTrace.

Loads processed feature Parquet datasets from data/processed/, fits the
WinCollapsePredictor XGBoost model, evaluates performance metrics, and saves the
model artifact to app/ml/weights/collapse_xgboost.json.

Usage:
    python scripts/train_models.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.ml.collapse_model import WinCollapsePredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train_models")

BASE_PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_PROJECT_DIR / "data/processed"
MODEL_OUTPUT_PATH = BASE_PROJECT_DIR / "backend/app/ml/weights/collapse_xgboost.json"


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
    logger.info("Dataset columns: %s", list(dataset.columns))

    logger.info("Initializing and training WinCollapsePredictor (XGBoost)...")
    predictor = WinCollapsePredictor()
    metrics = predictor.train_on_dataframe(dataset)

    logger.info("Training finished! Metrics: %s", metrics)

    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    predictor.save(MODEL_OUTPUT_PATH)
    logger.info("Saved trained model artifact to %s", MODEL_OUTPUT_PATH.absolute())


if __name__ == "__main__":
    train()
