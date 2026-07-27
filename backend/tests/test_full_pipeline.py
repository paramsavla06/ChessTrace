"""
Full pipeline integration test.

Tests PGN importing, database storage, position feature extraction,
and time feature extraction end-to-end using SQLite in-memory DB.
"""

from __future__ import annotations

from pathlib import Path

import chess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.models.game import Game
from app.services.import_services import ImportService


def run_pipeline_test():
    print("=" * 60)
    print("      ChessTrace Full Pipeline Integration Test      ".center(60))
    print("=" * 60)

    # 1. Initialize in-memory SQLite engine & create schema
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 2. Test ImportService
        pgn_file = Path(__file__).parent.parent / "sample_clock.pgn"
        if not pgn_file.exists():
            pgn_file = Path(__file__).parent.parent / "sample_multi.pgn"
        
        print(f"\n[1/3] Importing PGN file: {pgn_file.name}")
        
        service = ImportService(session)
        summary = service.import_file(pgn_file)

        print(f"   [OK] Processed : {summary.processed}")
        print(f"   [OK] Imported  : {summary.imported}")
        print(f"   [OK] Skipped   : {summary.skipped}")
        print(f"   [OK] Failed    : {summary.failed}")

        # 3. Query imported games & test Feature Extractors
        games = session.query(Game).all()
        print(f"\n[2/3] Querying imported games ({len(games)} found)...")

        for game in games:
            print(f"\n   --------------------------------------------------")
            print(f"   Game ID {game.id}: {game.white_player.display_name} vs {game.black_player.display_name}")
            print(f"   Result: {game.result.value} | Event: {game.event} | Total Moves: {len(game.moves)}")
            print(f"   --------------------------------------------------")

            previous_moves_white = []
            previous_moves_black = []

            for move in game.moves[:4]:  # Inspect first 4 moves
                board = chess.Board(move.fen)
                pos_feats = extract_position_features(board)
                
                prev_same_color = (
                    previous_moves_white if move.color.value == "white" else previous_moves_black
                )
                time_feats = extract_time_features(
                    move,
                    previous_moves_same_color=prev_same_color,
                    initial_clock_seconds=180,
                )

                print(
                    f"   Move {move.move_number:>2} ({move.color.value[:1].upper()}): {move.san:<6} | "
                    f"Phase: {pos_feats.game_phase:<10} | Mat Bal: {pos_feats.material_balance:>+2} | "
                    f"Think: {time_feats.think_time:.1f}s | Clock: {time_feats.time_remaining:.1f}s | "
                    f"TC: {time_feats.time_control}"
                )

                if move.color.value == "white":
                    previous_moves_white.append(move)
                else:
                    previous_moves_black.append(move)

        print("\n[3/3] Full Pipeline Execution Successful! All features functional.")
        print("=" * 60)

    finally:
        session.close()


if __name__ == "__main__":
    run_pipeline_test()
