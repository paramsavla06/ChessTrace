"""
Test suite for the 6 advanced AI/ML & analytics intelligence features.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import chess
from fastapi.testclient import TestClient

from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.main import app
from app.ml.anomaly import AnomalyDetector
from app.ml.clustering import PlayerArchetypeClassifier
from app.ml.elo_model import EloSimulatorManager
from app.ml.pattern_detector import CrossGamePatternDetector
from app.ml.similarity import PlayerSimilarityEngine
from app.models.game import Game, GameResult
from app.models.move import Move, MoveColor

client = TestClient(app)


def test_elo_simulator():
    board = chess.Board()
    pos = extract_position_features(board)
    move_obj = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE,
        san="e4",
        uci="e2e4",
        fen=board.fen(),
        time_spent=2000,
        clock_after=178000,
    )
    time_f = extract_time_features(move_obj, previous_moves_same_color=[])

    sim = EloSimulatorManager()
    res = sim.predict_for_elo(board, pos, time_f, "1600-1800")
    assert res.elo_bucket == "1600-1800"
    assert len(res.top_candidate_moves) > 0


def test_what_if_endpoint():
    payload = {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "played_move_uci": "d2d4",
        "alternative_move_uci": "c2c3",
        "think_time_sec": 3.5,
        "time_remaining_sec": 140.0,
    }
    response = client.post("/api/v1/analysis/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "probability_divergence" in data


def test_elo_sim_endpoint():
    payload = {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "target_elo_bucket": "1800-2000",
        "time_remaining_sec": 110.0,
    }
    response = client.post("/api/v1/analysis/elo-sim", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["elo_bucket"] == "1800-2000"
    assert len(data["top_candidate_moves"]) > 0


if __name__ == "__main__":
    test_elo_simulator()
    test_what_if_endpoint()
    test_elo_sim_endpoint()
    print("All 6 advanced AI/ML features tested successfully!")
