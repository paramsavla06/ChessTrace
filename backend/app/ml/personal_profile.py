"""
Personal Profile Fingerprint Engine for ChessTrace.

Decodes a player's unique chess fingerprint from historical game and move data:
- Accuracy vs. Clock remaining degradation curve
- Tilt signature (post-material loss think time & blunder rate)
- Panic play vs overthink move detection
- Time management distribution (opening/middlegame/endgame)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.models.game import Game
from app.models.move import Move, MoveColor


@dataclass(slots=True, frozen=True)
class AccuracyVsClockBucket:
    clock_bucket: str
    move_count: int
    avg_think_time: float


@dataclass(slots=True, frozen=True)
class TiltSignature:
    normal_avg_think_time: float
    post_material_loss_think_time: float
    tilt_speedup_percentage: float
    is_panic_tilted: bool


@dataclass(slots=True, frozen=True)
class TimeManagementDistribution:
    opening_time_pct: float
    middlegame_time_pct: float
    endgame_time_pct: float


@dataclass(slots=True, frozen=True)
class PersonalProfileFingerprint:
    player_name: str
    total_games_analyzed: int
    accuracy_vs_clock: list[AccuracyVsClockBucket]
    tilt_signature: TiltSignature
    time_distribution: TimeManagementDistribution
    panic_move_count: int
    overthink_move_count: int


def generate_personal_profile(
    player_name: str,
    games: Sequence[Game],
) -> PersonalProfileFingerprint:
    """
    Generate player's personal chess fingerprint from game history.

    Parameters
    ----------
    player_name
        Display name of the target player.

    games
        Collection of Game models with loaded moves.

    Returns
    -------
    PersonalProfileFingerprint
        Comprehensive personal fingerprint DTO.
    """
    total_games = len(games)

    all_player_moves: list[Move] = []
    post_loss_moves: list[Move] = []

    bucket_5m: list[float] = []
    bucket_2_5m: list[float] = []
    bucket_1_2m: list[float] = []
    bucket_sub1m: list[float] = []

    opening_time_sec = 0.0
    middlegame_time_sec = 0.0
    endgame_time_sec = 0.0

    panic_moves = 0
    overthink_moves = 0

    for game in games:
        # Determine player color in game
        is_white = (
            game.white_player and game.white_player.display_name.lower() == player_name.lower()
        )
        player_color = MoveColor.WHITE if is_white else MoveColor.BLACK

        prev_material_balance = 0
        material_loss_flag = False

        prior_thinks: list[float] = []

        for move in game.moves:
            if move.color != player_color:
                continue

            all_player_moves.append(move)
            think_sec = (move.time_spent or 0) / 1000.0
            clock_sec = (move.clock_after or 0) / 1000.0

            # Track time distribution across game phases
            if move.move_number <= 12:
                opening_time_sec += think_sec
            elif move.move_number <= 35:
                middlegame_time_sec += think_sec
            else:
                endgame_time_sec += think_sec

            # Bucket clock remaining
            if clock_sec >= 300.0:
                bucket_5m.append(think_sec)
            elif clock_sec >= 120.0:
                bucket_2_5m.append(think_sec)
            elif clock_sec >= 60.0:
                bucket_1_2m.append(think_sec)
            elif clock_sec > 0.0:
                bucket_sub1m.append(think_sec)

            # Check tilt (move played after losing material)
            if material_loss_flag:
                post_loss_moves.append(move)
                material_loss_flag = False

            if move.is_capture:
                material_loss_flag = True

            # Detect panic (think time < 30% of running average) vs overthink (> 3x running average)
            if prior_thinks:
                avg_prior = sum(prior_thinks) / len(prior_thinks)
                if avg_prior > 5.0 and think_sec < (avg_prior * 0.3):
                    panic_moves += 1
                elif avg_prior > 5.0 and think_sec > (avg_prior * 3.0):
                    overthink_moves += 1

            if move.time_spent is not None:
                prior_thinks.append(think_sec)

    # Compute clock buckets
    accuracy_vs_clock = [
        AccuracyVsClockBucket(
            clock_bucket="5m+",
            move_count=len(bucket_5m),
            avg_think_time=sum(bucket_5m) / max(len(bucket_5m), 1),
        ),
        AccuracyVsClockBucket(
            clock_bucket="2-5m",
            move_count=len(bucket_2_5m),
            avg_think_time=sum(bucket_2_5m) / max(len(bucket_2_5m), 1),
        ),
        AccuracyVsClockBucket(
            clock_bucket="1-2m",
            move_count=len(bucket_1_2m),
            avg_think_time=sum(bucket_1_2m) / max(len(bucket_1_2m), 1),
        ),
        AccuracyVsClockBucket(
            clock_bucket="<1m",
            move_count=len(bucket_sub1m),
            avg_think_time=sum(bucket_sub1m) / max(len(bucket_sub1m), 1),
        ),
    ]

    # Compute tilt signature
    all_thinks = [
        (m.time_spent or 0) / 1000.0 for m in all_player_moves if m.time_spent is not None
    ]
    post_loss_thinks = [
        (m.time_spent or 0) / 1000.0 for m in post_loss_moves if m.time_spent is not None
    ]

    norm_avg = sum(all_thinks) / max(len(all_thinks), 1)
    post_avg = (
        sum(post_loss_thinks) / max(len(post_loss_thinks), 1) if post_loss_thinks else norm_avg
    )

    speedup_pct = ((norm_avg - post_avg) / max(norm_avg, 1.0)) * 100.0
    is_tilted = speedup_pct > 20.0

    tilt_sig = TiltSignature(
        normal_avg_think_time=norm_avg,
        post_material_loss_think_time=post_avg,
        tilt_speedup_percentage=speedup_pct,
        is_panic_tilted=is_tilted,
    )

    # Compute time distribution percentages
    total_sec = max(opening_time_sec + middlegame_time_sec + endgame_time_sec, 1.0)
    time_dist = TimeManagementDistribution(
        opening_time_pct=(opening_time_sec / total_sec) * 100.0,
        middlegame_time_pct=(middlegame_time_sec / total_sec) * 100.0,
        endgame_time_pct=(endgame_time_sec / total_sec) * 100.0,
    )

    return PersonalProfileFingerprint(
        player_name=player_name,
        total_games_analyzed=total_games,
        accuracy_vs_clock=accuracy_vs_clock,
        tilt_signature=tilt_sig,
        time_distribution=time_dist,
        panic_move_count=panic_moves,
        overthink_move_count=overthink_moves,
    )
