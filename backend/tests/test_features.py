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
from app.features.time_features import extract_time_features, TimeControl
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


if __name__ == "__main__":
    test_position_features_starting_board()
    test_time_features_extraction()
    print("All feature tests passed!")
