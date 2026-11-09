from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

# Ensure backend root is on sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
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


def test_parser_pipeline_import() -> None:
    """Hermetic unit test verifying PGN parsing and database import."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    start = perf_counter()

    try:
        heading("ChessTrace PGN Import Test")

        backend_dir = Path(__file__).resolve().parent.parent
        pgn_file = backend_dir / "sample_multi.pgn"
        if not pgn_file.exists():
            pgn_file = backend_dir / "sample_clock.pgn"

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
            row("Speed", f"{summary.processed / elapsed:.2f} games/sec")

        print()

        assert summary.processed > 0, "Expected at least 1 game processed"
        assert summary.imported > 0, "Expected at least 1 game imported"
        assert summary.failed == 0, f"Expected 0 failed games, got {summary.failed}"

    finally:
        session.close()


# Backward-compatible alias
main = test_parser_pipeline_import

if __name__ == "__main__":
    test_parser_pipeline_import()
