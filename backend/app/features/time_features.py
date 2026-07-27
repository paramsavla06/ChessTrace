"""
Time feature extractor.

Extracts clock and time management metrics from Move ORM objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.models.move import Move, MoveColor


class TimeControl(str, Enum):
    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"
    CLASSICAL = "classical"


@dataclass(slots=True, frozen=True)
class TimeFeatures:
    think_time: float
    time_remaining: float
    is_time_pressure_120s: bool
    is_time_pressure_60s: bool
    is_time_pressure_30s: bool
    time_usage_ratio: float
    running_avg_think_time: float
    think_time_deviation: float
    time_control: str


def classify_time_control(initial_clock_seconds: int | None) -> str:
    """Classify game time control format based on initial clock seconds."""
    if initial_clock_seconds is None:
        return TimeControl.BLITZ.value
    if initial_clock_seconds < 180:
        return TimeControl.BULLET.value
    if initial_clock_seconds <= 600:
        return TimeControl.BLITZ.value
    if initial_clock_seconds <= 1800:
        return TimeControl.RAPID.value
    return TimeControl.CLASSICAL.value


def extract_time_features(
    move: Move,
    previous_moves_same_color: Sequence[Move],
    initial_clock_seconds: int | None = None,
) -> TimeFeatures:
    """
    Extract clock and time management metrics for a single move.

    Parameters
    ----------
    move
        Move entity to analyze.

    previous_moves_same_color
        Prior moves played by the same player in the current game.

    initial_clock_seconds
        Optional starting clock time for the game to classify time control.

    Returns
    -------
    TimeFeatures
        Extracted time features DTO.
    """
    think_time = float(move.time_spent or 0.0)
    time_remaining = float(move.clock_after or 0.0)

    is_120s = time_remaining < 120.0 and time_remaining > 0.0
    is_60s = time_remaining < 60.0 and time_remaining > 0.0
    is_30s = time_remaining < 30.0 and time_remaining > 0.0

    time_usage_ratio = think_time / max(time_remaining, 1.0)

    prior_think_times = [
        float(m.time_spent)
        for m in previous_moves_same_color
        if m.time_spent is not None
    ]

    if prior_think_times:
        running_avg = sum(prior_think_times) / len(prior_think_times)
    else:
        running_avg = think_time

    think_deviation = think_time - running_avg
    tc_category = classify_time_control(initial_clock_seconds)

    return TimeFeatures(
        think_time=think_time,
        time_remaining=time_remaining,
        is_time_pressure_120s=is_120s,
        is_time_pressure_60s=is_60s,
        is_time_pressure_30s=is_30s,
        time_usage_ratio=time_usage_ratio,
        running_avg_think_time=running_avg,
        think_time_deviation=think_deviation,
        time_control=tc_category,
    )
