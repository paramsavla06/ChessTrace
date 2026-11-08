"""
Dataset Exporter & Feature Preparation Pipeline for ChessTrace (v2).

Reads raw PGN files (such as Lichess Open Database dumps in data/raw/),
runs position and time feature extractors on every ply, assigns stable game IDs,
and streams out structured tabular datasets (Parquet format) into data/processed/v2/
with atomic chunk writes, byte-offset checkpointing, and robust resumability.

Usage:
    # Process initial representative dataset (200,000 games)
    python scripts/prepare_dataset.py --max-games 200000 --output-dir data/processed/v2

    # Process small test sample (5,000 games)
    python scripts/prepare_dataset.py --max-games 5000 --chunk-size 1000

    # Resume interrupted run
    python scripts/prepare_dataset.py --resume
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

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
DEFAULT_OUTPUT_DIR = BASE_PROJECT_DIR / "data/processed/v2"
DEFAULT_CHECKPOINT_DIR = BASE_PROJECT_DIR / "data/checkpoints"
DEFAULT_CHUNK_SIZE = 10000

# Canonical 34-column dataset schema
FEATURE_SCHEMA_COLUMNS = [
    # Identifiers & Context (9 columns)
    "game_id",
    "ply",
    "move_number",
    "color",
    "active_elo",
    "elo_bucket",
    "san",
    "uci",
    "game_result_score",
    # Position features (15 columns)
    "material_balance",
    "white_material",
    "black_material",
    "game_phase",
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
    # Time & Clock features (10 columns)
    "think_time",
    "time_remaining",
    "is_time_pressure_120s",
    "is_time_pressure_60s",
    "is_time_pressure_30s",
    "time_usage_ratio",
    "running_avg_think_time",
    "think_time_deviation",
    "time_control",
]


def get_elo_bucket(elo: int | None) -> str:
    """Categorize player Elo into authoritative ELO brackets."""
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


def extract_game_id(game: chess.pgn.Game) -> str:
    """
    Extract stable, unique game identifier.
    Prefers Lichess game ID from the Site header (e.g. 'https://lichess.org/l4jZLpdZ' -> 'l4jZLpdZ').
    Falls back to deterministic SHA-256 hash of core game metadata and opening plies.
    """
    site = game.headers.get("Site", "").strip()
    if site:
        match = re.search(r"lichess\.org/(?:[a-zA-Z0-9]+/)?([a-zA-Z0-9]{8,12})", site)
        if match:
            return match.group(1)
        token = site.rstrip("/").split("/")[-1]
        if token and re.match(r"^[a-zA-Z0-9]{8,12}$", token):
            return token

    # Deterministic fallback: hash date, players, result, and first 4 plies
    date = game.headers.get("UTCDate", "")
    time_str = game.headers.get("UTCTime", "")
    white = game.headers.get("White", "")
    black = game.headers.get("Black", "")
    eco = game.headers.get("ECO", "")
    result = game.headers.get("Result", "")

    first_moves: list[str] = []
    for node in game.mainline():
        if node.move:
            first_moves.append(node.move.uci())
        if len(first_moves) >= 4:
            break

    sig = f"{date}_{time_str}_{white}_{black}_{eco}_{result}_{'-'.join(first_moves)}"
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12]


class PGNStreamReader:
    """
    Streams raw games from PGN file in binary mode with exact byte-offset tracking.
    Enables O(1) byte-accurate resumption from checkpoints without re-scanning.
    """

    def __init__(self, pgn_path: Path, start_byte_offset: int = 0) -> None:
        self.pgn_path = pgn_path
        self.file = pgn_path.open("rb")
        if start_byte_offset > 0:
            self.file.seek(start_byte_offset)
        self.buffered_line: bytes | None = None
        self.buffered_offset: int = start_byte_offset

    def read_game(self) -> tuple[str, int, int] | None:
        """
        Reads next game.
        Returns (raw_pgn_text, game_start_offset, next_game_offset) or None at EOF.
        """
        lines: list[bytes] = []
        game_start_offset: int = self.buffered_offset

        if self.buffered_line is not None:
            lines.append(self.buffered_line)
            self.buffered_line = None

        while True:
            offset_before_read = self.file.tell()
            line = self.file.readline()
            if not line:
                break
            if line.startswith(b"[Event ") and lines:
                self.buffered_line = line
                self.buffered_offset = offset_before_read
                break
            lines.append(line)

        if not lines:
            return None

        raw_bytes = b"".join(lines).strip()
        if not raw_bytes:
            return None

        text = raw_bytes.decode("utf-8", errors="replace")
        next_offset = (
            self.buffered_offset if self.buffered_line is not None else self.file.tell()
        )
        return text, game_start_offset, next_offset

    def close(self) -> None:
        self.file.close()


@dataclass
class PreprocessingCheckpoint:
    version: int
    pgn_path: str
    pgn_size_bytes: int
    pgn_mtime: str
    next_game_byte_offset: int
    last_completed_chunk: int
    total_games_discovered: int
    total_games_processed: int
    total_games_skipped: int
    total_games_rejected: int
    total_plies_extracted: int
    created_at: str
    updated_at: str

    def save(self, checkpoint_path: Path) -> None:
        """Save checkpoint JSON atomically via temp file."""
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = checkpoint_path.with_suffix(".json.tmp")
        self.updated_at = datetime.now().isoformat()
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        os.replace(temp_path, checkpoint_path)

    @classmethod
    def load(cls, checkpoint_path: Path, pgn_path: Path) -> PreprocessingCheckpoint | None:
        """Load and validate checkpoint against raw PGN fingerprint."""
        if not checkpoint_path.exists():
            return None
        try:
            with checkpoint_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            cp = cls(**data)
            # Verify PGN identity
            curr_size = pgn_path.stat().st_size
            if cp.pgn_size_bytes != curr_size:
                logger.warning(
                    "Raw PGN size changed (expected %d, found %d). Checkpoint invalid.",
                    cp.pgn_size_bytes,
                    curr_size,
                )
                return None
            return cp
        except Exception as exc:
            logger.warning("Could not read checkpoint from %s: %s", checkpoint_path, exc)
            return None


def write_parquet_chunk(
    output_dir: Path,
    chunk_index: int,
    rows: list[dict[str, Any]],
) -> Path:
    """
    Safely write a batch of feature rows to Parquet using atomic temp file replacement.
    Validates row counts and schema before making chunk visible.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_name = f"features_chunk_{chunk_index:03d}.parquet"
    target_path = output_dir / chunk_name
    temp_path = output_dir / f"{chunk_name}.tmp"

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Attempted to write empty chunk {chunk_name}")

    # Validate schema
    missing = [col for col in FEATURE_SCHEMA_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Chunk {chunk_name} missing required columns: {missing}")

    # Ensure consistent column ordering
    df = df[FEATURE_SCHEMA_COLUMNS]

    # Write to temp file
    df.to_parquet(temp_path, index=False, engine="pyarrow")

    # Validate readability
    read_back = pd.read_parquet(temp_path)
    if len(read_back) != len(df):
        raise IOError(f"Parquet validation mismatch in {temp_path}: {len(read_back)} vs {len(df)}")

    # Atomic rename
    os.replace(temp_path, target_path)
    logger.info("Saved and validated chunk: %s (%d rows)", target_path.name, len(df))
    return target_path


def extract_game_rows(game: chess.pgn.Game, game_id: str) -> list[dict[str, Any]]:
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
    previous_white_clock: int | None = None
    previous_black_clock: int | None = None

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
        prev_clock = (
            previous_white_clock if active_color == chess.WHITE else previous_black_clock
        )
        time_spent = None

        if prev_clock is not None and clock_after is not None:
            time_spent = max(0, prev_clock - clock_after)

        if active_color == chess.WHITE:
            previous_white_clock = clock_after
        else:
            previous_black_clock = clock_after

        # Construct temporary Move ORM entity for feature extractor
        move_obj = Move(
            move_number=move_number,
            ply=ply,
            color=color_enum,
            san=san,
            uci=uci,
            fen=post_fen,
            clock_before=prev_clock,
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
                # Identifiers & Context
                "game_id": game_id,
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


def process_pgn_file(
    pgn_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    max_games: int | None = 200000,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    stratified_target: int = 0,
    resume: bool = True,
    force_restart: bool = False,
) -> dict[str, Any]:
    """
    Stream raw PGN file, extract feature tables, and save chunked Parquet files.
    Fully resumable with byte-accurate checkpoints.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if not pgn_path.exists():
        logger.error("PGN file not found: %s", pgn_path.absolute())
        return {"status": "error", "message": "PGN file not found"}

    checkpoint_file = checkpoint_dir / f"checkpoint_{output_dir.name}.json"
    start_byte_offset = 0
    chunk_index = 1
    total_games_discovered = 0
    games_processed = 0
    games_skipped = 0
    games_rejected = 0
    total_plies = 0

    seen_game_ids: set[str] = set()

    # Determine highest existing chunk in output_dir to prevent overwriting
    existing_chunks = sorted(output_dir.glob("features_chunk_*.parquet"))
    if existing_chunks:
        max_chunk = max(int(f.stem.split("_")[-1]) for f in existing_chunks)
        chunk_index = max_chunk + 1
        logger.info("Found %d existing chunks in %s. Next chunk index: %d", len(existing_chunks), output_dir, chunk_index)

    # Resume from checkpoint if enabled
    if resume and not force_restart and checkpoint_file.exists():
        cp = PreprocessingCheckpoint.load(checkpoint_file, pgn_path)
        if cp:
            start_byte_offset = cp.next_game_byte_offset
            chunk_index = cp.last_completed_chunk + 1
            total_games_discovered = cp.total_games_discovered
            games_processed = cp.total_games_processed
            games_skipped = cp.total_games_skipped
            games_rejected = cp.total_games_rejected
            total_plies = cp.total_plies_extracted
            logger.info(
                "Resuming from checkpoint: byte_offset=%d | last_chunk=%d | processed_games=%d | plies=%d",
                start_byte_offset,
                cp.last_completed_chunk,
                games_processed,
                total_plies,
            )

    # Pre-populate seen_game_ids from existing chunks so duplicate detection works across resumes
    if existing_chunks:
        for chunk_path in existing_chunks:
            try:
                chunk_df = pd.read_parquet(chunk_path, columns=["game_id"])
                seen_game_ids.update(chunk_df["game_id"].dropna().unique())
            except Exception as e:
                logger.debug("Could not read game IDs from %s: %s", chunk_path.name, e)
        if seen_game_ids:
            logger.info("Loaded %d previously processed game IDs into deduplication index.", len(seen_game_ids))

    reader = PGNStreamReader(pgn_path, start_byte_offset=start_byte_offset)
    current_chunk_rows: list[dict[str, Any]] = []
    chunk_game_count = 0

    elo_counts = {
        "<1000": 0,
        "1000-1200": 0,
        "1200-1400": 0,
        "1400-1600": 0,
        "1600-1800": 0,
        "1800-2000": 0,
        "2000+": 0,
    }

    t_start = time.time()
    t_last_log = t_start
    games_since_log = 0
    last_next_offset = start_byte_offset

    try:
        while True:
            item = reader.read_game()
            if item is None:
                break

            raw_pgn, game_start_offset, next_game_offset = item
            last_next_offset = next_game_offset
            total_games_discovered += 1

            # Parse game
            try:
                game = chess.pgn.read_game(io.StringIO(raw_pgn))
            except Exception as parse_err:
                games_rejected += 1
                logger.debug("Malformed PGN at offset %d: %s", game_start_offset, parse_err)
                continue

            if game is None or getattr(game, "errors", None):
                games_rejected += 1
                if getattr(game, "errors", None):
                    logger.debug("Game %s has PGN parse errors: %s", getattr(game, "headers", {}).get("Site", "unknown"), game.errors)
                continue

            game_id = extract_game_id(game)

            # Deduplication
            if game_id in seen_game_ids:
                games_skipped += 1
                continue
            seen_game_ids.add(game_id)

            # Stratification check if enabled
            if stratified_target > 0:
                w_elo = parse_int(game.headers.get("WhiteElo"))
                b_elo = parse_int(game.headers.get("BlackElo"))
                w_bucket = get_elo_bucket(w_elo)
                b_bucket = get_elo_bucket(b_elo)
                if (
                    elo_counts[w_bucket] >= stratified_target
                    and elo_counts[b_bucket] >= stratified_target
                ):
                    games_skipped += 1
                    continue
                elo_counts[w_bucket] += 1
                elo_counts[b_bucket] += 1

            # Feature extraction
            try:
                rows = extract_game_rows(game, game_id=game_id)
            except Exception as extract_err:
                games_rejected += 1
                logger.debug("Extraction failed for game %s: %s", game_id, extract_err)
                continue

            if not rows:
                games_skipped += 1
                continue

            current_chunk_rows.extend(rows)
            games_processed += 1
            chunk_game_count += 1
            total_plies += len(rows)
            games_since_log += 1

            # Periodic progress logging (every 1000 games)
            now = time.time()
            if games_since_log >= 1000 or (now - t_last_log) >= 30.0:
                elapsed = now - t_start
                g_rate = games_processed / max(1.0, elapsed)
                p_rate = total_plies / max(1.0, elapsed)
                eta_str = "--"
                if max_games and max_games > games_processed and g_rate > 0:
                    eta_sec = (max_games - games_processed) / g_rate
                    eta_str = f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s"

                logger.info(
                    "Games: %d (Target: %s) | Plies: %d | Chunk: %03d | Speed: %.1f g/s (%.1f p/s) | Elapsed: %ds | ETA: %s",
                    games_processed,
                    str(max_games) if max_games else "unlimited",
                    total_plies,
                    chunk_index,
                    g_rate,
                    p_rate,
                    int(elapsed),
                    eta_str,
                )
                t_last_log = now
                games_since_log = 0

            # Write full chunk
            if chunk_game_count >= chunk_size:
                write_parquet_chunk(output_dir, chunk_index, current_chunk_rows)
                # Checkpoint
                cp = PreprocessingCheckpoint(
                    version=2,
                    pgn_path=str(pgn_path.resolve()),
                    pgn_size_bytes=pgn_path.stat().st_size,
                    pgn_mtime=datetime.fromtimestamp(pgn_path.stat().st_mtime).isoformat(),
                    next_game_byte_offset=next_game_offset,
                    last_completed_chunk=chunk_index,
                    total_games_discovered=total_games_discovered,
                    total_games_processed=games_processed,
                    total_games_skipped=games_skipped,
                    total_games_rejected=games_rejected,
                    total_plies_extracted=total_plies,
                    created_at=datetime.fromtimestamp(t_start).isoformat(),
                    updated_at=datetime.now().isoformat(),
                )
                cp.save(checkpoint_file)

                chunk_index += 1
                chunk_game_count = 0
                current_chunk_rows = []

            # Target game limit reached
            if max_games and games_processed >= max_games:
                logger.info("Reached target limit of %d games.", max_games)
                break

            # Stratified target reached
            if stratified_target > 0 and all(c >= stratified_target for c in elo_counts.values()):
                logger.info("All ELO brackets reached target count of %d games!", stratified_target)
                break

    finally:
        reader.close()

    # Save remaining partial chunk
    if current_chunk_rows:
        write_parquet_chunk(output_dir, chunk_index, current_chunk_rows)
        cp = PreprocessingCheckpoint(
            version=2,
            pgn_path=str(pgn_path.resolve()),
            pgn_size_bytes=pgn_path.stat().st_size,
            pgn_mtime=datetime.fromtimestamp(pgn_path.stat().st_mtime).isoformat(),
            next_game_byte_offset=last_next_offset,
            last_completed_chunk=chunk_index,
            total_games_discovered=total_games_discovered,
            total_games_processed=games_processed,
            total_games_skipped=games_skipped,
            total_games_rejected=games_rejected,
            total_plies_extracted=total_plies,
            created_at=datetime.fromtimestamp(t_start).isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        cp.save(checkpoint_file)

    elapsed_total = time.time() - t_start
    summary = {
        "status": "success",
        "pgn_file": pgn_path.name,
        "total_games_discovered": total_games_discovered,
        "total_games_processed": games_processed,
        "total_games_skipped": games_skipped,
        "total_games_rejected": games_rejected,
        "total_plies_extracted": total_plies,
        "output_chunks": chunk_index,
        "output_dir": str(output_dir),
        "elapsed_seconds": round(elapsed_total, 2),
    }
    logger.info("Dataset export finished: %s", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChessTrace Dataset Exporter v2")
    parser.add_argument("--pgn", type=Path, default=DEFAULT_PGN_PATH, help="Path to raw PGN file")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for Parquet chunks")
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR, help="Checkpoint directory")
    parser.add_argument("--max-games", type=int, default=200000, help="Max games to process (default: 200000, set 0 for unlimited)")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Games per Parquet chunk (default: 10000)")
    parser.add_argument("--stratified-target", type=int, default=0, help="Target games per ELO bracket")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from last checkpoint if exists")
    parser.add_argument("--force-restart", action="store_true", help="Ignore checkpoint and restart from game 1")
    args = parser.parse_args()

    max_g = None if args.max_games <= 0 else args.max_games
    process_pgn_file(
        pgn_path=args.pgn,
        output_dir=args.output_dir,
        checkpoint_dir=args.checkpoint_dir,
        max_games=max_g,
        chunk_size=args.chunk_size,
        stratified_target=args.stratified_target,
        resume=args.resume and not args.force_restart,
        force_restart=args.force_restart,
    )
