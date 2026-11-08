"""
Model Training Script for ChessTrace V2.

Loads processed feature Parquet datasets from data/processed/v2/, performs a
leakage-free 3-way game partition (Train 70% / Val 15% / Test 15%), fits the
WinCollapsePredictor general XGBoost model, fits 7 rating-bracket XGBoost models for
the ELO simulation matrix, saves all model artifacts to backend/app/ml/weights/v2/,
saves the untouched test partition for final evaluation, and generates an explicit
model manifest.

Usage:
    python backend/scripts/train_models.py --data-dir data/processed/v2 --weights-dir backend/app/ml/weights/v2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import numpy as np
import pandas as pd

from app.core.constants import ELO_BUCKETS
from app.ml.collapse_model import FEATURE_COLUMNS, WinCollapsePredictor
from app.ml.split_utils import make_three_way_game_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train_models")

DEFAULT_PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = DEFAULT_PROJECT_DIR / "data/processed/v2"
DEFAULT_WEIGHTS_DIR = DEFAULT_PROJECT_DIR / "backend/app/ml/weights/v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ChessTrace XGBoost models on processed feature dataset.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing processed Parquet feature chunks (default: data/processed/v2).",
    )
    parser.add_argument(
        "--weights-dir",
        type=Path,
        default=DEFAULT_WEIGHTS_DIR,
        help="Directory where trained model artifacts (.json) will be saved (default: backend/app/ml/weights/v2).",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Path where model_manifest.json will be written (default: weights-dir/model_manifest.json).",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Proportion of games reserved for final test set (default: 0.15).",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Proportion of games reserved for early-stopping validation (default: 0.15).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for deterministic group-level partitioning (default: 42).",
    )
    return parser.parse_args()


def train(
    data_dir: Path,
    weights_dir: Path,
    manifest_path: Path | None = None,
    test_ratio: float = 0.15,
    val_ratio: float = 0.15,
    random_state: int = 42,
) -> dict[str, Any]:
    start_time = time.time()
    logger.info("Locating processed feature files in %s...", data_dir.resolve())

    parquet_files = sorted(data_dir.glob("*.parquet"))
    # Exclude any previous test partition file if present in data_dir
    parquet_files = [f for f in parquet_files if not f.name.startswith("test_partition")]
    if not parquet_files:
        raise FileNotFoundError(f"No parquet chunks found in {data_dir.resolve()}! Run prepare_dataset.py first.")

    logger.info("Found %d parquet feature files. Determining partition splits by game_id...", len(parquet_files))
    weights_dir.mkdir(parents=True, exist_ok=True)
    required_cols = list(dict.fromkeys(["game_id", "game_result_score", "elo_bucket", "ply", "time_control"] + FEATURE_COLUMNS))

    # Fast memory-efficient scan of unique game_id
    all_game_ids_set: set[str] = set()
    total_samples = 0
    for pf in parquet_files:
        chunk_gids = pd.read_parquet(pf, columns=["game_id"])
        total_samples += len(chunk_gids)
        all_game_ids_set.update(chunk_gids["game_id"].dropna().unique())

    unique_games_list = np.array(sorted(all_game_ids_set))
    unique_games = len(unique_games_list)
    logger.info("Dataset inventory: %d move samples across %d unique games.", total_samples, unique_games)

    test_partition_path = weights_dir / "test_partition.parquet"
    if test_partition_path.exists():
        logger.info("Found existing held-out test partition at %s. Preserving partition immutability...", test_partition_path.name)
        test_df = pd.read_parquet(test_partition_path)
        test_gids = set(test_df["game_id"])
        dev_unique_games = np.array(sorted(all_game_ids_set - test_gids))
        rng = np.random.RandomState(random_state)
        shuffled_dev = dev_unique_games.copy()
        rng.shuffle(shuffled_dev)
        n_val = max(1, int(round(unique_games * val_ratio)))
        val_gids = set(shuffled_dev[:n_val])
        train_gids = set(shuffled_dev[n_val:])
    else:
        logger.info(
            "Creating three-way group split (Train: %.0f%% / Val: %.0f%% / Test: %.0f%%, seed=%d)...",
            (1.0 - test_ratio - val_ratio) * 100,
            val_ratio * 100,
            test_ratio * 100,
            random_state,
        )
        rng = np.random.RandomState(random_state)
        shuffled_all = unique_games_list.copy()
        rng.shuffle(shuffled_all)
        n_test = max(1, int(round(unique_games * test_ratio)))
        n_val = max(1, int(round(unique_games * val_ratio)))
        test_gids = set(shuffled_all[:n_test])
        val_gids = set(shuffled_all[n_test : n_test + n_val])
        train_gids = set(shuffled_all[n_test + n_val :])

    # Disjointness assertions
    assert train_gids.isdisjoint(val_gids), "LEAKAGE: train IDs intersect val IDs!"
    assert train_gids.isdisjoint(test_gids), "LEAKAGE: train IDs intersect test IDs!"
    assert val_gids.isdisjoint(test_gids), "LEAKAGE: val IDs intersect test IDs!"
    assert len(train_gids) + len(val_gids) + len(test_gids) == unique_games, "Game ID partition count mismatch!"

    # Save test partition if not already saved
    if not test_partition_path.exists():
        logger.info("Extracting and saving held-out test partition to %s...", test_partition_path.name)
        test_chunks = []
        for pf in parquet_files:
            c_df = pd.read_parquet(pf, columns=required_cols)
            mask = c_df["game_id"].isin(test_gids)
            if mask.any():
                test_chunks.append(c_df[mask])
        test_df = pd.concat(test_chunks, ignore_index=True)
        test_df.to_parquet(test_partition_path, index=False)
        del test_chunks
        logger.info("Saved held-out test partition (%d rows, %d games)", len(test_df), len(test_gids))

    # Memory downcasting type map
    DTYPE_MAP = {
        "material_balance": "int8",
        "white_material": "int8",
        "black_material": "int8",
        "white_mobility": "int16",
        "black_mobility": "int16",
        "white_center_control": "int8",
        "black_center_control": "int8",
        "white_pawn_shield": "int8",
        "black_pawn_shield": "int8",
        "white_passed_pawns": "int8",
        "black_passed_pawns": "int8",
        "white_isolated_pawns": "int8",
        "black_isolated_pawns": "int8",
        "white_doubled_pawns": "int8",
        "black_doubled_pawns": "int8",
        "think_time": "float32",
        "time_remaining": "float32",
        "is_time_pressure_120s": "int8",
        "is_time_pressure_60s": "int8",
        "is_time_pressure_30s": "int8",
        "time_usage_ratio": "float32",
        "running_avg_think_time": "float32",
        "think_time_deviation": "float32",
        "game_result_score": "float32",
        "ply": "int16",
        "elo_bucket": "category",
    }

    # Load validation set
    logger.info("Loading validation partition (%d target games)...", len(val_gids))
    val_chunks = []
    for pf in parquet_files:
        c_df = pd.read_parquet(pf, columns=required_cols)
        mask = c_df["game_id"].isin(val_gids)
        if mask.any():
            val_chunks.append(c_df[mask].astype({k: v for k, v in DTYPE_MAP.items() if k in c_df.columns}))
    val_df = pd.concat(val_chunks, ignore_index=True)
    del val_chunks
    logger.info("Validation partition loaded: %d rows (%d games)", len(val_df), val_df["game_id"].nunique())

    # Load training set
    logger.info("Loading training partition (%d target games)...", len(train_gids))
    train_chunks = []
    for pf in parquet_files:
        c_df = pd.read_parquet(pf, columns=required_cols)
        mask = c_df["game_id"].isin(train_gids)
        if mask.any():
            train_chunks.append(c_df[mask].astype({k: v for k, v in DTYPE_MAP.items() if k in c_df.columns}))
    train_df = pd.concat(train_chunks, ignore_index=True)
    del train_chunks
    logger.info("Training partition loaded: %d rows (%d games)", len(train_df), train_df["game_id"].nunique())

    test_id_fingerprint = hashlib.sha256("".join(sorted(test_gids)).encode()).hexdigest()[:16]

    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": "v2",
        "data_dir": str(data_dir.resolve()),
        "weights_dir": str(weights_dir.resolve()),
        "total_chunks": len(parquet_files),
        "total_samples": total_samples,
        "unique_games": unique_games,
        "target_variable": "game_result_score",
        "target_semantics": {
            "description": "Eventual game result from White's perspective",
            "values": {"1.0": "White win", "0.5": "Draw", "0.0": "Black win"},
        },
        "feature_columns": FEATURE_COLUMNS,
        "split_methodology": {
            "type": "Three-way disjoint group split by game_id",
            "random_state": random_state,
            "train_games": len(train_gids),
            "train_rows": len(train_df),
            "train_ratio": round(len(train_gids) / max(1, unique_games), 4),
            "val_games": len(val_gids),
            "val_rows": len(val_df),
            "val_ratio": round(len(val_gids) / max(1, unique_games), 4),
            "test_games": len(test_gids),
            "test_rows": len(test_df),
            "test_ratio": round(len(test_gids) / max(1, unique_games), 4),
            "test_partition_file": test_partition_path.name,
            "test_id_sha256_prefix": test_id_fingerprint,
            "leakage_checks_passed": True,
        },
        "hyperparameters": {
            "n_estimators": 250,
            "max_depth": 6,
            "learning_rate": 0.04,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "early_stopping_rounds": 20,
            "eval_metric": "rmse",
        },
        "models": {},
    }

    # 1. Train General Win/Collapse XGBoost Model
    general_model_path = weights_dir / "collapse_xgboost.json"
    logger.info("Initializing and training General WinCollapsePredictor (XGBoost)...")
    gen_t0 = time.time()
    general_predictor = WinCollapsePredictor()
    general_metrics = general_predictor.fit_partitions(train_df, val_df, random_state=random_state)
    general_predictor.save(general_model_path)
    gen_duration = round(time.time() - gen_t0, 2)
    logger.info(
        "Saved general model to %s (Val RMSE: %.4f | Val MAE: %.4f | Val R2: %.4f | Best Iter: %d | Time: %.1fs)",
        general_model_path.name,
        general_metrics.get("val_rmse", 0.0),
        general_metrics.get("val_mae", 0.0),
        general_metrics.get("val_r2", 0.0),
        general_metrics.get("best_iteration", 0),
        gen_duration,
    )

    manifest["models"]["general"] = {
        "artifact_file": general_model_path.name,
        "artifact_path": str(general_model_path.resolve()),
        "artifact_size_bytes": general_model_path.stat().st_size,
        "training_duration_seconds": gen_duration,
        "train_samples": len(train_df),
        "train_games": len(train_gids),
        "val_samples": len(val_df),
        "val_games": len(val_gids),
        "metrics": general_metrics,
    }

    # 2. Train 7 ELO Bracket Models for ELO Simulation Matrix
    if "elo_bucket" in train_df.columns:
        logger.info("Training ELO-Bracket Segmented XGBoost Models...")
        for bucket in ELO_BUCKETS:
            elo_train = train_df[train_df["elo_bucket"] == bucket].copy().reset_index(drop=True)
            elo_val = val_df[val_df["elo_bucket"] == bucket].copy().reset_index(drop=True)

            if len(elo_train) < 50 or len(elo_val) < 10:
                logger.warning(
                    "Not enough samples for ELO bucket %s (train: %d, val: %d), skipping.",
                    bucket, len(elo_train), len(elo_val),
                )
                continue

            logger.info(
                "Training XGBoost for ELO '%s' (%d train rows / %d games, %d val rows / %d games)...",
                bucket, len(elo_train), elo_train["game_id"].nunique(),
                len(elo_val), elo_val["game_id"].nunique(),
            )
            elo_t0 = time.time()
            elo_predictor = WinCollapsePredictor()
            elo_metrics = elo_predictor.fit_partitions(elo_train, elo_val, random_state=random_state)
            elo_duration = round(time.time() - elo_t0, 2)

            safe_bucket_name = bucket.replace("<", "under_").replace("+", "_plus").replace("-", "_to_")
            elo_weights_path = weights_dir / f"elo_xgboost_{safe_bucket_name}.json"
            elo_predictor.save(elo_weights_path)
            logger.info(
                "Saved ELO model artifact '%s' (Val RMSE: %.4f | Val MAE: %.4f | Val R2: %.4f | Best Iter: %d | Time: %.1fs)",
                elo_weights_path.name,
                elo_metrics.get("val_rmse", 0.0),
                elo_metrics.get("val_mae", 0.0),
                elo_metrics.get("val_r2", 0.0),
                elo_metrics.get("best_iteration", 0),
                elo_duration,
            )

            manifest["models"][f"elo_{bucket}"] = {
                "bucket": bucket,
                "safe_bucket_name": safe_bucket_name,
                "artifact_file": elo_weights_path.name,
                "artifact_path": str(elo_weights_path.resolve()),
                "artifact_size_bytes": elo_weights_path.stat().st_size,
                "training_duration_seconds": elo_duration,
                "train_samples": len(elo_train),
                "train_games": int(elo_train["game_id"].nunique()),
                "val_samples": len(elo_val),
                "val_games": int(elo_val["game_id"].nunique()),
                "metrics": elo_metrics,
            }

    total_duration = round(time.time() - start_time, 2)
    manifest["total_training_duration_seconds"] = total_duration

    if manifest_path is None:
        manifest_path = weights_dir / "model_manifest.json"

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Model training complete in %.1fs. Manifest saved to %s", total_duration, manifest_path.resolve())
    return manifest


def main():
    args = parse_args()
    train(
        args.data_dir,
        args.weights_dir,
        args.manifest_path,
        test_ratio=args.test_ratio,
        val_ratio=args.val_ratio,
        random_state=args.random_state,
    )


if __name__ == "__main__":
    main()
