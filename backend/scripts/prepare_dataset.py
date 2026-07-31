"""
Dataset Exporter & Feature Preparation Pipeline for ChessTrace.

Reads raw PGN files (such as Lichess Open Database dumps in data/raw/),
runs position and time feature extractors on every ply, and streams out
structured tabular datasets (Parquet format) into data/processed/.

Usage:
    python scripts/prepare_dataset.py --max-games 50000
"""

from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path
from typing import Any, TextIO

import chess
import chess.pgn
import pandas as pd

from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.models.move import Move, MoveColor
from app.parsers.move_parser import _extract_clock
from app.utils.chess_utils import parse_int

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("prepare_dataset")

BASE_PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PGN_PATH = BASE_PROJECT_DIR / "data/raw/lichess_db_standard_rated_2017-11.pgn"
OUTPUT_DIR = BASE_PROJECT_DIR / "data/processed"
CHUNK_SIZE = 10000  # Number of games per Parquet chunk file


def get_elo_bucket(elo: int | None) -> str:
    """Categorize player Elo into ELO brackets."""
    if elo is None:
        return "1400-1600"
    if elo < 1000:
        return "<1000"
    if elo < 1200:
        return "1000-1200"
    if elo < 1400:
        return "1200-1400"
    if elo < 1600:
        return "1400-1600"
    if elo < 1800:
        return "1600-1800"
    if elo < 2000:
        return "1800-2000"
    return "2000+"


def get_result_score(result_str: str, color: chess.Color) -> float:
    """Return numeric result score relative to active player (1.0 = Win, 0.5 = Draw, 0.0 = Loss)."""
    if result_str == "1-0":
        return 1.0 if color == chess.WHITE else 0.0
    if result_str == "0-1":
        return 0.0 if color == chess.WHITE else 1.0
    return 0.5


def parse_raw_game(file_stream: TextIO, buffered_line_container: list[str]) -> str:
    """Stream single raw PGN game text with lookahead buffering."""
    lines: list[str] = []
    if buffered_line_container:
        lines.append(buffered_line_container.pop())

    while True:
        line = file_stream.readline()
        if not line:
            break
        if line.startswith("[Event ") and lines:
            buffered_line_container.append(line)
            break
        lines.append(line)

    return "".join(lines).strip()


def extract_game_rows(game: chess.pgn.Game) -> list[dict[str, Any]]:
    """Extract position + time tabular feature dicts for all plies in a game."""
    rows: list[dict[str, Any]] = []

    white_elo = parse_int(game.headers.get("WhiteElo"))
    black_elo = parse_int(game.headers.get("BlackElo"))
    result_str = game.headers.get("Result", "*")
    time_control_str = game.headers.get("TimeControl", "")

    # Parse initial clock seconds if available
    initial_clock = None
    if "+" in time_control_str or "|" in time_control_str:
        base_part = time_control_str.split("+")[0].split("|")[0]
        initial_clock = parse_int(base_part)
    elif time_control_str.isdigit():
        initial_clock = int(time_control_str)

    board = game.board()
    previous_clock: int | None = None

    previous_moves_white: list[Move] = []
    previous_moves_black: list[Move] = []

    for ply, node in enumerate(game.mainline(), start=1):
        chess_move = node.move
        if chess_move is None:
            continue

        active_color = board.turn
        color_enum = MoveColor.WHITE if active_color == chess.WHITE else MoveColor.BLACK
        active_elo = white_elo if active_color == chess.WHITE else black_elo
        elo_bucket = get_elo_bucket(active_elo)
        result_score = get_result_score(result_str, active_color)

        move_number = (ply + 1) // 2
        san = board.san(chess_move)
        uci = chess_move.uci()

        board.push(chess_move)
        post_fen = board.fen()

        clock_after = _extract_clock(node)
        time_spent = None
        if previous_clock is not None and clock_after is not None:
            time_spent = previous_clock - clock_after

        # Construct temporary Move ORM entity for feature extractor
        move_obj = Move(
            move_number=move_number,
            ply=ply,
            color=color_enum,
            san=san,
            uci=uci,
            fen=post_fen,
            clock_before=previous_clock,
            clock_after=clock_after,
            time_spent=time_spent,
        )

        # Extract features
        pos_feats = extract_position_features(board)
        prev_same_color = (
            previous_moves_white if active_color == chess.WHITE else previous_moves_black
        )
        time_feats = extract_time_features(
            move_obj,
            previous_moves_same_color=prev_same_color,
            initial_clock_seconds=initial_clock,
        )

        rows.append(
            {
                # Context & Identifiers
                "ply": ply,
                "move_number": move_number,
                "color": "white" if active_color == chess.WHITE else "black",
                "active_elo": active_elo,
                "elo_bucket": elo_bucket,
                "san": san,
                "uci": uci,
                "game_result_score": result_score,
                # Position features
                "material_balance": pos_feats.material_balance,
                "white_material": pos_feats.white_material,
                "black_material": pos_feats.black_material,
                "game_phase": pos_feats.game_phase,
                "white_mobility": pos_feats.white_mobility,
                "black_mobility": pos_feats.black_mobility,
                "white_center_control": pos_feats.white_center_control,
                "black_center_control": pos_feats.black_center_control,
                "white_pawn_shield": pos_feats.white_pawn_shield,
                "black_pawn_shield": pos_feats.black_pawn_shield,
                "white_passed_pawns": pos_feats.white_passed_pawns,
                "black_passed_pawns": pos_feats.black_passed_pawns,
                "white_isolated_pawns": pos_feats.white_isolated_pawns,
                "black_isolated_pawns": pos_feats.black_isolated_pawns,
                "white_doubled_pawns": pos_feats.white_doubled_pawns,
                "black_doubled_pawns": pos_feats.black_doubled_pawns,
                # Time features
                "think_time": time_feats.think_time,
                "time_remaining": time_feats.time_remaining,
                "is_time_pressure_120s": time_feats.is_time_pressure_120s,
                "is_time_pressure_60s": time_feats.is_time_pressure_60s,
                "is_time_pressure_30s": time_feats.is_time_pressure_30s,
                "time_usage_ratio": time_feats.time_usage_ratio,
                "running_avg_think_time": time_feats.running_avg_think_time,
                "think_time_deviation": time_feats.think_time_deviation,
                "time_control": time_feats.time_control,
            }
        )

        if active_color == chess.WHITE:
            previous_moves_white.append(move_obj)
        else:
            previous_moves_black.append(move_obj)

        previous_clock = clock_after

    return rows


