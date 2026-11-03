"""
Time feature extractor.

Extracts clock and time management metrics from Move ORM objects.
Handles missing clock telemetry safely without zero-biasing or synthesizing fake clocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.models.move import Move, MoveColor


class TimeControl(str, Enum):
    UNKNOWN = "unknown"
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
    has_clock_data: bool = True


def classify_time_control(initial_clock_seconds: int | None) -> str:
    """
    Classify game time control format based on initial clock seconds.
    Returns 'unknown' when initial clock telemetry is missing or unavailable.
    """
    if initial_clock_seconds is None or initial_clock_seconds <= 0:
        return TimeControl.UNKNOWN.value
    if initial_clock_seconds < 180:
        return TimeControl.BULLET.value
    if initial_clock_seconds <= 600:
        return TimeControl.BLITZ.value
    if initial_clock_seconds <= 1800:
        return TimeControl.RAPID.value
    return TimeControl.CLASSICAL.value


def _normalize_seconds(val: int | float | None) -> float | None:
    """
    Safely convert clock timestamps to float seconds.
    Detects if millisecond timestamps (e.g. 85000ms) or second timestamps (e.g. 85s) were supplied.
    """
    if val is None:
        return None
    f_val = float(val)
    if f_val >= 1000.0:
        return f_val / 1000.0
    return f_val


def extract_time_features(
    move: Move,
    previous_moves_same_color: Sequence[Move],
    initial_clock_seconds: int | None = None,
) -> TimeFeatures:
    """
    Extract clock and time management metrics for a single move.
    Only uses time features when genuine clock telemetry exists.

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
        Extracted time features DTO. If clock data is missing, has_clock_data is False
        and time metrics are strictly zeroed out.
    """
    has_clock = (move.clock_after is not None) or (move.time_spent is not None and move.time_spent > 0)
    norm_clock_after = _normalize_seconds(move.clock_after)
    norm_time_spent = _normalize_seconds(move.time_spent)
    norm_clock_before = _normalize_seconds(move.clock_before)

    tc_category = classify_time_control(initial_clock_seconds)

    # When no clock telemetry exists in the game, do NOT synthesize fake times
    if not has_clock:
        return TimeFeatures(
            think_time=0.0,
            time_remaining=0.0,
            is_time_pressure_120s=False,
            is_time_pressure_60s=False,
            is_time_pressure_30s=False,
            time_usage_ratio=0.0,
            running_avg_think_time=0.0,
            think_time_deviation=0.0,
            time_control=tc_category,
            has_clock_data=False,
        )

    # 1. Resolve think_time (in seconds)
    if norm_time_spent is not None:
        think_time = max(0.0, norm_time_spent)
    elif norm_clock_before is not None and norm_clock_after is not None:
        think_time = max(0.0, norm_clock_before - norm_clock_after)
    else:
        prior_spents = [
            _normalize_seconds(m.time_spent)
            for m in previous_moves_same_color
            if m.time_spent is not None
        ]
        prior_valid = [s for s in prior_spents if s is not None and s > 0]
        think_time = sum(prior_valid) / len(prior_valid) if prior_valid else 0.0

    # 2. Resolve time_remaining (in seconds)
    if norm_clock_after is not None:
        time_remaining = max(0.0, norm_clock_after)
    elif initial_clock_seconds is not None and initial_clock_seconds > 0:
        time_remaining = float(initial_clock_seconds)
    else:
        time_remaining = 0.0

    # 3. Time pressure boundary handling
    is_120s = 0.0 < time_remaining <= 120.0
    is_60s = 0.0 < time_remaining <= 60.0
    is_30s = 0.0 < time_remaining <= 30.0

    # 4. Time usage ratio: think_time divided by clock_before
    if norm_clock_before is not None and norm_clock_before > 0:
        available_clock = norm_clock_before
    else:
        available_clock = time_remaining + think_time

    time_usage_ratio = min(1.0, max(0.0, think_time / max(available_clock, 1.0)))

    # 5. Running think time average and deviation
    prior_think_times = [
        _normalize_seconds(m.time_spent)
        for m in previous_moves_same_color
        if m.time_spent is not None
    ]
    valid_priors = [t for t in prior_think_times if t is not None]

    if valid_priors:
        running_avg = sum(valid_priors) / len(valid_priors)
    else:
        running_avg = think_time

    think_deviation = think_time - running_avg

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
        has_clock_data=True,
    )
