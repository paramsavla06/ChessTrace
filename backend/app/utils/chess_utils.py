"""
Utility functions used throughout the ChessTrace PGN import pipeline.

This module contains helper functions for:

- Player name normalization
- PGN hashing
- Safe parsing of PGN header values
- Date parsing
- Time control parsing
- Clock conversion
- Result conversion

These utilities are intentionally stateless and reusable.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Final

from app.models.game import GameResult


UNKNOWN_VALUES: Final[set[str]] = {
    "",
    "?",
    "??",
    "-",
    "unknown",
    "none",
}


def compute_pgn_hash(pgn_text: str) -> str:
    """
    Compute a SHA-256 hash for the raw pgn text.
    Used to detect duplicate games.

    Args:
        pgn_text:
            Raw PGN text.

    Returns:
        64-character hexadecimal SHA-256 hash.
    """

    return hashlib.sha256(pgn_text.encode("utf-8")).hexdigest()


def normalize_player_name(name: str) -> str:
    """
    Normalize a player name for database lookup.

    Operations:
    - Remove leading/trailing whitespace
    - Collapse multiple spaces
    - Case-insensitive normalization

    Example:
        " Magnus   Carlsen "
        ->
        "magnus carlsen"
    """

    return " ".join(
        name.casefold().split()
    )


def parse_int(value: str | None) -> int | None:
    """
    Safely converting a string into an integer.

    Returns None if coversion is impossible
    """

    if value is None:
        return None

    value = value.strip()

    if value.casefold() in UNKNOWN_VALUES:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def parse_game_date(value: str | None) -> date | None:
    """
    Parse a PGN Date tag.

    Supported examples:

        2023.04.15
        2023-04-15

    Unknown dates return None.
    """

    if value is None:
        return None

    value = value.strip()

    if value.casefold() in UNKNOWN_VALUES:
        return None

    value = value.replace("-", ".")

    parts = value.split(".")

    if len(parts) != 3:
        return None

    try:
        year = int(parts[0])

        if "?" in parts[1] or "?" in parts[2]:
            return None

        month = int(parts[1])
        day = int(parts[2])

        return date(year, month, day)

    except Exception:
        return None


def parse_result(result: str) -> GameResult:
    """
    Convert PGN result string into GameResult enum.
    """

    mapping = {
        "1-0": GameResult.WHITE_WIN,
        "0-1": GameResult.BLACK_WIN,
        "1/2-1/2": GameResult.DRAW,
        "*": GameResult.ONGOING,
    }

    return mapping.get(result, GameResult.ONGOING)


def normalize_time_control(value: str | None) -> str | None:
    """
    Normalize PGN TimeControl tag.

    Examples:

        600+5
        180+2
        60+0

    Returns None for unknown values.
    """

    if value is None:
        return None

    value = value.strip()

    if value.casefold() in UNKNOWN_VALUES:
        return None

    return value


_ECO_PATTERN = re.compile(r"^[A-E][0-9]{2}$")


def normalize_eco(eco: str | None) -> str | None:
    """
    Validate and normalize ECO code.

    Examples:

        B12
        C65

    Invalid values return None.
    """

    if eco is None:
        return None

    eco = eco.strip().upper()

    if _ECO_PATTERN.fullmatch(eco):
        return eco

    return None


def clean_header(value: str | None) -> str | None:
    """
    Normalize generic PGN header strings.

    Removes extra whitespace and converts unknown values to None.
    """

    if value is None:
        return None

    value = " ".join(value.split())

    if value.casefold() in UNKNOWN_VALUES:
        return None

    return value


_CLOCK_PATTERN = re.compile(
    r"^(?:(\d+):)?(\d+):(\d+)(?:\.(\d+))?$"
)


def parse_clock(clock: str | None) -> int | None:
    """
    Convert a PGN clock annotation into milliseconds.

    Supported formats:

        1:23:45
        05:14
        00:01:52.4

    Returns:
        Milliseconds remaining on the clock.
    """

    if clock is None:
        return None

    clock = clock.strip()

    if clock.casefold() in UNKNOWN_VALUES:
        return None

    match = _CLOCK_PATTERN.match(clock)

    if not match:
        return None

    hours, minutes, seconds, fraction = match.groups()

    hours = int(hours or 0)
    minutes = int(minutes)
    seconds = int(seconds)

    milliseconds = int((fraction or "0").ljust(3, "0")[:3])

    total = (
        hours * 3600
        + minutes * 60
        + seconds
    ) * 1000

    total += milliseconds

    return total
