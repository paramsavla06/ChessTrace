"""
Stockfish engine wrapper.

Responsible for managing a Stockfish engine process.

Responsibilities
----------------
- Launch Stockfish
- Configure engine options
- Analyse chess positions
- Shut down the engine cleanly

Non-responsibilities
--------------------
- Database operations
- Feature extraction
- Game iteration
- ML predictions
"""
from __future__ import annotations

from pathlib import Path

import chess
import chess.engine

from app.engine.limits import (
    DEFAULT_DEPTH,
    DEFAULT_HASH_MB,
    DEFAULT_THREADS,
)

import threading

# Global lock to ensure only ONE Stockfish process runs at a time across all FastAPI threads
stockfish_lock = threading.Lock()

class StockfishEngine:
    """
    Thin wrapper around python-chess's UCI engine.
    """
    
    def __init__(
		self,
		engine_path: str | Path,
		*,
		threads: int = DEFAULT_THREADS,
		hash_mb: int = DEFAULT_HASH_MB,
	) -> None:
        stockfish_lock.acquire()
        try:
            self._engine: chess.engine.SimpleEngine = (
				chess.engine.SimpleEngine.popen_uci(str(engine_path))
			)
            self._engine.configure(
                {
                    "Threads": threads,
                    "Hash": hash_mb,
                }
            )
        except (FileNotFoundError, OSError) as exc:
            stockfish_lock.release()
            raise RuntimeError(
				f"Failed to start Stockfish engine: {engine_path}"
			) from exc
        
    def analyse(
		self,
		board: chess.Board,
		*,
		depth: int = DEFAULT_DEPTH,
	) -> chess.engine.InfoDict:
        """
        Analyse a position.

        Parameters
        ----------
        board
            Position to analyse.

        depth
            Search depth.

        Returns
        -------
        chess.engine.InfoDict
            Raw engine analysis.
        """
        return self._engine.analyse(board, chess.engine.Limit(depth=depth))
    
    @property
    def version(self) -> str:
        """Return the name/version of the running engine."""
        return self._engine.id.get("name", "Stockfish")

    def quit(self) -> None:
        """Shut down the Stockfish engine."""
        try:
            self._engine.quit()
            self._engine.close()
        except chess.engine.EngineTerminatedError:
            pass

    def __enter__(self) -> "StockfishEngine":
        return self

    from types import TracebackType
    
    def __exit__(
		self,
		exc_type: type[BaseException] | None,
		exc: BaseException | None,
		tb: TracebackType | None,
	) -> None:
        try:
            self.quit()
        finally:
            stockfish_lock.release()

