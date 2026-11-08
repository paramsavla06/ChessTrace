"""
Dataset Validation & Integrity Verification Engine for ChessTrace.

Performs thorough quantitative verification of processed Parquet chunks:
- Validates canonical 34-column schema across all chunks
- Reconciles total games, unique game IDs, and plies against checkpoints
- Verifies ELO distribution, time controls, and clock telemetry
- Detects missing/null/infinite values or corrupted records
- Detects duplicate game IDs across chunk boundaries
- Generates structured validation summary and dataset manifest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.constants import ELO_BUCKETS
from scripts.prepare_dataset import FEATURE_SCHEMA_COLUMNS, PreprocessingCheckpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("validate_dataset")

BASE_PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = BASE_PROJECT_DIR / "data/processed/v2"
DEFAULT_CHECKPOINT_DIR = BASE_PROJECT_DIR / "data/checkpoints"
DEFAULT_MANIFEST_PATH = BASE_PROJECT_DIR / "data/metadata/dataset_manifest_v2.json"


def validate_dataset(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    target_games: int | None = None,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    """
    Validate all Parquet chunks in dataset_dir and verify consistency with checkpoint.
    """
    logger.info("Validating dataset in %s...", dataset_dir.resolve())
    if not dataset_dir.exists():
        logger.error("Dataset directory does not exist: %s", dataset_dir)
        return {"valid": False, "error": "Dataset directory not found"}

    parquet_files = sorted(dataset_dir.glob("features_chunk_*.parquet"))
    if not parquet_files:
        logger.error("No parquet chunks found in %s", dataset_dir)
        return {"valid": False, "error": "No parquet files found"}

    logger.info("Discovered %d Parquet chunk files.", len(parquet_files))

    total_rows = 0
    total_bytes = 0
    all_game_ids: set[str] = set()
    duplicate_game_ids = 0
    chunk_summaries = []
    elo_distribution: dict[str, int] = {b: 0 for b in ELO_BUCKETS}
    tc_distribution: dict[str, int] = {}
    outcome_distribution: dict[str, int] = {"1-0": 0, "0-1": 0, "1/2-1/2": 0}
    clock_telemetry_rows = 0
    null_counts: dict[str, int] = {col: 0 for col in FEATURE_SCHEMA_COLUMNS}
    infinite_counts: dict[str, int] = {col: 0 for col in FEATURE_SCHEMA_COLUMNS}
    schema_errors = []

    for chunk_idx, pf in enumerate(parquet_files, start=1):
        file_bytes = pf.stat().st_size
        total_bytes += file_bytes

        try:
            df = pd.read_parquet(pf)
        except Exception as read_err:
            schema_errors.append(f"Unreadable chunk {pf.name}: {read_err}")
            continue

        # Validate schema
        missing_cols = [c for c in FEATURE_SCHEMA_COLUMNS if c not in df.columns]
        if missing_cols:
            schema_errors.append(f"{pf.name} missing columns: {missing_cols}")

        rows = len(df)
        total_rows += rows

        # Check nulls and infinite values
        chunk_nulls = df[FEATURE_SCHEMA_COLUMNS].isnull().sum()
        for col, cnt in chunk_nulls.items():
            null_counts[col] += int(cnt)

        # Numerical columns infinite check
        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if col in infinite_counts:
                inf_cnt = int(np.isinf(df[col]).sum())
                infinite_counts[col] += inf_cnt

        # Unique game IDs & duplicates
        chunk_games = df["game_id"].unique()
        for gid in chunk_games:
            if gid in all_game_ids:
                duplicate_game_ids += 1
            else:
                all_game_ids.add(gid)

        # ELO distribution
        if "elo_bucket" in df.columns:
            for bucket, count in df["elo_bucket"].value_counts().items():
                elo_distribution[str(bucket)] = elo_distribution.get(str(bucket), 0) + int(count)

        # Time control distribution
        if "time_control" in df.columns:
            for tc, count in df["time_control"].value_counts().items():
                tc_distribution[str(tc)] = tc_distribution.get(str(tc), 0) + int(count)

        # Outcome distribution (from game_result_score)
        if "game_result_score" in df.columns:
            white_wins = int((df["game_result_score"] == 1.0).sum())
            black_wins = int((df["game_result_score"] == 0.0).sum())
            draws = int((df["game_result_score"] == 0.5).sum())
            outcome_distribution["1-0"] += white_wins
            outcome_distribution["0-1"] += black_wins
            outcome_distribution["1/2-1/2"] += draws

        # Clock telemetry (think_time > 0 or has remaining clock)
        if "think_time" in df.columns:
            clock_telemetry_rows += int((df["think_time"] > 0).sum())

        chunk_summaries.append({
            "chunk_name": pf.name,
            "rows": rows,
            "unique_games": len(chunk_games),
            "size_mb": round(file_bytes / (1024 * 1024), 2),
        })

    # Checkpoint consistency check
    checkpoint_file = checkpoint_dir / f"checkpoint_{dataset_dir.name}.json"
    cp_info = {}
    reconciled_games = False
    reconciled_plies = False

    if checkpoint_file.exists():
        try:
            with checkpoint_file.open("r", encoding="utf-8") as f:
                cp_data = json.load(f)
            cp_processed = cp_data.get("total_games_processed")
            cp_plies = cp_data.get("total_plies_extracted")
            reconciled_games = (len(all_game_ids) == cp_processed)
            reconciled_plies = (total_rows == cp_plies)

            cp_info = {
                "checkpoint_exists": True,
                "checkpoint_processed_games": cp_processed,
                "checkpoint_plies": cp_plies,
                "last_completed_chunk": cp_data.get("last_completed_chunk"),
                "reconciled_games": reconciled_games,
                "reconciled_plies": reconciled_plies,
                "next_game_byte_offset": cp_data.get("next_game_byte_offset"),
                "pgn_path": cp_data.get("pgn_path"),
            }
        except Exception as exc:
            cp_info = {"checkpoint_exists": False, "error": f"Unreadable checkpoint JSON: {exc}"}
    else:
        cp_info = {"checkpoint_exists": False}

    unique_games_count = len(all_game_ids)
    clock_pct = round((clock_telemetry_rows / max(1, total_rows)) * 100.0, 2)
    has_nulls = any(cnt > 0 for cnt in null_counts.values())
    has_infs = any(cnt > 0 for cnt in infinite_counts.values())
    is_valid = len(schema_errors) == 0 and not has_nulls and not has_infs and duplicate_game_ids == 0 and unique_games_count > 0

    if target_games:
        if unique_games_count < target_games:
            logger.warning(
                "Processed games (%d) is below target (%d).", unique_games_count, target_games
            )
            is_valid = False

    report: dict[str, Any] = {
        "valid": is_valid,
        "dataset_directory": str(dataset_dir.resolve()),
        "total_parquet_chunks": len(parquet_files),
        "total_dataset_size_mb": round(total_bytes / (1024 * 1024), 2),
        "total_move_samples": total_rows,
        "total_unique_games": unique_games_count,
        "duplicate_game_ids": duplicate_game_ids,
        "clock_telemetry_percentage": clock_pct,
        "schema_errors": schema_errors,
        "null_counts": {k: v for k, v in null_counts.items() if v > 0},
        "infinite_counts": {k: v for k, v in infinite_counts.items() if v > 0},
        "elo_distribution": elo_distribution,
        "time_control_distribution": tc_distribution,
        "outcome_distribution": outcome_distribution,
        "checkpoint_status": cp_info,
        "chunk_summaries": chunk_summaries,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("=" * 60)
    logger.info("DATASET VALIDATION REPORT")
    logger.info("=" * 60)
    logger.info("Validation Result: %s", "PASSED" if is_valid else "FAILED")
    logger.info("Chunks: %d | Total Plies: %s | Unique Games: %s", len(parquet_files), f"{total_rows:,}", f"{unique_games_count:,}")
    logger.info("Dataset Size: %.2f MB | Clock Telemetry: %.1f%%", total_bytes / (1024 * 1024), clock_pct)
    logger.info("Duplicates: %d | Null Values: %s | Infinite Values: %s", duplicate_game_ids, "None" if not has_nulls else "Detected", "None" if not has_infs else "Detected")
    logger.info("Reconciled with checkpoint: Games=%s, Plies=%s", reconciled_games, reconciled_plies)
    logger.info("ELO Distribution: %s", elo_distribution)
    logger.info("=" * 60)

    if manifest_output:
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Saved dataset manifest to %s", manifest_output.resolve())

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChessTrace Dataset Validator")
    parser.add_argument("--dataset-dir", "--data-dir", dest="dataset_dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--target-games", type=int, default=None)
    parser.add_argument("--manifest-output", type=Path, default=None)
    args = parser.parse_args()

    rep = validate_dataset(args.dataset_dir, args.checkpoint_dir, args.target_games, args.manifest_output)
    print(json.dumps(rep, indent=2))
    sys.exit(0 if rep.get("valid") else 1)
