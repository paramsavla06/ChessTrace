"""
Unit tests for position and clock feature extraction pipelines.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import chess
from app.features.position_features import extract_position_features, GamePhase
from app.features.time_features import (
    extract_time_features,
    classify_time_control,
    _normalize_seconds,
    TimeControl,
)
from app.models.move import Move, MoveColor


def test_position_features_starting_board():
    board = chess.Board()
    features = extract_position_features(board)

    assert features.material_balance == 0
    assert features.white_material == 39
    assert features.black_material == 39
    assert features.game_phase == GamePhase.OPENING.value
    assert features.white_mobility > 0
    assert features.black_mobility > 0


def test_time_features_extraction():
    move = Move(
        game_id=1,
        move_number=10,
        ply=19,
        color=MoveColor.WHITE,
        san="Nf3",
        uci="g1f3",
        fen="rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        time_spent=12000,
        clock_after=85000,
    )

    prev_move = Move(
        game_id=1,
        move_number=9,
        ply=17,
        color=MoveColor.WHITE,
        san="e4",
        uci="e2e4",
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        time_spent=8000,
        clock_after=97000,
    )

    features = extract_time_features(
        move,
        previous_moves_same_color=[prev_move],
        initial_clock_seconds=300,
    )

    assert features.think_time == 12.0
    assert features.time_remaining == 85.0
    assert features.is_time_pressure_120s is True
    assert features.is_time_pressure_60s is False
    assert features.running_avg_think_time == 8.0
    assert features.think_time_deviation == 4.0
    assert features.time_control == TimeControl.BLITZ.value


def test_normalize_seconds_unit():
    """Unit tests for _normalize_seconds covering None, negative, zero, sub-second, and boundary values."""
    # Missing / None
    assert _normalize_seconds(None) is None

    # Negative values clamped safely to 0.0
    assert _normalize_seconds(-500) == 0.0
    assert _normalize_seconds(-1) == 0.0
    assert _normalize_seconds(-12500) == 0.0

    # Zero
    assert _normalize_seconds(0) == 0.0
    assert _normalize_seconds(0.0) == 0.0

    # Sub-second values (milliseconds < 1000)
    assert _normalize_seconds(1) == 0.001
    assert _normalize_seconds(450) == 0.45
    assert _normalize_seconds(999) == 0.999

    # Boundary: exactly 1 second
    assert _normalize_seconds(1000) == 1.0

    # Multi-second standard game values
    assert _normalize_seconds(2500) == 2.5
    assert _normalize_seconds(30000) == 30.0
    assert _normalize_seconds(85000) == 85.0

    # Classical long clocks (where old heuristic failed if seconds were passed)
    assert _normalize_seconds(1200000) == 1200.0  # 20 minutes in ms
    assert _normalize_seconds(5400000) == 5400.0  # 90 minutes in ms


def test_extract_time_features_fast_move_and_low_clock_scramble():
    """Integration test for sub-second bullet move and low-clock scramble."""
    move = Move(
        game_id=1,
        move_number=35,
        ply=69,
        color=MoveColor.WHITE,
        san="Kh1",
        uci="g1h1",
        fen="7k/8/8/8/8/8/8/7K b - - 0 35",
        time_spent=350,   # Fast bullet premove / snap move: 350ms (0.35s)
        clock_after=800,  # Critical clock scramble: 800ms remaining (0.8s)
    )

    features = extract_time_features(
        move,
        previous_moves_same_color=[],
        initial_clock_seconds=60,
    )

    assert features.has_clock_data is True
    assert features.think_time == 0.35
    assert features.time_remaining == 0.8
    assert features.is_time_pressure_30s is True
    assert features.is_time_pressure_60s is True
    assert features.is_time_pressure_120s is True
    assert features.time_control == TimeControl.BULLET.value
    # Available clock before move = clock_after + think_time = 0.8 + 0.35 = 1.15
    # time_usage_ratio = 0.35 / 1.15
    assert 0.0 < features.time_usage_ratio <= 1.0


def test_extract_time_features_threshold_boundaries_and_negatives():
    """Integration test covering exact 30s/60s/120s thresholds, negative clamp, and Classical clocks."""
    # Boundary: exactly 30.0s remaining
    m_30 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=30000,
    )
    f_30 = extract_time_features(m_30, previous_moves_same_color=[])
    assert f_30.time_remaining == 30.0
    assert f_30.is_time_pressure_30s is True
    assert f_30.is_time_pressure_60s is True
    assert f_30.is_time_pressure_120s is True

    # Boundary: 30.1s remaining (just above 30s)
    m_30_1 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=30100,
    )
    f_30_1 = extract_time_features(m_30_1, previous_moves_same_color=[])
    assert f_30_1.time_remaining == 30.1
    assert f_30_1.is_time_pressure_30s is False
    assert f_30_1.is_time_pressure_60s is True

    # Boundary: exactly 60.0s remaining
    m_60 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=60000,
    )
    f_60 = extract_time_features(m_60, previous_moves_same_color=[])
    assert f_60.time_remaining == 60.0
    assert f_60.is_time_pressure_60s is True
    assert f_60.is_time_pressure_120s is True

    # Boundary: 60.1s remaining
    m_60_1 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=60100,
    )
    f_60_1 = extract_time_features(m_60_1, previous_moves_same_color=[])
    assert f_60_1.is_time_pressure_60s is False
    assert f_60_1.is_time_pressure_120s is True

    # Boundary: exactly 120.0s remaining
    m_120 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=120000,
    )
    f_120 = extract_time_features(m_120, previous_moves_same_color=[])
    assert f_120.time_remaining == 120.0
    assert f_120.is_time_pressure_120s is True

    # Boundary: 120.1s remaining
    m_120_1 = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=2000, clock_after=120100,
    )
    f_120_1 = extract_time_features(m_120_1, previous_moves_same_color=[])
    assert f_120_1.is_time_pressure_120s is False

    # Negative timestamps clamped safely
    m_neg = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=-500, clock_after=-2000,
    )
    f_neg = extract_time_features(m_neg, previous_moves_same_color=[])
    assert f_neg.think_time == 0.0
    assert f_neg.time_remaining == 0.0

    # Classical long clock: 1 hour (3,600,000ms) left in a 90-minute classical game
    m_classical = Move(
        move_number=20, ply=39, color=MoveColor.WHITE, san="d4", uci="d2d4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=45000, clock_after=3600000,
    )
    f_classical = extract_time_features(m_classical, previous_moves_same_color=[], initial_clock_seconds=5400)
    assert f_classical.think_time == 45.0
    assert f_classical.time_remaining == 3600.0
    assert f_classical.is_time_pressure_120s is False
    assert f_classical.time_control == TimeControl.CLASSICAL.value


def test_extract_time_features_missing_clock():
    """Verify that moves without clock telemetry strictly zero out time features."""
    m_no_clock = Move(
        move_number=1, ply=1, color=MoveColor.WHITE, san="e4", uci="e2e4", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        time_spent=None, clock_after=None,
    )
    f = extract_time_features(m_no_clock, previous_moves_same_color=[])
    assert f.has_clock_data is False
    assert f.think_time == 0.0
    assert f.time_remaining == 0.0
    assert f.is_time_pressure_120s is False
    assert f.is_time_pressure_60s is False
    assert f.is_time_pressure_30s is False
    assert f.time_usage_ratio == 0.0


if __name__ == "__main__":
    test_position_features_starting_board()
    test_time_features_extraction()
    test_normalize_seconds_unit()
    test_extract_time_features_fast_move_and_low_clock_scramble()
    test_extract_time_features_threshold_boundaries_and_negatives()
    test_extract_time_features_missing_clock()
    print("All feature tests passed!")
