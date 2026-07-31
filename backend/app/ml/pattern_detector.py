"""
Cross-Game Recurring Pattern Detector.

Identifies recurring tactical, positional, and time management mistake patterns
across a player's last N games.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from app.models.game import Game

logger = logging.getLogger(__name__)


@dataclass
class RecurringPattern:
    pattern_name: str
    category: str  # "time_management" | "tactical" | "endgame" | "opening"
    frequency_count: int
    impact_severity: str  # "high" | "medium" | "low"
    recommendation: str


class CrossGamePatternDetector:
    """
    Scans a sequence of games to detect recurring mistake patterns.
    """

    def detect_patterns(self, games: Sequence[Game]) -> list[RecurringPattern]:
        """
        Detect recurring mistake patterns across games.
        """
        patterns: list[RecurringPattern] = []
        if not games:
            return patterns

        total_games = len(games)
        sub_30s_blunder_count = 0
        opening_overthink_count = 0
        endgame_rush_count = 0

        for game in games:
            for move in game.moves:
                if not move.time_spent or not move.clock_after:
                    continue

                think_sec = move.time_spent / 1000.0
                clock_sec = move.clock_after / 1000.0

                # 1. Panic under 30s clock
                if clock_sec < 30.0 and think_sec < 1.0:
                    sub_30s_blunder_count += 1

                # 2. Overthinking in early opening (moves 1-10)
                if move.move_number <= 10 and think_sec > 15.0:
                    opening_overthink_count += 1

                # 3. Rushing in late endgame (moves 40+)
                if move.move_number >= 40 and think_sec < 2.0:
                    endgame_rush_count += 1

        if sub_30s_blunder_count >= 2:
            patterns.append(
                RecurringPattern(
                    pattern_name="Time-Pressure Rush (<30s Clock)",
                    category="time_management",
                    frequency_count=sub_30s_blunder_count,
                    impact_severity="high",
                    recommendation="Practice pre-moving standard responses and maintain a minimum 3-second buffer per move in low-clock situations.",
                )
            )

        if opening_overthink_count >= 2:
            patterns.append(
                RecurringPattern(
                    pattern_name="Opening Move Overthinking",
                    category="opening",
                    frequency_count=opening_overthink_count,
                    impact_severity="medium",
                    recommendation="Memorize your core opening repertoire to save clock time for complex middlegame positions.",
                )
            )

        if endgame_rush_count >= 3:
            patterns.append(
                RecurringPattern(
                    pattern_name="Endgame Move Rushing",
                    category="endgame",
                    frequency_count=endgame_rush_count,
                    impact_severity="high",
                    recommendation="Slow down in technical endgames; calculate king-pawn races thoroughly before committing.",
                )
            )

        return patterns