def process_pgn_file(pgn_path: Path, max_games: int | None = None) -> None:
    """Stream PGN file and export extracted feature tables to Parquet."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not pgn_path.exists():
        logger.error("PGN file not found: %s", pgn_path.absolute())
        return

    logger.info("Processing raw dataset: %s", pgn_path.name)
    if max_games:
        logger.info("Target max games: %d", max_games)

    games_count = 0
    total_plies = 0
    chunk_index = 1
    current_chunk_rows: list[dict[str, Any]] = []

    buffered_lines: list[str] = []

    with pgn_path.open("r", encoding="utf-8", errors="replace") as file_stream:
        while True:
            raw_pgn = parse_raw_game(file_stream, buffered_lines)
            if not raw_pgn.strip():
                break

            game = chess.pgn.read_game(io.StringIO(raw_pgn))
            if game is None:
                continue

            game_rows = extract_game_rows(game)
            if not game_rows:
                continue

            current_chunk_rows.extend(game_rows)
            games_count += 1
            total_plies += len(game_rows)

            if games_count % 1000 == 0:
                logger.info("Processed %d games (%d plies)...", games_count, total_plies)

            if games_count % CHUNK_SIZE == 0:
                chunk_file = OUTPUT_DIR / f"features_chunk_{chunk_index:03d}.parquet"
                df = pd.DataFrame(current_chunk_rows)
                df.to_parquet(chunk_file, index=False)
                logger.info("Saved chunk: %s (%d rows)", chunk_file.name, len(df))
                chunk_index += 1
                current_chunk_rows = []

            if max_games and games_count >= max_games:
                break

    # Save remaining rows
    if current_chunk_rows:
        chunk_file = OUTPUT_DIR / f"features_chunk_{chunk_index:03d}.parquet"
        df = pd.DataFrame(current_chunk_rows)
        df.to_parquet(chunk_file, index=False)
        logger.info("Saved final chunk: %s (%d rows)", chunk_file.name, len(df))

    logger.info(
        "Dataset export complete! Games=%d | Total Plies=%d | Output=%s",
        games_count,
        total_plies,
        OUTPUT_DIR.absolute(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChessTrace Dataset Exporter")
    parser.add_argument(
        "--pgn",
        type=Path,
        default=DEFAULT_PGN_PATH,
        help="Path to raw PGN file",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=10000,
        help="Maximum games to process (default: 10000, set to 0 for unlimited)",
    )
    parser.add_argument(
        "--stratified-target",
        type=int,
        default=0,
        help="Target games per ELO bracket for stratified sampling (e.g. 2000)",
    )
    args = parser.parse_args()

    max_g = None if args.max_games <= 0 else args.max_games
    process_pgn_file(args.pgn, max_games=max_g)
