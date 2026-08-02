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
    eval_cp: float | None = None


class WhatIfRequest(BaseModel):
    fen: str
    played_move_uci: str
    alternative_move_uci: str
    think_time_sec: float = 5.0
    time_remaining_sec: float = 120.0
    initial_clock_seconds: int = 300
    eval_cp: float | None = None
    perspective: str = "white"  # "white" or "black"


class EloSimRequest(BaseModel):
    fen: str
    target_elo_bucket: str = "1600-1800"
    time_remaining_sec: float = 120.0
    best_move_uci: str | None = None


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
                "accuracy_pct": b.accuracy_pct,
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
        "phase_accuracy": {
            "opening_accuracy_pct": round(profile.phase_accuracy.opening_accuracy_pct, 1),
            "middlegame_accuracy_pct": round(profile.phase_accuracy.middlegame_accuracy_pct, 1),
            "endgame_accuracy_pct": round(profile.phase_accuracy.endgame_accuracy_pct, 1),
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
    pred = predictor.predict(pos_feats, time_feats, eval_cp=req.eval_cp)

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

    # --- Parse PLAYED move ---
    played_move = None
    try:
        played_move = board.parse_uci(req.played_move_uci)
    except Exception:
        try:
            played_move = board.parse_san(req.played_move_uci)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid played move '{req.played_move_uci}'")

    if played_move not in board.legal_moves:
        raise HTTPException(status_code=400, detail=f"Played move '{req.played_move_uci}' is not legal in this position.")

    played_san = board.san(played_move)

    # --- Parse ALTERNATIVE move (supports SAN like 'Ke2', 'g4' or UCI like 'e1e2', 'g3g4') ---
    alt_move = None
    # Try SAN first (most natural for users)
    try:
        alt_move = board.parse_san(req.alternative_move_uci)
    except Exception:
        pass
    # Then try UCI
    if alt_move is None:
        try:
            alt_move = board.parse_uci(req.alternative_move_uci)
        except Exception:
            pass

    if alt_move is None or alt_move not in board.legal_moves:
        # Build a helpful error listing some legal moves
        legal_sans = [board.san(m) for m in list(board.legal_moves)[:8]]
        raise HTTPException(
            status_code=400,
            detail=f"'{req.alternative_move_uci}' is not a legal move. Try SAN (e.g. {', '.join(legal_sans[:4])}) or UCI (e.g. {list(board.legal_moves)[0].uci()})."
        )

    alt_san = board.san(alt_move)

    # --- Evaluate BOTH resulting positions with Stockfish ---
    try:
        with StockfishEngine(STOCKFISH_PATH) as engine:
            evaluator = Evaluator(engine)
            
            # Played move: evaluate the resulting position
            board_played = board.copy()
            board_played.push(played_move)
            played_eval_cp = req.eval_cp  # fallback to cached eval from timeline
            
            try:
                ev = evaluator.evaluate(board_played, move_number=1, depth=16)
                raw = ev.cp_score
                if raw is None and ev.mate_score is not None:
                    raw = 200000 if ev.mate_score > 0 else -200000
                if raw is not None:
                    # score.relative is from the NEXT side-to-move's perspective.
                    # Normalize to White's perspective (positive = good for White):
                    played_eval_cp = -raw if board_played.turn == chess.BLACK else raw
            except Exception:
                pass

            # Alternative move: if same as played, clone results; otherwise evaluate fresh
            if alt_move == played_move:
                board_alt = board_played
                alt_eval_cp = played_eval_cp
            else:
                board_alt = board.copy()
                board_alt.push(alt_move)
                alt_eval_cp = None
                
                try:
                    ev = evaluator.evaluate(board_alt, move_number=1, depth=16)
                    raw = ev.cp_score
                    if raw is None and ev.mate_score is not None:
                        raw = 200000 if ev.mate_score > 0 else -200000
                    if raw is not None:
                        alt_eval_cp = -raw if board_alt.turn == chess.BLACK else raw
                except Exception:
                    pass
    except Exception:
        # Fallback if engine fails to start
        played_eval_cp = req.eval_cp
        alt_eval_cp = None

    if alt_move != played_move and alt_eval_cp is None:
        raise HTTPException(
            status_code=400,
            detail="Stockfish engine failed to evaluate the alternative variation. Ensure Stockfish is installed and STOCKFISH_PATH is set correctly in backend/.env."
        )

    # --- Run predictor for both ---
    predictor = WinCollapsePredictor()

    from app.models.move import Move, MoveColor
    color = MoveColor.WHITE if board.turn == chess.WHITE else MoveColor.BLACK

    pos_played = extract_position_features(board_played)
    move_played_obj = Move(
        move_number=1, ply=1, color=color, san=played_san, uci=played_move.uci(),
        fen=board_played.fen(), time_spent=int(req.think_time_sec * 1000),
        clock_after=int(req.time_remaining_sec * 1000),
    )
    time_played = extract_time_features(move_played_obj, previous_moves_same_color=[])
    pred_played = predictor.predict(pos_played, time_played, eval_cp=played_eval_cp)

    pos_alt = extract_position_features(board_alt)
    move_alt_obj = Move(
        move_number=1, ply=1, color=color, san=alt_san, uci=alt_move.uci(),
        fen=board_alt.fen(), time_spent=int(req.think_time_sec * 1000),
        clock_after=int(req.time_remaining_sec * 1000),
    )
    time_alt = extract_time_features(move_alt_obj, previous_moves_same_color=[])
    pred_alt = predictor.predict(pos_alt, time_alt, eval_cp=alt_eval_cp)

    win_diff = pred_alt.win_probability - pred_played.win_probability
    collapse_diff = pred_alt.collapse_probability - pred_played.collapse_probability
    
    # Evaluate delta from the requested perspective
    player_win_diff = win_diff if req.perspective == "white" else -win_diff

    # --- Build rich recommendation ---
    played_wp = round(pred_played.win_probability * 100, 1)
    alt_wp = round(pred_alt.win_probability * 100, 1)
    played_eval_str = f"{played_eval_cp / 100:+.2f}" if played_eval_cp is not None else "N/A"
    alt_eval_str = f"{alt_eval_cp / 100:+.2f}" if alt_eval_cp is not None else "N/A"
    
    persp_str = req.perspective.capitalize()

    if player_win_diff > 0.08:
        rec = f"🟢 {alt_san} is significantly better for {persp_str} than {played_san}! ({alt_eval_str} vs {played_eval_str})"
    elif player_win_diff > 0.03:
        rec = f"🟡 {alt_san} is slightly better for {persp_str} than {played_san} ({alt_eval_str} vs {played_eval_str})"
    elif player_win_diff > -0.03:
        rec = f"⚖️ Both moves are roughly equal ({alt_san}: {alt_eval_str}, {played_san}: {played_eval_str})"
    elif player_win_diff > -0.08:
        rec = f"🟡 {alt_san} is slightly worse for {persp_str} than {played_san} ({alt_eval_str} vs {played_eval_str})"
    else:
        rec = f"🔴 {alt_san} is significantly worse for {persp_str} than {played_san} ({alt_eval_str} vs {played_eval_str})"

    return {
        "played_move": {
            "uci": played_move.uci(),
            "san": played_san,
            "eval_cp": played_eval_cp,
            "win_probability": round(pred_played.win_probability, 4),
            "collapse_probability": round(pred_played.collapse_probability, 4),
        },
        "alternative_move": {
            "uci": alt_move.uci(),
            "san": alt_san,
            "eval_cp": alt_eval_cp,
            "win_probability": round(pred_alt.win_probability, 4),
            "collapse_probability": round(pred_alt.collapse_probability, 4),
        },
        "probability_divergence": {
            "win_probability_delta": round(player_win_diff, 4),
            "collapse_probability_delta": round(collapse_diff, 4),
            "recommendation": rec,
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
    result = manager.predict_for_elo(board, pos_feats, time_feats, req.target_elo_bucket, best_move_uci=req.best_move_uci)

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


@router.get("/analysis/openings/{username}", summary="Get Opening Health Report")
def get_opening_health(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Analyze player's ECO opening performance, win rates, and middlegame evaluation deterioration."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=100)

    eco_stats: dict[str, dict[str, Any]] = {}

    for g in games:
        eco = g.eco or "A00"
        opening_name = g.opening or "Standard Opening"
        if eco not in eco_stats:
            eco_stats[eco] = {
                "eco": eco,
                "name": opening_name,
                "total_played": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
            }

        is_white = g.white_player and g.white_player.display_name.lower() == username.lower()
        result_val = g.result.value if hasattr(g.result, "value") else str(g.result)

        eco_stats[eco]["total_played"] += 1
        if (is_white and result_val == "1-0") or (not is_white and result_val == "0-1"):
            eco_stats[eco]["wins"] += 1
        elif result_val == "1/2-1/2":
            eco_stats[eco]["draws"] += 1
        else:
            eco_stats[eco]["losses"] += 1

    report = []
    for eco, data in eco_stats.items():
        win_rate = (data["wins"] / max(1, data["total_played"])) * 100.0
        recommendation = (
            "Strong opening repertoire choice!" if win_rate >= 55.0
            else "Middlegame positions deteriorate by move 20 — consider refining lines." if win_rate < 40.0
            else "Solid performance."
        )
        report.append({
            "eco": eco,
            "opening_name": data["name"],
            "total_played": data["total_played"],
            "win_rate_pct": round(win_rate, 1),
            "wins": data["wins"],
            "losses": data["losses"],
            "draws": data["draws"],
            "recommendation": recommendation,
        })

    report.sort(key=lambda r: r["total_played"], reverse=True)

    return {
        "username": username,
        "total_games_analyzed": len(games),
        "openings": report[:6],
    }


@router.get("/analysis/brilliances/{username}", summary="Get Brilliancy Hall of Fame")
def get_brilliancy_hall_of_fame(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve top 5 statistically extraordinary brilliant moves for a player."""
    repo = GameRepository(db)
    games = repo.list_games(username=username, limit=50)

    detector = AnomalyDetector()
    all_brilliances = []

    for game in games:
        anomalies = detector.detect_game_anomalies(game)
        for a in anomalies:
            if a.anomaly_type == "brilliancy":
                all_brilliances.append({
                    "game_id": game.id,
                    "white_player": game.white_player.display_name if game.white_player else "White",
                    "black_player": game.black_player.display_name if game.black_player else "Black",
                    "move_number": a.move_number,
                    "san": a.san,
                    "anomaly_score": a.anomaly_score,
                    "description": a.description,
                })

    all_brilliances.sort(key=lambda b: b["anomaly_score"], reverse=True)

    return {
        "username": username,
        "total_brilliances_found": len(all_brilliances),
        "top_brilliances": all_brilliances[:5],
    }


@router.get("/analysis/compare/{username1}/{username2}", summary="Head-to-Head Player Comparison")
def compare_players(username1: str, username2: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Compare two player fingerprints side-by-side."""
    repo = GameRepository(db)
    games1 = repo.list_games(username=username1, limit=50)
    games2 = repo.list_games(username=username2, limit=50)

    profile1 = generate_personal_profile(username1, games1)
    profile2 = generate_personal_profile(username2, games2)

    archetype_engine = PlayerArchetypeClassifier()
    arch1 = archetype_engine.classify_archetype(profile1)
    arch2 = archetype_engine.classify_archetype(profile2)

    p1_tilt = profile1.tilt_signature.tilt_speedup_percentage
    p2_tilt = profile2.tilt_signature.tilt_speedup_percentage

    collapse_first = (
        username1 if p1_tilt > p2_tilt
        else username2 if p2_tilt > p1_tilt
        else "Equal pressure resilience"
    )

    return {
        "player1": {
            "username": username1,
            "archetype": arch1.primary_archetype,
            "normal_think_pace_sec": profile1.tilt_signature.normal_avg_think_time,
            "post_blunder_pace_sec": profile1.tilt_signature.post_material_loss_think_time,
            "tilt_speedup_pct": p1_tilt,
            "panic_move_count": profile1.panic_move_count,
            "overthink_move_count": profile1.overthink_move_count,
        },
        "player2": {
            "username": username2,
            "archetype": arch2.primary_archetype,
            "normal_think_pace_sec": profile2.tilt_signature.normal_avg_think_time,
            "post_blunder_pace_sec": profile2.tilt_signature.post_material_loss_think_time,
            "tilt_speedup_pct": p2_tilt,
            "panic_move_count": profile2.panic_move_count,
            "overthink_move_count": profile2.overthink_move_count,
        },
        "head_to_head_summary": {
            "tilt_vulnerability_winner": collapse_first,
            "comparison_verdict": f"{username1} ({arch1.primary_archetype}) vs {username2} ({arch2.primary_archetype}).",
        },
    }
