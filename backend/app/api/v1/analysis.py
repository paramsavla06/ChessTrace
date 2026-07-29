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
from app.ml.collapse_model import WinCollapsePredictor
from app.ml.explainer import ShapExplainer
from app.ml.personal_profile import generate_personal_profile
from app.repositories.game_repository import GameRepository
from app.services.analysis_services import AnalysisService

router = APIRouter()


class PredictRequest(BaseModel):
    fen: str
    think_time_sec: float = 5.0
    time_remaining_sec: float = 120.0
    initial_clock_seconds: int = 300


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

    # Mock move object for time feature extraction
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
