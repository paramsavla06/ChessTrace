"""
Analysis & ML Intelligence endpoints.
"""

from __future__ import annotations

from typing import Any
import chess
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import STOCKFISH_PATH
from app.database.dependencies import get_db
from app.engine.analyzer import Analyzer
from app.engine.evaluator import Evaluator
from app.engine.stockfish import StockfishEngine
from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.ml.anomaly import AnomalyDetector
from app.ml.clustering import PlayerArchetypeClassifier
from app.ml.collapse_model import WinCollapsePredictor
from app.ml.elo_model import EloSimulatorManager
from app.ml.explainer import ShapExplainer
from app.ml.pattern_detector import CrossGamePatternDetector
from app.ml.personal_profile import generate_personal_profile
from app.ml.similarity import PlayerSimilarityEngine
from app.repositories.game_repository import GameRepository
from app.services.analysis_services import AnalysisService

router = APIRouter()


class PredictRequest(BaseModel):
    fen: str
    think_time_sec: float = 5.0
    time_remaining_sec: float = 120.0
    initial_clock_seconds: int = 300


class WhatIfRequest(BaseModel):
    fen: str
    played_move_uci: str
    alternative_move_uci: str
    think_time_sec: float = 5.0
    time_remaining_sec: float = 120.0
    initial_clock_seconds: int = 300


class EloSimRequest(BaseModel):
    fen: str
    target_elo_bucket: str = "1600-1800"
    time_remaining_sec: float = 120.0


@router.post("/analysis/game/{game_id}", summary="Run Stockfish analysis on a game")
def analyze_game_by_id(
    game_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger Stockfish engine position evaluation for a game."""
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)

    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    try:
        with StockfishEngine(STOCKFISH_PATH) as engine:
            evaluator = Evaluator(engine)
            analyzer = Analyzer(evaluator)
            service = AnalysisService(db, analyzer, engine)

            eval_count = service.analyze_game(game)
            db.commit()

            return {
                "message": f"Successfully evaluated game ID {game_id}",
                "evaluations_persisted": eval_count,
            }

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Stockfish engine analysis failed: {exc}"
        ) from exc


@router.get("/analysis/profile/{username}", summary="Get player personal fingerprint profile")
def get_player_profile(
    username: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve player personal profile fingerprint & time management metrics."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=500)

    if not games:
        raise HTTPException(
            status_code=404, detail=f"No games found for player '{username}'"
        )

    profile = generate_personal_profile(username, games)

    return {
        "player_name": profile.player_name,
        "total_games_analyzed": profile.total_games_analyzed,
        "accuracy_vs_clock": [
            {
                "clock_bucket": b.clock_bucket,
                "move_count": b.move_count,
                "avg_think_time_sec": round(b.avg_think_time, 2),
            }
            for b in profile.accuracy_vs_clock
        ],
        "tilt_signature": {
            "normal_avg_think_time_sec": round(profile.tilt_signature.normal_avg_think_time, 2),
            "post_material_loss_think_time_sec": round(
                profile.tilt_signature.post_material_loss_think_time, 2
            ),
            "tilt_speedup_percentage": round(profile.tilt_signature.tilt_speedup_percentage, 1),
            "is_panic_tilted": profile.tilt_signature.is_panic_tilted,
        },
        "time_distribution": {
            "opening_time_pct": round(profile.time_distribution.opening_time_pct, 1),
            "middlegame_time_pct": round(profile.time_distribution.middlegame_time_pct, 1),
            "endgame_time_pct": round(profile.time_distribution.endgame_time_pct, 1),
        },
        "panic_move_count": profile.panic_move_count,
        "overthink_move_count": profile.overthink_move_count,
    }


@router.post("/analysis/predict", summary="Predict Win/Collapse probability & SHAP explanation")
def predict_position(req: PredictRequest) -> dict[str, Any]:
    """Run ML predictor and SHAP explainability engine on position & clock inputs."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string.")

    pos_feats = extract_position_features(board)

    from app.models.move import Move, MoveColor
    move_obj = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE if board.turn == chess.WHITE else MoveColor.BLACK,
        san="move",
        uci="e2e4",
        fen=req.fen,
        time_spent=int(req.think_time_sec * 1000),
        clock_after=int(req.time_remaining_sec * 1000),
    )

    time_feats = extract_time_features(
        move_obj,
        previous_moves_same_color=[],
        initial_clock_seconds=req.initial_clock_seconds,
    )

    predictor = WinCollapsePredictor()
    pred = predictor.predict(pos_feats, time_feats)

    explainer = ShapExplainer(predictor)
    exp = explainer.explain(pos_feats, time_feats)

    return {
        "win_probability": round(pred.win_probability, 4),
        "collapse_probability": round(pred.collapse_probability, 4),
        "time_pressure_risk_multiplier": pred.time_pressure_risk_multiplier,
        "narrative_summary": exp.narrative_summary,
        "top_positive_factors": [
            {"feature": f.display_name, "impact": round(f.shap_value, 4)}
            for f in exp.top_positive_factors
        ],
        "top_negative_factors": [
            {"feature": f.display_name, "impact": round(f.shap_value, 4)}
            for f in exp.top_negative_factors
        ],
    }


