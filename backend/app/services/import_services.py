"""
PGN import service.

Responsible for importing PGN games into the database.

Responsibilities
----------------
- Read PGN files
- Detect duplicate games
- Resolve players
- Persist games
- Persist moves
- Transaction management
- Logging

Non-responsibilities
--------------------
- Parsing PGN headers
- Parsing moves
- Engine analysis
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TextIO

import chess.pgn
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Game
from app.parsers.pgn_parser import parse_pgn
from app.parsers.player_parser import resolve_player
from app.schemas.import_summary import ImportSummary
from app.utils.chess_utils import compute_pgn_hash, parse_int

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


class ImportService:
    """
    Service responsible for importing PGN files.
    """

    def __init__(self, session: Session):
        self.session = session
        self._buffered_line: str | None = None

    def import_file(self, path: str | Path) -> ImportSummary:
        """
        Import every game contained in a PGN file.

        Parameters
        ----------
        path
            Path to the PGN file.

        Returns
        -------
        ImportSummary
            Summary of the import operation.
        """

        summary = ImportSummary()

        path = Path(path)

        logger.info("Importing %s", path)

        with path.open(
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            while True:

                raw_pgn = self._read_raw_game(file)

                if not raw_pgn.strip():
                    break

                summary.processed += 1

                game_hash = compute_pgn_hash(raw_pgn)

                if self._game_exists(game_hash):
                    summary.skipped += 1
                    existing_game = self.session.query(Game).filter(Game.pgn_hash == game_hash).first()
                    if existing_game:
                        summary.game_ids.append(existing_game.id)
                    continue

                try:

                    game = chess.pgn.read_game(
                        io.StringIO(raw_pgn)
                    )

                    if game is None:
                        summary.failed += 1

                        logger.warning(
                            "Skipping unreadable PGN."
                        )
                        continue

                    parsed = parse_pgn(game)

                    white = resolve_player(
                        self.session,
                        parsed.white_name,
                        parse_int(game.headers.get("WhiteFideId")),
                        game.headers.get("WhiteTitle"),
                        game.headers.get("WhiteFideCountry"),
                    )

                    black = resolve_player(
                        self.session,
                        parsed.black_name,
                        parse_int(game.headers.get("BlackFideId")),
                        game.headers.get("BlackTitle"),
                        game.headers.get("BlackFideCountry"),
                    )

                    parsed.game.white_player = white
                    parsed.game.black_player = black
                    parsed.game.pgn_hash = game_hash

                    self.session.add(parsed.game)

                    self.session.flush()
                    if parsed.game.id:
                        summary.game_ids.append(parsed.game.id)

                    for move in parsed.moves:
                        move.game = parsed.game

                    self.session.add_all(parsed.moves)

                    summary.imported += 1

                    if (
                        summary.imported > 0
                        and summary.imported % BATCH_SIZE == 0
                    ):
                        self.session.commit()

                        logger.info(
                            "Processed=%d Imported=%d Skipped=%d Failed=%d",
                            summary.processed,
                            summary.imported,
                            summary.skipped,
                            summary.failed,
                        )

                except Exception as exc:

                    summary.failed += 1

                    self.session.rollback()

                    logger.exception(
                        "Failed importing game: %s",
                        exc,
                    )

        try:
            self.session.commit()

        except SQLAlchemyError:
            self.session.rollback()
            raise

        logger.info("Import complete.")

        logger.info(
            "Processed=%d Imported=%d Skipped=%d Failed=%d",
            summary.processed,
            summary.imported,
            summary.skipped,
            summary.failed,
        )

        return summary

    def _game_exists(self, pgn_hash: str) -> bool:
        """
        Return True if a PGN already exists.
        """

        return (
            self.session.query(Game.id)
            .filter(Game.pgn_hash == pgn_hash)
            .first()
            is not None
        )
        
    def _read_raw_game(self, file: TextIO) -> str:
        """
        Read a single PGN game from an open stream.

        Uses a one-line lookahead buffer instead of rewinding the
        file pointer, making it safe for large UTF-8 PGN files.

        Returns
        -------
        str
            Raw PGN text.

            Returns an empty string when EOF is reached.
        """
        lines: list[str] = []

        # Consume buffered line from previous read.
        if self._buffered_line is not None:
            lines.append(self._buffered_line)
            self._buffered_line = None


        while True:

            line = file.readline()

            if not line:
                break

            # Beginning of next game's headers.
            if line.startswith("[Event ") and lines:
                self._buffered_line = line
                break

            lines.append(line)

        return "".join(lines).strip()
