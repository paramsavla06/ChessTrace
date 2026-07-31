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


@router.websocket("/ws/live/{game_id}")
async def stream_live_game(websocket: WebSocket, game_id: str) -> None:
    """
    WebSocket endpoint for real-time live game spectating.

    Connects to public Lichess stream API (https://lichess.org/api/stream/game/{game_id}),
    runs real-time position + clock feature extraction, XGBoost win/collapse prediction,
    and SHAP explainability narrative generation per move.
    """
    await websocket.accept()
    logger.info("WebSocket client connected for live spectating game ID '%s'", game_id)

    predictor = WinCollapsePredictor()
    explainer = ShapExplainer(predictor)

    try:
        # Stream live PGN/NDJSON from Lichess API
        url = f"https://lichess.org/api/stream/game/{game_id}"

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

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Handle move event in Lichess stream
                    moves_str = data.get("state", {}).get("moves", "") or data.get("moves", "")
                    if not moves_str:
                        continue

                    move_list = moves_str.split()
                    if len(move_list) <= ply:
                        continue

                    # Process new move
                    new_uci = move_list[ply]
                    try:
                        chess_move = chess.Move.from_uci(new_uci)
                        if chess_move not in board.legal_moves:
                            board = chess.Board()
                            for m in move_list[: ply + 1]:
                                board.push_uci(m)
                        else:
                            board.push(chess_move)
                    except ValueError:
                        continue

                    ply += 1
                    move_number = (ply + 1) // 2
                    active_color = (
                        MoveColor.WHITE if board.turn == chess.BLACK else MoveColor.BLACK
                    )

                    # Extract clock info from stream data if present
                    clock_after = None
                    if "wtime" in data or "btime" in data:
                        clock_after = (
                            data.get("wtime")
                            if active_color == MoveColor.WHITE
                            else data.get("btime")
                        )

                    time_spent = None
                    if previous_clock is not None and clock_after is not None:
                        time_spent = max(0, previous_clock - clock_after)

                    move_obj = Move(
                        move_number=move_number,
                        ply=ply,
                        color=active_color,
                        san=board.san(chess_move) if chess_move in board.legal_moves else new_uci,
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
                        "game_id": game_id,
                        "ply": ply,
                        "move_number": move_number,
                        "color": active_color.value,
                        "uci": new_uci,
                        "fen": board.fen(),
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

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for game ID '%s'", game_id)
    except Exception as exc:
        logger.exception("Error in live WebSocket stream for game ID '%s': %s", game_id, exc)
        try:
            await websocket.send_json({"error": f"Live stream error: {exc}"})
            await websocket.close()
        except Exception:
            pass