@router.post("/analysis/what-if", summary="Counterfactual What-If Alternative Move Analysis")
def analyze_what_if(req: WhatIfRequest) -> dict[str, Any]:
    """Evaluate win/collapse probability divergence for played vs alternative move."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string.")

    predictor = WinCollapsePredictor()
    explainer = ShapExplainer(predictor)

    # Played move state
    board_played = board.copy()
    try:
        board_played.push_uci(req.played_move_uci)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid played move UCI '{req.played_move_uci}'")

    pos_played = extract_position_features(board_played)

    from app.models.move import Move, MoveColor
    move_played_obj = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE if board.turn == chess.WHITE else MoveColor.BLACK,
        san="played",
        uci=req.played_move_uci,
        fen=board_played.fen(),
        time_spent=int(req.think_time_sec * 1000),
        clock_after=int(req.time_remaining_sec * 1000),
    )
    time_played = extract_time_features(move_played_obj, previous_moves_same_color=[])
    pred_played = predictor.predict(pos_played, time_played)

    # Alternative move state
    board_alt = board.copy()
    try:
        board_alt.push_uci(req.alternative_move_uci)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid alternative move UCI '{req.alternative_move_uci}'"
        )

    pos_alt = extract_position_features(board_alt)
    move_alt_obj = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE if board.turn == chess.WHITE else MoveColor.BLACK,
        san="alt",
        uci=req.alternative_move_uci,
        fen=board_alt.fen(),
        time_spent=int(req.think_time_sec * 1000),
        clock_after=int(req.time_remaining_sec * 1000),
    )
    time_alt = extract_time_features(move_alt_obj, previous_moves_same_color=[])
    pred_alt = predictor.predict(pos_alt, time_alt)

    win_diff = pred_alt.win_probability - pred_played.win_probability
    collapse_diff = pred_alt.collapse_probability - pred_played.collapse_probability

    return {
        "played_move": {
            "uci": req.played_move_uci,
            "win_probability": round(pred_played.win_probability, 4),
            "collapse_probability": round(pred_played.collapse_probability, 4),
        },
        "alternative_move": {
            "uci": req.alternative_move_uci,
            "win_probability": round(pred_alt.win_probability, 4),
            "collapse_probability": round(pred_alt.collapse_probability, 4),
        },
        "probability_divergence": {
            "win_probability_delta": round(win_diff, 4),
            "collapse_probability_delta": round(collapse_diff, 4),
            "recommendation": (
                "Alternative move significantly improves win probability!"
                if win_diff > 0.05
                else "Played move was optimal or equivalent."
            ),
        },
    }


@router.post("/analysis/elo-sim", summary="ELO-Segmented Human Move Simulation")
def simulate_elo_move(req: EloSimRequest) -> dict[str, Any]:
    """Predict candidate human moves & think times for a target ELO bracket."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string.")

    pos_feats = extract_position_features(board)
    from app.models.move import Move, MoveColor
    move_obj = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE if board.turn == chess.WHITE else MoveColor.BLACK,
        san="move",
        uci="e2e4",
        fen=req.fen,
        time_spent=3000,
        clock_after=int(req.time_remaining_sec * 1000),
    )
    time_feats = extract_time_features(move_obj, previous_moves_same_color=[])

    manager = EloSimulatorManager()
    result = manager.predict_for_elo(board, pos_feats, time_feats, req.target_elo_bucket)

    return {
        "elo_bucket": result.elo_bucket,
        "fen": result.fen,
        "engine_recommendation": result.engine_recommendation,
        "top_candidate_moves": [
            {
                "san": m.san,
                "uci": m.uci,
                "probability": m.probability,
                "expected_think_time_sec": m.expected_think_time_sec,
                "is_engine_top_choice": m.is_engine_top_choice,
            }
            for m in result.top_candidate_moves
        ],
    }


