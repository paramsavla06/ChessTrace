"""
Lichess API Service.

Responsible for auto-fetching user game history with clock data from Lichess.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import LICHESS_API_TOKEN
from app.schemas.import_summary import ImportSummary
from app.services.import_services import ImportService
from app.utils.chess_utils import compute_pgn_hash

logger = logging.getLogger(__name__)


class LichessService:
    """
    Service for fetching public games from the Lichess REST API.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.import_service = ImportService(session)

    def import_user_games(
        self,
        username: str,
        *,
        max_games: int = 50,
    ) -> ImportSummary:
        """
        Download games for a Lichess user and import them into the database.

        Parameters
        ----------
        username
            Lichess username.
        max_games
            Maximum games to fetch.

        Returns
        -------
        ImportSummary
            Summary of import operation.
        """
        import os
        import httpx
        url = f"https://lichess.org/api/games/user/{username}"
        params = {
            "max": max_games,
            "clocks": "true",
            "evals": "false",
            "opening": "true",
        }
        headers = {
            "User-Agent": "ChessTrace/1.0 (https://github.com/paramsavla06/ChessTrace)",
            "Accept": "application/x-chess-pgn",
        }

        api_token = LICHESS_API_TOKEN or os.getenv("LICHESS_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        summary = ImportSummary()

        logger.info("Fetching up to %d Lichess games for user '%s'", max_games, username)

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params, headers=headers, follow_redirects=True)
                if response.status_code == 404:
                    raise ValueError(f"Lichess user '{username}' not found or has no public games.")
                if response.status_code == 429:
                    retry_sec = response.headers.get("Retry-After", "60")
                    raise ValueError(f"Lichess rate limit exceeded (HTTP 429). Please wait {retry_sec} seconds before trying again.")
                response.raise_for_status()
                pgn_text = response.text

            if not pgn_text.strip():
                return summary

            # Stream games from pgn_text
            import io
            file_stream = io.StringIO(pgn_text)

            while True:
                raw_pgn = self.import_service._read_raw_game(file_stream)
                if not raw_pgn.strip():
                    break

                summary.processed += 1
                game_hash = compute_pgn_hash(raw_pgn)

                if self.import_service._game_exists(game_hash):
                    summary.skipped += 1
                    continue

                try:
                    import chess.pgn
                    game = chess.pgn.read_game(io.StringIO(raw_pgn))
                    if game is None:
                        summary.failed += 1
                        continue

                    from app.parsers.pgn_parser import parse_pgn
                    from app.parsers.player_parser import resolve_player
                    from app.utils.chess_utils import parse_int

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

                    for move in parsed.moves:
                        move.game = parsed.game
                    self.session.add_all(parsed.moves)

                    summary.imported += 1
                except Exception as exc:
                    summary.failed += 1
                    logger.warning("Failed importing game: %s", exc)

            self.session.commit()
            return summary

        except Exception as exc:
            self.session.rollback()
            logger.exception("Failed to fetch Lichess games for user %s: %s", username, exc)
            raise
