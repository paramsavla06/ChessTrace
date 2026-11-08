"""
Leakage-Free Three-Way Game Partitioning Engine.

Splits chess datasets by unique `game_id` so that all plies belonging to a given
game remain strictly confined to exactly one partition:
  1. Train partition (e.g. 70% of games): Used strictly for gradient updates.
  2. Validation partition (e.g. 15% of games): Used strictly for early-stopping evaluation.
  3. Final-Test partition (e.g. 15% of games): Completely held-out, untouched until final evaluation.

Guarantees:
  - set(train_game_ids) ∩ set(val_game_ids) = ∅
  - set(train_game_ids) ∩ set(test_game_ids) = ∅
  - set(val_game_ids) ∩ set(test_game_ids) = ∅
  - len(train_rows) + len(val_rows) + len(test_rows) == total_rows
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PartitionStats:
    train_games: int
    train_rows: int
    val_games: int
    val_rows: int
    test_games: int
    test_rows: int
    total_games: int
    total_rows: int
    test_ratio: float
    val_ratio: float
    train_ratio: float
    random_state: int


def make_three_way_game_split(
    df: pd.DataFrame,
    test_ratio: float = 0.15,
    val_ratio: float = 0.15,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, PartitionStats]:
    """
    Split a DataFrame into three strictly disjoint partitions by `game_id`.

    Args:
        df: Input DataFrame containing at least a 'game_id' column.
        test_ratio: Proportion of unique games assigned to the final test partition (default: 0.15).
        val_ratio: Proportion of unique games assigned to early-stopping validation (default: 0.15).
        random_state: Seed for deterministic group shuffling (default: 42).

    Returns:
        tuple of (train_df, val_df, test_df, partition_stats)
    """
    if "game_id" not in df.columns:
        raise ValueError("DataFrame must contain a 'game_id' column for group-aware splitting.")

    if not (0.0 < test_ratio < 0.5) or not (0.0 < val_ratio < 0.5) or not (test_ratio + val_ratio < 0.8):
        raise ValueError(
            f"Invalid split ratios: test_ratio={test_ratio}, val_ratio={val_ratio}. "
            "Ratios must leave a substantial training partition."
        )

    # 1. Extract unique games deterministically
    unique_games = np.array(sorted(df["game_id"].unique()))
    total_unique_games = len(unique_games)
    total_rows = len(df)

    if total_unique_games < 3:
        raise ValueError(f"Need at least 3 unique games to create 3 partitions, got {total_unique_games}.")

    # 2. Shuffle unique games with deterministic seed
    rng = np.random.RandomState(random_state)
    shuffled_games = unique_games.copy()
    rng.shuffle(shuffled_games)

    # 3. Compute partition boundaries
    n_test = max(1, int(round(total_unique_games * test_ratio)))
    n_val = max(1, int(round(total_unique_games * val_ratio)))
    n_train = total_unique_games - n_test - n_val

    if n_train < 1:
        raise ValueError("Training partition would be empty. Reduce test_ratio or val_ratio.")

    test_game_ids = set(shuffled_games[:n_test])
    val_game_ids = set(shuffled_games[n_test : n_test + n_val])
    train_game_ids = set(shuffled_games[n_test + n_val:])

    # 4. Strict mathematical disjointness assertions
    assert train_game_ids.isdisjoint(val_game_ids), "LEAKAGE: train IDs intersect validation IDs!"
    assert train_game_ids.isdisjoint(test_game_ids), "LEAKAGE: train IDs intersect test IDs!"
    assert val_game_ids.isdisjoint(test_game_ids), "LEAKAGE: validation IDs intersect test IDs!"
    assert len(train_game_ids) + len(val_game_ids) + len(test_game_ids) == total_unique_games, (
        "Partition sum does not equal total unique games!"
    )

    # 5. Filter DataFrames
    test_df = df[df["game_id"].isin(test_game_ids)].copy().reset_index(drop=True)
    val_df = df[df["game_id"].isin(val_game_ids)].copy().reset_index(drop=True)
    train_df = df[df["game_id"].isin(train_game_ids)].copy().reset_index(drop=True)

    # 6. Verify row-level disjointness and completeness
    test_rows = len(test_df)
    val_rows = len(val_df)
    train_rows = len(train_df)

    assert set(train_df["game_id"]).isdisjoint(set(val_df["game_id"])), "LEAKAGE in train/val rows!"
    assert set(train_df["game_id"]).isdisjoint(set(test_df["game_id"])), "LEAKAGE in train/test rows!"
    assert set(val_df["game_id"]).isdisjoint(set(test_df["game_id"])), "LEAKAGE in val/test rows!"
    assert train_rows + val_rows + test_rows == total_rows, (
        f"Row count mismatch: {train_rows} + {val_rows} + {test_rows} != {total_rows}"
    )

    stats = PartitionStats(
        train_games=len(train_game_ids),
        train_rows=train_rows,
        val_games=len(val_game_ids),
        val_rows=val_rows,
        test_games=len(test_game_ids),
        test_rows=test_rows,
        total_games=total_unique_games,
        total_rows=total_rows,
        test_ratio=round(len(test_game_ids) / total_unique_games, 4),
        val_ratio=round(len(val_game_ids) / total_unique_games, 4),
        train_ratio=round(len(train_game_ids) / total_unique_games, 4),
        random_state=random_state,
    )

    logger.info(
        "Three-way group split created (seed=%d): "
        "Train: %d games (%d rows, %.1f%%) | "
        "Val: %d games (%d rows, %.1f%%) | "
        "Test: %d games (%d rows, %.1f%%)",
        random_state,
        stats.train_games, stats.train_rows, stats.train_ratio * 100,
        stats.val_games, stats.val_rows, stats.val_ratio * 100,
        stats.test_games, stats.test_rows, stats.test_ratio * 100,
    )

    return train_df, val_df, test_df, stats

