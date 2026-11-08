"""
Comprehensive test suite for Phase 1: Dataset Preprocessing, Game ID Extraction,
Atomic Chunking, and Checkpointing / Resumability.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

import chess.pgn
import pandas as pd
import pytest

from scripts.prepare_dataset import (
    FEATURE_SCHEMA_COLUMNS,
    PGNStreamReader,
    PreprocessingCheckpoint,
    extract_game_id,
    extract_game_rows,
    get_elo_bucket,
    get_result_score,
    process_pgn_file,
    write_parquet_chunk,
)


# Controlled multi-scenario synthetic PGN text
SAMPLE_SYNTHETIC_PGN = """[Event "Normal Rated Game"]
[Site "https://lichess.org/a1b2c3d4"]
[Date "2017.11.01"]
[White "PlayerOne"]
[Black "PlayerTwo"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1520"]
[TimeControl "300+0"]

1. e4 { [%clk 0:05:00] } e5 { [%clk 0:05:00] } 2. Nf3 { [%clk 0:04:58] } Nc6 { [%clk 0:04:57] } 3. Bc4 { [%clk 0:04:55] } Bc5 { [%clk 0:04:50] } 4. d3 { [%clk 0:04:50] } Nf6 { [%clk 0:04:48] } 1-0

[Event "Game Without Clock Telemetry"]
[Site "https://lichess.org/e5f6g7h8"]
[Date "2017.11.01"]
[White "MasterA"]
[Black "MasterB"]
[Result "1/2-1/2"]
[WhiteElo "2150"]
[BlackElo "2180"]
[TimeControl "-"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 1/2-1/2

[Event "Malformed Game - Syntax Error"]
[Site "https://lichess.org/badgame1"]
[White "Corrupted"]
[Black "User"]
[Result "*"]
[SetUp "1"]
[FEN "invalid fen 8 8 8"]

1. e4 e5 *

[Event "Incomplete Truncated PGN"]
[Site "https://lichess.org/trunc001"]
[White "PlayerX"]
[Black "PlayerY"]
[Result "*"]

1. c4 c5 2. Nc3 Nc6

[Event "Missing Headers Fallback ID"]
[White "Novice"]
[Black "Beginner"]
[Result "0-1"]
[WhiteElo "920"]
[BlackElo "980"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 0-1

[Event "Duplicate of First Game"]
[Site "https://lichess.org/a1b2c3d4"]
[Date "2017.11.01"]
[White "PlayerOne"]
[Black "PlayerTwo"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1520"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 1-0

[Event "High Rating Blitz Game"]
[Site "https://lichess.org/grandm11"]
[Date "2017.11.02"]
[White "GrandmasterW"]
[Black "GrandmasterB"]
[Result "0-1"]
[WhiteElo "2450"]
[BlackElo "2480"]
[TimeControl "180+2"]

1. e4 c5 { [%clk 0:03:00] } 2. Nf3 d6 { [%clk 0:03:01] } 3. d4 cxd4 { [%clk 0:02:58] } 0-1
"""


@pytest.fixture
def temp_pgn_file(tmp_path: Path) -> Path:
    """Write synthetic PGN to a temporary file."""
    pgn_path = tmp_path / "test_games.pgn"
    pgn_path.write_text(SAMPLE_SYNTHETIC_PGN, encoding="utf-8")
    return pgn_path


def test_game_id_extraction_and_fallback():
    """Verify Lichess Site URL extraction and deterministic fallback."""
    # 1. Standard Lichess Site URL
    pgn_with_url = '[Event "Test"]\n[Site "https://lichess.org/l4jZLpdZ"]\n\n1. e4 e5 *'
    game1 = chess.pgn.read_game(io.StringIO(pgn_with_url))
    assert game1 is not None
    assert extract_game_id(game1) == "l4jZLpdZ"

    # 2. Missing Site header -> deterministic fallback hash
    pgn_no_site = '[Event "Test"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n1. d4 d5 *'
    game2 = chess.pgn.read_game(io.StringIO(pgn_no_site))
    assert game2 is not None
    gid2 = extract_game_id(game2)
    assert len(gid2) == 12
    # Ensure deterministic stability
    game2_repeat = chess.pgn.read_game(io.StringIO(pgn_no_site))
    assert extract_game_id(game2_repeat) == gid2


def test_feature_extraction_clock_and_untimed():
    """Verify feature extraction for games with clock telemetry and games without."""
    # Timed game
    timed_pgn = (
        '[Event "Timed"]\n[Site "https://lichess.org/timed001"]\n[WhiteElo "1650"]\n[BlackElo "1670"]\n'
        '[TimeControl "300+0"]\n\n1. e4 { [%clk 0:05:00] } e5 { [%clk 0:05:00] } 2. Nf3 { [%clk 0:04:55] } *'
    )
    g_timed = chess.pgn.read_game(io.StringIO(timed_pgn))
    assert g_timed is not None
    rows_timed = extract_game_rows(g_timed, "timed001")
    assert len(rows_timed) == 3
    assert rows_timed[0]["game_id"] == "timed001"
    assert rows_timed[2]["think_time"] == 5.0  # 300s - 295s = 5s
    assert rows_timed[2]["time_remaining"] == 295.0

    # Untimed game
    untimed_pgn = '[Event "Untimed"]\n[Site "https://lichess.org/untimed1"]\n\n1. e4 e5 2. Nf3 *'
    g_untimed = chess.pgn.read_game(io.StringIO(untimed_pgn))
    assert g_untimed is not None
    rows_untimed = extract_game_rows(g_untimed, "untimed1")
    assert len(rows_untimed) == 3
    assert rows_untimed[0]["think_time"] == 0.0
    assert rows_untimed[0]["time_remaining"] == 0.0
    assert rows_untimed[0]["is_time_pressure_30s"] is False


def test_pgn_stream_reader_byte_offsets(temp_pgn_file: Path):
    """Verify PGNStreamReader yields non-empty games with valid incremental byte offsets."""
    reader = PGNStreamReader(temp_pgn_file)
    games_read = 0
    prev_offset = -1
    offsets = []

    while True:
        res = reader.read_game()
        if res is None:
            break
        raw_text, start_off, next_off = res
        assert "[Event " in raw_text
        assert start_off > prev_offset
        assert next_off > start_off
        prev_offset = start_off
        offsets.append((start_off, next_off))
        games_read += 1

    reader.close()
    assert games_read == 7  # 7 games total in synthetic PGN

    # Verify seeking to offset of game 2 directly reads game 2
    g2_start = offsets[1][0]
    reader2 = PGNStreamReader(temp_pgn_file, start_byte_offset=g2_start)
    res2 = reader2.read_game()
    assert res2 is not None
    assert 'Game Without Clock Telemetry' in res2[0]
    reader2.close()


def test_chunking_atomic_and_continuous(temp_pgn_file: Path, tmp_path: Path):
    """Verify atomic chunk creation, continuous numbering, and partial chunk retention."""
    output_dir = tmp_path / "processed_test"
    checkpoint_dir = tmp_path / "checkpoints_test"

    # Process with chunk_size=2 games per chunk
    summary = process_pgn_file(
        pgn_path=temp_pgn_file,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        max_games=10,
        chunk_size=2,
        resume=False,
    )

    assert summary["status"] == "success"
    # Games: 1 (normal), 2 (untimed), 3 (malformed-rejected), 4 (incomplete-processed),
    # 5 (novice), 6 (duplicate of 1 - skipped), 7 (grandmaster)
    # Total processed valid games: 5 games -> chunk_001 (2 games), chunk_002 (2 games), chunk_003 (1 game partial)
    chunks = sorted(output_dir.glob("features_chunk_*.parquet"))
    assert len(chunks) == 3
    assert chunks[0].name == "features_chunk_001.parquet"
    assert chunks[1].name == "features_chunk_002.parquet"
    assert chunks[2].name == "features_chunk_003.parquet"

    # Verify schema of all chunks
    for c in chunks:
        df = pd.read_parquet(c)
        assert not df.empty
        assert list(df.columns) == FEATURE_SCHEMA_COLUMNS
        assert "game_id" in df.columns
        assert df["game_id"].nunique() >= 1


def test_checkpointing_interruption_and_resumption(temp_pgn_file: Path, tmp_path: Path):
    """Verify that processing can be stopped and resumed without duplicate records or overwriting."""
    output_dir = tmp_path / "resumable_output"
    checkpoint_dir = tmp_path / "resumable_checkpoints"

    # Step 1: Run with max_games = 2 and chunk_size = 2 -> produces chunk_001
    summary1 = process_pgn_file(
        pgn_path=temp_pgn_file,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        max_games=2,
        chunk_size=2,
        resume=False,
    )
    assert summary1["total_games_processed"] == 2
    chunks_step1 = list(output_dir.glob("features_chunk_*.parquet"))
    assert len(chunks_step1) == 1
    assert chunks_step1[0].name == "features_chunk_001.parquet"
    df_chunk1 = pd.read_parquet(chunks_step1[0])
    chunk1_rows = len(df_chunk1)
    chunk1_game_ids = set(df_chunk1["game_id"].unique())

    # Step 2: Resume with max_games = 10 -> should pick up from next offset, write chunk_002 & chunk_003
    summary2 = process_pgn_file(
        pgn_path=temp_pgn_file,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        max_games=10,
        chunk_size=2,
        resume=True,
    )
    assert summary2["total_games_processed"] > 2

    chunks_step2 = sorted(output_dir.glob("features_chunk_*.parquet"))
    assert len(chunks_step2) >= 2

    # Verify chunk_001 was NOT modified or overwritten
    df_chunk1_after = pd.read_parquet(output_dir / "features_chunk_001.parquet")
    assert len(df_chunk1_after) == chunk1_rows
    assert set(df_chunk1_after["game_id"].unique()) == chunk1_game_ids

    # Verify chunks 2 and 3 contain disjoint game IDs from chunk 1
    for c in chunks_step2[1:]:
        df_next = pd.read_parquet(c)
        overlap = set(df_next["game_id"].unique()).intersection(chunk1_game_ids)
        assert len(overlap) == 0, f"Detected game_id overlap in resumed chunk {c.name}: {overlap}"


def test_duplicate_game_detection(temp_pgn_file: Path, tmp_path: Path):
    """Verify that duplicate games with identical game_ids are skipped."""
    output_dir = tmp_path / "dedup_output"
    checkpoint_dir = tmp_path / "dedup_checkpoints"

    summary = process_pgn_file(
        pgn_path=temp_pgn_file,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        max_games=10,
        chunk_size=10,
        resume=False,
    )

    # In SAMPLE_SYNTHETIC_PGN, game 6 has identical Site to game 1:
    # It must be counted in total_games_skipped
    assert summary["total_games_skipped"] >= 1


def test_malformed_and_incomplete_handling(temp_pgn_file: Path, tmp_path: Path):
    """Verify that malformed and incomplete PGNs do not crash the pipeline."""
    output_dir = tmp_path / "robustness_output"
    checkpoint_dir = tmp_path / "robustness_checkpoints"

    summary = process_pgn_file(
        pgn_path=temp_pgn_file,
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        max_games=10,
        chunk_size=10,
        resume=False,
    )

    # Game 3 (syntax error) should be recorded in total_games_rejected
    assert summary["total_games_rejected"] >= 1
    # Valid games must still be processed into the output
    assert summary["total_games_processed"] >= 3
