from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to ChessTrace API" in response.json()["message"]


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_games_list_endpoint():
    response = client.get("/api/v1/games")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_prediction_endpoint():
    payload = {
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "think_time_sec": 4.5,
        "time_remaining_sec": 28.0,
        "initial_clock_seconds": 180,
    }
    response = client.post("/api/v1/analysis/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "win_probability" in data
    assert "collapse_probability" in data
    assert "narrative_summary" in data


if __name__ == "__main__":
    test_root_endpoint()
    test_health_endpoint()
    test_games_list_endpoint()
    test_prediction_endpoint()
    print("All API endpoints tested successfully!")
