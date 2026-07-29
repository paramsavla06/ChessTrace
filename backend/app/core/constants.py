"""
Application-wide domain constants.
"""

from __future__ import annotations

ELO_BUCKETS = [
    "<1000",
    "1000-1200",
    "1200-1400",
    "1400-1600",
    "1600-1800",
    "1800-2000",
    "2000+",
]

TIME_CONTROLS = ["bullet", "blitz", "rapid", "classical"]

GAME_PHASES = ["opening", "middlegame", "endgame"]
