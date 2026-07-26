from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.database.session import SessionLocal
from app.services.import_services import ImportService


WIDTH = 60


def divider(char: str = "=") -> None:
    print(char * WIDTH)


def heading(title: str) -> None:
    divider()
    print(title.center(WIDTH))
    divider()


def row(key: str, value) -> None:
    print(f"{key:<12}: {value}")


def main() -> None:
    session = SessionLocal()

    start = perf_counter()

    try:
        heading("ChessTrace PGN Import Test")

        pgn_file = Path("sample_multi.pgn")

        row("File", pgn_file.name)
        print()

        service = ImportService(session)

        summary = service.import_file(pgn_file)

        elapsed = perf_counter() - start

        heading("SUMMARY")

        row("Processed", summary.processed)
        row("Imported", summary.imported)
        row("Skipped", summary.skipped)
        row("Failed", summary.failed)
        row("Time", f"{elapsed:.2f} s")

        if elapsed > 0:
            row(
                "Speed",
                f"{summary.processed / elapsed:.2f} games/sec",
            )

        print()

        if summary.failed > 0:
            print("⚠ Import completed with errors.")
        elif summary.imported > 0:
            print("✓ Import completed successfully.")
        elif summary.skipped > 0:
            print("✓ Duplicate game(s) detected. Nothing new imported.")
        else:
            print("✓ No games found in the PGN file.")

    except Exception as e:
        session.rollback()

        print("\nERROR")
        divider("-")
        print(type(e).__name__)
        print(e)
        divider("-")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
