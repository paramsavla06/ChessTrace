"""
Unit tests for leakage-free three-way game partitioning engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import numpy as np
import pandas as pd
import pytest

from app.ml.split_utils import make_three_way_game_split, PartitionStats


@pytest.fixture
def synthetic_chess_dataset() -> pd.DataFrame:
    """Create a synthetic dataset with multi-ply games."""
    records = []
    # 100 unique games, each with varying plies (between 10 and 60)
    for g_idx in range(1, 101):
        gid = f"game_{g_idx:03d}"
        plies = 10 + (g_idx % 50)
        score = 1.0 if g_idx % 3 == 0 else (0.5 if g_idx % 3 == 1 else 0.0)
        for p in range(1, plies + 1):
            records.append({
                "game_id": gid,
                "ply": p,
                "game_result_score": score,
                "material_balance": np.random.randint(-5, 6),
                "think_time": float(np.random.randint(1, 30)),
            })
    return pd.DataFrame(records)


def test_three_way_split_disjointness(synthetic_chess_dataset):
    """Verify that all three partitions have zero overlapping game IDs."""
    train_df, val_df, test_df, stats = make_three_way_game_split(
        synthetic_chess_dataset,
        test_ratio=0.15,
        val_ratio=0.15,
        random_state=42,
    )

    train_ids = set(train_df["game_id"])
    val_ids = set(val_df["game_id"])
    test_ids = set(test_df["game_id"])

    # 1. Zero pairwise overlap
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

    # 2. Complete partition of all games
    all_partitioned_ids = train_ids | val_ids | test_ids
    assert all_partitioned_ids == set(synthetic_chess_dataset["game_id"])
    assert len(all_partitioned_ids) == 100

    # 3. Complete row conservation
    assert len(train_df) + len(val_df) + len(test_df) == len(synthetic_chess_dataset)

    # 4. Proportions match expectations
    assert stats.test_games == 15
    assert stats.val_games == 15
    assert stats.train_games == 70


def test_three_way_split_determinism(synthetic_chess_dataset):
    """Verify that identical random_state produces identical partitions."""
    train1, val1, test1, _ = make_three_way_game_split(synthetic_chess_dataset, random_state=99)
    train2, val2, test2, _ = make_three_way_game_split(synthetic_chess_dataset, random_state=99)

    assert set(train1["game_id"]) == set(train2["game_id"])
    assert set(val1["game_id"]) == set(val2["game_id"])
    assert set(test1["game_id"]) == set(test2["game_id"])


def test_three_way_split_different_seeds(synthetic_chess_dataset):
    """Verify that different random_state seeds produce different splits."""
    _, _, test1, _ = make_three_way_game_split(synthetic_chess_dataset, random_state=42)
    _, _, test2, _ = make_three_way_game_split(synthetic_chess_dataset, random_state=99)

    # With 100 games and 15 in test, two different seeds should not have identical test sets
    assert set(test1["game_id"]) != set(test2["game_id"])


def test_three_way_split_missing_game_id():
    """Verify error when 'game_id' column is missing."""
    df = pd.DataFrame({"col_a": [1, 2, 3]})
    with pytest.raises(ValueError, match="DataFrame must contain a 'game_id' column"):
        make_three_way_game_split(df)


def test_three_way_split_elo_subsets_preserve_disjointness(synthetic_chess_dataset):
    """Verify that ELO-filtered subsets of master partitions remain 100% disjoint."""
    # Assign synthetic ELO buckets
    buckets = ["<1000", "1000-1200", "1200-1400", "1400-1600", "1600-1800", "1800-2000", "2000+"]
    synthetic_chess_dataset["elo_bucket"] = [
        buckets[i % len(buckets)] for i in range(len(synthetic_chess_dataset))
    ]

    train_df, val_df, test_df, _ = make_three_way_game_split(
        synthetic_chess_dataset, test_ratio=0.15, val_ratio=0.15, random_state=42
    )

    for b in buckets:
        sub_train = train_df[train_df["elo_bucket"] == b]
        sub_val = val_df[val_df["elo_bucket"] == b]
        sub_test = test_df[test_df["elo_bucket"] == b]

        t_ids = set(sub_train["game_id"])
        v_ids = set(sub_val["game_id"])
        te_ids = set(sub_test["game_id"])

        assert t_ids.isdisjoint(v_ids), f"Leakage in ELO bucket {b} between train and val!"
        assert t_ids.isdisjoint(te_ids), f"Leakage in ELO bucket {b} between train and test!"
        assert v_ids.isdisjoint(te_ids), f"Leakage in ELO bucket {b} between val and test!"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))



