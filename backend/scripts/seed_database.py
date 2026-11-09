"""
Database Seeding and Smoke Verification Script.

Truncates existing development tables and seeds reference test games
(Magnus Carlsen vs Hikaru Nakamura) with full move, clock, and evaluation records.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure backend root is on sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import DATABASE_URL
from app.models import (
    Player,
    Game,
    Move,
    Evaluation,
    GameResult,
    Variant,
    MoveColor,
)


engine = create_engine(DATABASE_URL, echo=False)


def insert_test_data() -> None:
    """Truncate tables and seed reference players, game, moves, and evaluations."""
    with Session(engine) as session:
        session.execute(text("""
            TRUNCATE TABLE
                evaluations,
                moves,
                games,
                players
            RESTART IDENTITY CASCADE;
        """))
        session.commit()

        # Players
        white = Player(
            display_name="Magnus Carlsen",
            fide_id=1503014,
            title="GM",
            federation="NOR",
        )

        black = Player(
            display_name="Hikaru Nakamura",
            fide_id=2016192,
            title="GM",
            federation="USA",
        )

        session.add_all([white, black])
        session.flush()

        # Game
        game = Game(
            site="Lichess",
            event="Titled Tuesday Blitz",
            game_round="1",
            game_date=date.today(),
            white_player_id=white.id,
            black_player_id=black.id,
            result=GameResult.WHITE_WIN,
            variant=Variant.STANDARD,
            eco="C65",
            opening="Ruy Lopez",
            variation="Berlin Defense",
            time_control="180+0",
            rated=True,
        )

        session.add(game)
        session.flush()

        # Moves
        moves_data = [
            ("e4", "e2e4", MoveColor.WHITE, 1, 1, 180000, 178000, 2000, 25),
            ("e5", "e7e5", MoveColor.BLACK, 1, 2, 180000, 179000, 1000, -20),
            ("Nf3", "g1f3", MoveColor.WHITE, 2, 3, 178000, 176000, 2000, 30),
            ("Nc6", "b8c6", MoveColor.BLACK, 2, 4, 179000, 177000, 2000, -25),
            ("Bb5", "f1b5", MoveColor.WHITE, 3, 5, 176000, 173000, 3000, 35),
            ("a6", "a7a6", MoveColor.BLACK, 3, 6, 177000, 174000, 3000, -30),
            ("Ba4", "b5a4", MoveColor.WHITE, 4, 7, 173000, 171000, 2000, 30),
            ("Nf6", "g8f6", MoveColor.BLACK, 4, 8, 174000, 170000, 4000, -28),
            ("O-O", "e1g1", MoveColor.WHITE, 5, 9, 171000, 168000, 3000, 32),
            ("Be7", "f8e7", MoveColor.BLACK, 5, 10, 170000, 166000, 4000, -30),
        ]

        for san, uci, color, num, ply, cb, ca, ts, eval_score in moves_data:
            move = Move(
                game_id=game.id,
                move_number=num,
                ply=ply,
                color=color,
                san=san,
                uci=uci,
                clock_before=cb,
                clock_after=ca,
                time_spent=ts,
            )
            session.add(move)
            session.flush()

            evaluation = Evaluation(
                move_id=move.id,
                depth=18,
                score_cp=eval_score,
                best_move=uci,
                engine_version="Stockfish 16",
            )
            session.add(evaluation)

        session.commit()
        print("\n[OK] Test data inserted successfully!\n")


def verify_database() -> None:
    """Verify seeded database records and print smoke summary."""
    with Session(engine) as session:
        game = session.query(Game).first()

        if game is None:
            print("[WARN] No game found in database.")
            return

        print("=" * 60)
        print("DATABASE SMOKE TEST SUMMARY".center(60))
        print("=" * 60)

        print(f"Game ID           : {game.id}")
        print(f"Site              : {game.site}")
        print(f"Event             : {game.event}")
        print(f"Result            : {game.result.value}")
        print(f"Time Control      : {game.time_control}")
        print(f"White             : {game.white_player.display_name}")
        print(f"Black             : {game.black_player.display_name}")
        print(f"Total Moves       : {len(game.moves)}")

        if game.moves:
            first_move = game.moves[0]
            print(f"\nFirst Move        : {first_move.san} ({first_move.color.value})")
            print(f"Clock Time Spent  : {first_move.time_spent} ms")
            if first_move.evaluations:
                ev = first_move.evaluations[0]
                print(f"Engine Eval       : {ev.score_cp} cp (depth {ev.depth})")

        print("=" * 60)
        print("SMOKE TEST COMPLETED SUCCESSFULLY".center(60))
        print("=" * 60)


if __name__ == "__main__":
    insert_test_data()
    verify_database()

