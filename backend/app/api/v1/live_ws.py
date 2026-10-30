"""
Real-Time WebSocket Live Game Spectating Endpoint.

Connects to Lichess live game WebSocket stream, extracts position and clock
features per move, executes fast XGBoost + SHAP inference, and broadcasts live
analysis frames in real-time.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from typing import Any

import chess
import chess.pgn
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.ml.collapse_model import WinCollapsePredictor
from app.ml.explainer import ShapExplainer
from app.models.move import Move, MoveColor
from app.parsers.move_parser import _extract_clock

logger = logging.getLogger(__name__)

router = APIRouter()


# Instantiate ML models globally so they don't block the event loop on every connection
predictor = WinCollapsePredictor()
explainer = ShapExplainer(predictor)

@router.websocket("/ws/live/{game_id}")
async def stream_live_game(websocket: WebSocket, game_id: str) -> None:
    """
    WebSocket endpoint for real-time live game spectating.

    Connects to public Lichess stream API (https://lichess.org/api/stream/game/{game_id}),
    runs real-time position + clock feature extraction, XGBoost win/collapse prediction,
    and SHAP explainability narrative generation per move.
    """
    await websocket.accept()
    clean_game_id = game_id.strip()[:8]
    logger.info("WebSocket client connected for live spectating game ID '%s'", clean_game_id)

    try:
        # Stream live PGN/NDJSON from Lichess API
        url = f"https://lichess.org/api/stream/game/{clean_game_id}"

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    await websocket.send_json(
                        {
                            "error": f"Lichess game stream returned status {response.status_code}. Verify game ID."
                        }
                    )
                    await websocket.close()
                    return

                board = chess.Board()
                ply = 0
                previous_clock: int | None = None
                prev_white_moves: list[Move] = []
                prev_black_moves: list[Move] = []
                white_player = "White"
                black_player = "Black"

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Extract player names if metadata is present in this block
                    if "players" in data:
                        players_data = data.get("players", {})
                        if isinstance(players_data, dict):
                            w_user = players_data.get("white", {})
                            if isinstance(w_user, dict):
                                white_player = w_user.get("user", {}).get("name") or w_user.get("name") or white_player
                            b_user = players_data.get("black", {})
                            if isinstance(b_user, dict):
                                black_player = b_user.get("user", {}).get("name") or b_user.get("name") or black_player

                    # Send initial frame before first move if fen is present
                    new_uci = data.get("lm")
                    if ply == 0 and not new_uci and "fen" in data:
                        initial_frame = {
                            "game_id": clean_game_id,
                            "ply": 0,
                            "move_number": 0,
                            "color": "white",
                            "uci": "",
                            "fen": data.get("fen", board.fen()),
                            "white_player": white_player,
                            "black_player": black_player,
                            "white_clock": data.get("wc"),
                            "black_clock": data.get("bc"),
                            "win_probability": 0.5,
                            "collapse_probability": 0.1,
                            "time_pressure_risk_multiplier": 1.0,
                            "narrative_summary": "Spectating live game stream...",
                        }
                        await websocket.send_json(initial_frame)
                        continue

                    if not new_uci:
                        continue
                        
                    try:
                        chess_move = chess.Move.from_uci(new_uci)
                        if chess_move in board.legal_moves:
                            # Calculate SAN BEFORE pushing to the board
                            calculated_san = board.san(chess_move)
                            board.push(chess_move)
                        else:
                            logger.error("Illegal move received from stream: %s", new_uci)
                            continue
                    except ValueError:
                        continue

                    ply += 1
                    move_number = (ply + 1) // 2
                    active_color = (
                        MoveColor.WHITE if board.turn == chess.BLACK else MoveColor.BLACK
                    )

                    # Extract clock info from stream data
                    clock_after = None
                    if "wc" in data and "bc" in data:
                        # Lichess spectator stream sends clock in seconds, we need milliseconds for compatibility
                        clock_after = (
                            int(data.get("wc") * 1000)
                            if active_color == MoveColor.WHITE
                            else int(data.get("bc") * 1000)
                        )

                    time_spent = None
                    if previous_clock is not None and clock_after is not None:
                        time_spent = max(0, previous_clock - clock_after)

                    move_obj = Move(
                        move_number=move_number,
                        ply=ply,
                        color=active_color,
                        san=calculated_san,
                        uci=new_uci,
                        fen=board.fen(),
                        clock_before=previous_clock,
                        clock_after=clock_after,
                        time_spent=time_spent,
                    )

                    # Features & ML inference
                    pos_feats = extract_position_features(board)
                    prev_same = (
                        prev_white_moves
                        if active_color == MoveColor.WHITE
                        else prev_black_moves
                    )
                    time_feats = extract_time_features(
                        move_obj,
                        previous_moves_same_color=prev_same,
                    )

                    pred = predictor.predict(pos_feats, time_feats)
                    exp = explainer.explain(pos_feats, time_feats)

                    frame = {
                        "game_id": clean_game_id,
                        "ply": ply,
                        "move_number": move_number,
                        "color": active_color.value,
                        "uci": new_uci,
                        "fen": board.fen(),
                        "white_player": white_player,
                        "black_player": black_player,
                        "white_clock": data.get("wc"),
                        "black_clock": data.get("bc"),
                        # ML Predictions
                        "win_probability": round(pred.win_probability, 4),
                        "collapse_probability": round(pred.collapse_probability, 4),
                        "time_pressure_risk_multiplier": pred.time_pressure_risk_multiplier,
                        # SHAP Explainability
                        "narrative_summary": exp.narrative_summary,
                        # Position & Clock Metrics
                        "material_balance": pos_feats.material_balance,
                        "game_phase": pos_feats.game_phase,
                        "think_time_sec": time_feats.think_time,
                        "time_remaining_sec": time_feats.time_remaining,
                        "is_time_pressure_30s": time_feats.is_time_pressure_30s,
                    }

                    await websocket.send_json(frame)

                    if active_color == MoveColor.WHITE:
                        prev_white_moves.append(move_obj)
                    else:
                        prev_black_moves.append(move_obj)

                    previous_clock = clock_after

                # Game stream finished (game concluded or completed)
                logger.info("Live stream ended for game ID '%s'. Reconciling final moves...", clean_game_id)
                try:
                    export_url = f"https://lichess.org/game/export/{clean_game_id}?moves=true&clocks=true&evals=false"
                    export_resp = await client.get(export_url, headers={"Accept": "application/json"}, timeout=8.0)
                    if export_resp.status_code == 200:
                        export_data = export_resp.json()
                        all_sans = export_data.get("moves", "").split()
                        
                        # Catch up any trailing moves missed by delayed spectator stream
                        if len(all_sans) > len(board.move_stack):
                            missing_sans = all_sans[len(board.move_stack):]
                            logger.info("Catching up %d missing final moves: %s", len(missing_sans), missing_sans)
                            
                            for m_san in missing_sans:
                                try:
                                    chess_move = board.parse_san(m_san)
                                    calculated_san = board.san(chess_move)
                                    board.push(chess_move)
                                except Exception as parse_err:
                                    logger.warning("Could not parse missing move %s: %s", m_san, parse_err)
                                    break
                                    
                                ply += 1
                                move_number = (ply + 1) // 2
                                active_color = MoveColor.WHITE if board.turn == chess.BLACK else MoveColor.BLACK
                                
                                move_obj = Move(
                                    move_number=move_number,
                                    ply=ply,
                                    color=active_color,
                                    san=calculated_san,
                                    uci=chess_move.uci(),
                                    fen=board.fen(),
                                    clock_before=previous_clock,
                                    clock_after=previous_clock,
                                    time_spent=1,
                                )
                                
                                pos_feats = extract_position_features(board)
                                prev_same = prev_white_moves if active_color == MoveColor.WHITE else prev_black_moves
                                time_feats = extract_time_features(move_obj, previous_moves_same_color=prev_same)
                                pred = predictor.predict(pos_feats, time_feats)
                                exp = explainer.explain(pos_feats, time_feats)
                                
                                frame = {
                                    "game_id": clean_game_id,
                                    "ply": ply,
                                    "move_number": move_number,
                                    "color": active_color.value,
                                    "uci": chess_move.uci(),
                                    "san": calculated_san,
                                    "fen": board.fen(),
                                    "white_player": white_player,
                                    "black_player": black_player,
                                    "white_clock": previous_clock // 1000 if previous_clock else None,
                                    "black_clock": previous_clock // 1000 if previous_clock else None,
                                    "win_probability": round(pred.win_probability, 4),
                                    "collapse_probability": round(pred.collapse_probability, 4),
                                    "time_pressure_risk_multiplier": pred.time_pressure_risk_multiplier,
                                    "narrative_summary": exp.narrative_summary,
                                    "material_balance": pos_feats.material_balance,
                                    "game_phase": pos_feats.game_phase,
                                    "think_time_sec": time_feats.think_time,
                                    "time_remaining_sec": time_feats.time_remaining,
                                    "is_time_pressure_30s": time_feats.is_time_pressure_30s,
                                }
                                await websocket.send_json(frame)
                                
                                if active_color == MoveColor.WHITE:
                                    prev_white_moves.append(move_obj)
                                else:
                                    prev_black_moves.append(move_obj)

                        # Send terminal game-over notification
                        raw_status = export_data.get("status", "completed")
                        winner = export_data.get("winner")
                        if winner == "white":
                            result_text = f"1-0 · {white_player} won ({raw_status})"
                        elif winner == "black":
                            result_text = f"0-1 · {black_player} won ({raw_status})"
                        else:
                            result_text = f"½-½ · Draw ({raw_status})"

                        await websocket.send_json({
                            "game_id": clean_game_id,
                            "game_over": True,
                            "status": "completed",
                            "winner": winner,
                            "result_text": result_text,
                            "narrative_summary": f"Game Over — {result_text}",
                        })
                except Exception as final_err:
                    logger.warning("Could not reconcile final moves: %s", final_err)
                    await websocket.send_json({
                        "game_id": clean_game_id,
                        "game_over": True,
                        "status": "completed",
                        "narrative_summary": "Game completed.",
                    })

                while True:
                    await asyncio.sleep(60)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for game ID '%s'", game_id)
    except Exception as exc:
        logger.exception("Error in live WebSocket stream for game ID '%s': %s", game_id, exc)
        try:
            await websocket.send_json({"error": f"Live stream error: {exc}"})
            await websocket.close()
        except Exception:
            pass