@router.get("/analysis/archetype/{username}", summary="Get Player K-Means Archetype Cluster")
def get_player_archetype(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Classify player into K-Means archetype cluster."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=500)
    if not games:
        raise HTTPException(status_code=404, detail=f"No games found for player '{username}'")

    profile = generate_personal_profile(username, games)
    classifier = PlayerArchetypeClassifier()
    res = classifier.classify_profile(profile)

    return {
        "username": username,
        "primary_archetype": res.primary_archetype,
        "secondary_archetype": res.secondary_archetype,
        "archetype_scores": res.archetype_scores,
        "description": res.description,
    }


@router.get("/analysis/similarity/{username}", summary="Get Similar Player Neighbors")
def get_similar_players(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Find nearest player neighbors using Cosine Similarity graph."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=500)
    if not games:
        raise HTTPException(status_code=404, detail=f"No games found for player '{username}'")

    profile = generate_personal_profile(username, games)
    engine = PlayerSimilarityEngine()
    matches = engine.find_similar_players(profile, top_n=3)

    return {
        "username": username,
        "similar_players": [
            {
                "username": m.username,
                "similarity_score_pct": m.similarity_score_pct,
                "shared_traits": m.shared_traits,
            }
            for m in matches
        ],
    }


@router.get("/analysis/patterns/{username}", summary="Get Cross-Game Recurring Patterns")
def get_recurring_patterns(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Detect recurring mistake patterns across a player's last N games."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=100)
    if not games:
        raise HTTPException(status_code=404, detail=f"No games found for player '{username}'")

    detector = CrossGamePatternDetector()
    patterns = detector.detect_patterns(games)

    return {
        "username": username,
        "total_games_scanned": len(games),
        "recurring_patterns": [
            {
                "pattern_name": p.pattern_name,
                "category": p.category,
                "frequency_count": p.frequency_count,
                "impact_severity": p.impact_severity,
                "recommendation": p.recommendation,
            }
            for p in patterns
        ],
    }


@router.get("/analysis/anomalies/{game_id}", summary="Get Game Anomaly Detection")
def get_game_anomalies(game_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Detect move anomalies (brilliancies, panic moves, overthinking) in a game."""
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    detector = AnomalyDetector()
    anomalies = detector.detect_game_anomalies(game)

    return {
        "game_id": game_id,
        "total_anomalies_found": len(anomalies),
        "anomalies": [
            {
                "move_number": a.move_number,
                "ply": a.ply,
                "color": a.color,
                "san": a.san,
                "anomaly_type": a.anomaly_type,
                "anomaly_score": a.anomaly_score,
                "description": a.description,
            }
            for a in anomalies
        ],
    }
