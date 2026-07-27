"""
Schema representing the evaluation of a single chess position.

Used as the data transfer object (DTO) between the Stockfish engine
and the rest of the ChessTrace application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(slots=True, frozen=True)
class EvaluationResult:
    """
    Represents the evaluation of a single chess position.

    Responsibilities
    ----------------
    - Store the result of evaluating one position.
    - Provide an immutable interface between the engine layer and
      the rest of the application.

    Non-responsibilities
    --------------------
    - Running Stockfish
    - Database operations
    - Feature extraction
    - Game analysis
    """

    # ------------------------------------------------------------------
    # Position metadata
    # ------------------------------------------------------------------

    move_number: int
    fen: str

    # ------------------------------------------------------------------
    # Engine evaluation
    # ------------------------------------------------------------------

    depth: int

    cp_score: int | None
    mate_score: int | None

    # ------------------------------------------------------------------
    # Move information
    # ------------------------------------------------------------------

    played_move: str | None = None
    best_move: str | None = None

    principal_variation: Sequence[str] = field(default_factory=tuple)

    # ------------------------------------------------------------------
    # Engine statistics
    # ------------------------------------------------------------------

    nodes: int = 0
    nps: int = 0
    time_ms: int = 0
