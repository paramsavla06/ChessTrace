from datetime import date

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


# Create SQLAlchemy Engine
engine = create_engine(DATABASE_URL, echo=False)


def insert_test_data():
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
        # ----------------------------------------
        # Players
        # ----------------------------------------
        white = Player(
            name="Magnus Carlsen",
            fide_id=1503014,
            title="GM",
            federation="NOR",
        )

        black = Player(
            name="Hikaru Nakamura",
            fide_id=2016192,
            title="GM",
            federation="USA",
        )

        session.add_all([white, black])
        session.flush()

        # ----------------------------------------
        # Game
        # ----------------------------------------
        game = Game(
            site="Lichess",
            event="Smoke Test",
            game_round="1",
            game_date=date.today(),
            white_player=white,
            black_player=black,
            white_elo=2835,
            black_elo=2780,
            result=GameResult.WHITE_WIN,
            eco="C20",
            opening="King's Pawn Game",
            variation=None,
            time_control="600+5",
            termination="Normal",
            rated=True,
            variant=Variant.STANDARD,
            initial_fen=None,
            pgn_hash="SMOKE_TEST_HASH_001",
        )

        session.add(game)
        session.flush()

        # ----------------------------------------
        # Move
        # ----------------------------------------
        move = Move(
            game=game,
            move_number=1,
            ply=1,
            color=MoveColor.WHITE,
            san="e4",
            uci="e2e4",
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            is_capture=False,
            is_check=False,
            is_checkmate=False,
            promotion=None,
            clock_before=600,
            clock_after=598,
            time_spent=2,
        )

        session.add(move)
        session.flush()

        # ----------------------------------------
        # Evaluation
        # ----------------------------------------
        evaluation = Evaluation(
            move=move,
            depth=20,
            score_cp=32,
            mate=None,
            best_move="e7e5",
            pv="e7e5 g1f3",
            nodes=180000,
            nps=1500000,
            analysis_time_ms=120,
            engine_version="Stockfish 17",
        )

        session.add(evaluation)

        session.commit()

        print("\nTest data inserted successfully!\n")


def verify_database():
    with Session(engine) as session:
        game = session.query(Game).first()

        if game is None:
            print("No game found.")
            return

        print("=" * 60)
        print("DATABASE SMOKE TEST")
        print("=" * 60)

        print(f"Game ID           : {game.id}")
        print(f"Site              : {game.site}")
        print(f"Event             : {game.event}")
        print(f"Date              : {game.game_date}")
        print(f"Opening           : {game.opening}")
        print(f"Variation         : {game.variation}")
        print(f"ECO               : {game.eco}")
        print(f"Result            : {game.result.value}")
        print(f"Variant           : {game.variant.value}")
        print(f"Time Control      : {game.time_control}")
        print(f"Rated             : {game.rated}")

        print("\nPlayers")
        print(f"White             : {game.white_player.name}")
        print(f"Black             : {game.black_player.name}")

        print(f"\nTotal Moves       : {len(game.moves)}")

        first_move = game.moves[0]

        print("\nFirst Move")
        print("-" * 60)
        print(f"Move Number       : {first_move.move_number}")
        print(f"Ply               : {first_move.ply}")
        print(f"Color             : {first_move.color.value}")
        print(f"SAN               : {first_move.san}")
        print(f"UCI               : {first_move.uci}")
        print(f"Capture           : {first_move.is_capture}")
        print(f"Check             : {first_move.is_check}")
        print(f"Checkmate         : {first_move.is_checkmate}")
        print(f"Clock Before      : {first_move.clock_before}")
        print(f"Clock After       : {first_move.clock_after}")
        print(f"Time Spent        : {first_move.time_spent}")

        evaluation = first_move.evaluations[0]

        print("\nEvaluation")
        print("-" * 60)
        print(f"Depth             : {evaluation.depth}")
        print(f"Score (cp)        : {evaluation.score_cp}")
        print(f"Mate              : {evaluation.mate}")
        print(f"Best Move         : {evaluation.best_move}")
        print(f"Nodes             : {evaluation.nodes}")
        print(f"NPS               : {evaluation.nps}")
        print(f"Analysis Time(ms) : {evaluation.analysis_time_ms}")
        print(f"Engine            : {evaluation.engine_version}")

        print("\n")
        print("=" * 60)
        print("SMOKE TEST PASSED SUCCESSFULLY")
        print("=" * 60)


if __name__ == "__main__":
    insert_test_data()
    verify_database()
