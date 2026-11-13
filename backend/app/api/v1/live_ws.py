"""
Real-Time WebSocket Live Game Spectating Endpoint.

Connects to Lichess live game WebSocket stream, extracts position and clock
features per move, executes fast XGBoost + SHAP inference, and broadcasts live
analysis frames in real-time with resilient auto-reconnect and heartbeat keepalive.
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

TERMINAL_STATUSES = {
    "mate", "resign", "outoftime", "timeout", "draw",
    "stalemate", "cheat", "aborted", "noStart", "unknownFinish"
}


@router.websocket("/ws/live/{game_id}")
async def stream_live_game(websocket: WebSocket, game_id: str) -> None:
    """
    Resilient WebSocket endpoint for real-time live game spectating.

    Connects to public Lichess stream API (https://lichess.org/api/stream/game/{game_id}),
    runs real-time position + clock feature extraction, XGBoost win/collapse prediction,
    and SHAP explainability narrative generation per move.
    Features ping/pong keepalive to prevent proxy timeouts and automatic reconnection.
    """
    await websocket.accept()
    clean_game_id = game_id.strip()[:8]
    logger.info("WebSocket client connected for live spectating game ID '%s'", clean_game_id)

    stop_event = asyncio.Event()

    async def heartbeat_sender() -> None:
        """Send periodic ping frames every 15s to keep WebSocket through Cloudflare/Render alive."""
        try:
            while not stop_event.is_set():
                await asyncio.sleep(15)
                if stop_event.is_set():
                    break
                await websocket.send_json({"type": "ping"})
        except Exception:
            stop_event.set()

    async def client_listener() -> None:
        """Listen for incoming messages from client to detect client-side disconnects or pongs."""
        try:
            while not stop_event.is_set():
                msg_text = await websocket.receive_text()
                try:
                    data = json.loads(msg_text)
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception:
                    pass
        except WebSocketDisconnect:
            stop_event.set()
        except Exception:
            stop_event.set()

    heartbeat_task = asyncio.create_task(heartbeat_sender())
    listener_task = asyncio.create_task(client_listener())

    try:
        board = chess.Board()
        ply = 0
        previous_clock: int | None = None
        prev_white_moves: list[Move] = []
        prev_black_moves: list[Move] = []
        white_player = "White"
        black_player = "Black"
        initial_clock_sec: int | None = None
        time_control_str: str | None = None
        game_is_terminal = False

        async with httpx.AsyncClient(timeout=None) as client:
            # Check export first to see if game exists and retrieve initial metadata
            try:
                export_url = f"https://lichess.org/game/export/{clean_game_id}?moves=true&clocks=true&evals=false"
                init_resp = await client.get(export_url, headers={"Accept": "application/json"}, timeout=8.0)
                if init_resp.status_code == 200:
                    init_data = init_resp.json()
                    players_info = init_data.get("players", {})
                    if "white" in players_info:
                        white_player = players_info["white"].get("user", {}).get("name") or players_info["white"].get("name") or white_player
                    if "black" in players_info:
                        black_player = players_info["black"].get("user", {}).get("name") or players_info["black"].get("name") or black_player
                    if "clock" in init_data:
                        c_init = init_data["clock"].get("initial")
                        c_inc = init_data["clock"].get("increment", 0)
                        if c_init is not None:
                            initial_clock_sec = int(c_init)
                            time_control_str = f"{c_init}+{c_inc}"
            except Exception as e:
                logger.warning("Could not pre-fetch Lichess metadata for %s: %s", clean_game_id, e)

            # Send initial frame at ply 0
            initial_frame = {
                "game_id": clean_game_id,
                "ply": 0,
                "move_number": 0,
                "color": "white",
                "uci": "",
                "san": "",
                "fen": board.fen(),
                "white_player": white_player,
                "black_player": black_player,
                "white_clock": initial_clock_sec,
                "black_clock": initial_clock_sec,
                "time_control": time_control_str,
                "initial_clock_seconds": initial_clock_sec,
                "win_probability": 0.5,
                "collapse_probability": 0.1,
                "black_collapse_probability": 0.1,
                "time_pressure_risk_multiplier": 1.0,
                "narrative_summary": "Spectating live game stream...",
            }
            await websocket.send_json(initial_frame)

            # Helper to sync and broadcast missing moves from export
            async def catch_up_from_export(export_data: dict[str, Any]) -> None:
                nonlocal ply, board, previous_clock, white_player, black_player
                all_sans = export_data.get("moves", "").split()
                if len(all_sans) > len(board.move_stack):
                    missing_sans = all_sans[len(board.move_stack):]
                    logger.info("Syncing %d missing moves for %s: %s", len(missing_sans), clean_game_id, missing_sans)
                    for m_san in missing_sans:
                        try:
                            chess_move = board.parse_san(m_san)
                            calculated_san = board.san(chess_move)
                            board.push(chess_move)
                        except Exception as parse_err:
                            logger.warning("Could not parse move '%s': %s", m_san, parse_err)
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
                            time_spent=1000,
                        )
                        pos_feats = extract_position_features(board)
                        prev_same = prev_white_moves if active_color == MoveColor.WHITE else prev_black_moves
                        time_feats = extract_time_features(
                            move_obj,
                            previous_moves_same_color=prev_same,
                            initial_clock_seconds=initial_clock_sec,
                        )
                        pred = predictor.predict(pos_feats, time_feats)
                        exp = explainer.explain(pos_feats, time_feats)

                        sync_frame = {
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
                            "time_control": time_control_str,
                            "initial_clock_seconds": initial_clock_sec,
                            "win_probability": round(pred.win_probability, 4),
                            "collapse_probability": round(pred.collapse_probability, 4),
                            "black_collapse_probability": round(pred.black_collapse_probability, 4),
                            "time_pressure_risk_multiplier": pred.time_pressure_risk_multiplier,
                            "narrative_summary": exp.narrative_summary,
                            "material_balance": pos_feats.material_balance,
                            "game_phase": pos_feats.game_phase,
                            "think_time_sec": time_feats.think_time,
                            "time_remaining_sec": time_feats.time_remaining,
                            "is_time_pressure_30s": time_feats.is_time_pressure_30s,
                        }
                        await websocket.send_json(sync_frame)

                        if active_color == MoveColor.WHITE:
                            prev_white_moves.append(move_obj)
                        else:
                            prev_black_moves.append(move_obj)

            # Outer resilient loop: streams live moves, reconnecting if Lichess stream hiccups mid-game
            while not game_is_terminal and not stop_event.is_set():
                stream_url = f"https://lichess.org/api/stream/game/{clean_game_id}"
                try:
                    async with client.stream("GET", stream_url) as response:
                        if response.status_code != 200:
                            logger.warning("Lichess stream status %d for %s", response.status_code, clean_game_id)
                            # Check export to see if game already ended or is unavailable
                            export_url = f"https://lichess.org/game/export/{clean_game_id}?moves=true&clocks=true&evals=false"
                            exp_resp = await client.get(export_url, headers={"Accept": "application/json"}, timeout=8.0)
                            if exp_resp.status_code == 200:
                                exp_data = exp_resp.json()
                                await catch_up_from_export(exp_data)
                                raw_status = exp_data.get("status", "completed")
                                if raw_status in TERMINAL_STATUSES or exp_data.get("winner") is not None:
                                    game_is_terminal = True
                                    winner = exp_data.get("winner")
                                    result_text = f"1-0 · {white_player} won" if winner == "white" else f"0-1 · {black_player} won" if winner == "black" else f"½-½ · Draw"
                                    await websocket.send_json({
                                        "game_id": clean_game_id,
                                        "game_over": True,
                                        "status": raw_status,
                                        "winner": winner,
                                        "result_text": result_text,
                                        "narrative_summary": f"Game Over — {result_text}",
                                    })
                                    break
                            await asyncio.sleep(2.0)
                            continue

                        async for line in response.aiter_lines():
                            if stop_event.is_set():
                                break
                            if not line.strip():
                                continue

                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            # Update clock & players metadata
                            if "clock" in data and isinstance(data["clock"], dict):
                                c_init = data["clock"].get("initial")
                                c_inc = data["clock"].get("increment", 0)
                                if c_init is not None:
                                    initial_clock_sec = int(c_init)
                                    time_control_str = f"{c_init}+{c_inc}"
                            elif initial_clock_sec is None and ("wc" in data or "bc" in data):
                                c_sec = data.get("wc") or data.get("bc")
                                if c_sec is not None:
                                    initial_clock_sec = int(c_sec)
                                    time_control_str = f"{initial_clock_sec}+0"

                            if "players" in data and isinstance(data["players"], dict):
                                w_user = data["players"].get("white", {})
                                if isinstance(w_user, dict):
                                    white_player = w_user.get("user", {}).get("name") or w_user.get("name") or white_player
                                b_user = data["players"].get("black", {})
                                if isinstance(b_user, dict):
                                    black_player = b_user.get("user", {}).get("name") or b_user.get("name") or black_player

                            new_uci = data.get("lm")
                            if not new_uci:
                                # Status check if block has terminal status
                                if data.get("status") in TERMINAL_STATUSES or data.get("winner") is not None:
                                    game_is_terminal = True
                                    winner = data.get("winner")
                                    result_text = f"1-0 · {white_player} won" if winner == "white" else f"0-1 · {black_player} won" if winner == "black" else f"½-½ · Draw"
                                    await websocket.send_json({
                                        "game_id": clean_game_id,
                                        "game_over": True,
                                        "status": data.get("status"),
                                        "winner": winner,
                                        "result_text": result_text,
                                        "narrative_summary": f"Game Over — {result_text}",
                                    })
                                    break
                                continue

                            # Parse and push move
                            try:
                                chess_move = chess.Move.from_uci(new_uci)
                                if chess_move in board.legal_moves:
                                    calculated_san = board.san(chess_move)
                                    board.push(chess_move)
                                else:
                                    # Board might be behind stream, attempt catch-up via export
                                    export_url = f"https://lichess.org/game/export/{clean_game_id}?moves=true&clocks=true&evals=false"
                                    sync_resp = await client.get(export_url, headers={"Accept": "application/json"}, timeout=5.0)
                                    if sync_resp.status_code == 200:
                                        await catch_up_from_export(sync_resp.json())
                                    continue
                            except Exception:
                                continue

                            ply += 1
                            move_number = (ply + 1) // 2
                            active_color = (
                                MoveColor.WHITE if board.turn == chess.BLACK else MoveColor.BLACK
                            )

                            clock_after = None
                            if "wc" in data and "bc" in data:
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

                            pos_feats = extract_position_features(board)
                            prev_same = (
                                prev_white_moves
                                if active_color == MoveColor.WHITE
                                else prev_black_moves
                            )
                            time_feats = extract_time_features(
                                move_obj,
                                previous_moves_same_color=prev_same,
                                initial_clock_seconds=initial_clock_sec,
                            )

                            pred = predictor.predict(pos_feats, time_feats)
                            exp = explainer.explain(pos_feats, time_feats)

                            frame = {
                                "game_id": clean_game_id,
                                "ply": ply,
                                "move_number": move_number,
                                "color": active_color.value,
                                "uci": new_uci,
                                "san": calculated_san,
                                "fen": board.fen(),
                                "white_player": white_player,
                                "black_player": black_player,
                                "white_clock": data.get("wc"),
                                "black_clock": data.get("bc"),
                                "time_control": time_control_str,
                                "initial_clock_seconds": initial_clock_sec,
                                "win_probability": round(pred.win_probability, 4),
                                "collapse_probability": round(pred.collapse_probability, 4),
                                "black_collapse_probability": round(pred.black_collapse_probability, 4),
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

                            previous_clock = clock_after

                except (httpx.TransportError, httpx.ReadTimeout, httpx.RemoteProtocolError) as net_err:
                    logger.info("Lichess stream transient network interruption for %s: %s", clean_game_id, net_err)
                except Exception as stream_err:
                    logger.warning("Stream loop error for %s: %s", clean_game_id, stream_err)

                if stop_event.is_set():
                    break

                # Stream ended or disconnected: check game status via export before terminating
                try:
                    export_url = f"https://lichess.org/game/export/{clean_game_id}?moves=true&clocks=true&evals=false"
                    export_resp = await client.get(export_url, headers={"Accept": "application/json"}, timeout=8.0)
                    if export_resp.status_code == 200:
                        export_data = export_resp.json()
                        await catch_up_from_export(export_data)

                        raw_status = export_data.get("status", "started")
                        winner = export_data.get("winner")

                        if raw_status in TERMINAL_STATUSES or winner is not None:
                            game_is_terminal = True
                            if winner == "white":
                                result_text = f"1-0 · {white_player} won ({raw_status})"
                            elif winner == "black":
                                result_text = f"0-1 · {black_player} won ({raw_status})"
                            else:
                                result_text = f"½-½ · Draw ({raw_status})"

                            await websocket.send_json({
                                "game_id": clean_game_id,
                                "game_over": True,
                                "status": raw_status,
                                "winner": winner,
                                "result_text": result_text,
                                "narrative_summary": f"Game Over — {result_text}",
                            })
                            break
                        else:
                            # Game is still active! Wait briefly and reconnect stream
                            logger.info("Game %s is still '%s'. Reconnecting live stream...", clean_game_id, raw_status)
                            await asyncio.sleep(1.5)
                            continue
                except Exception as exp_err:
                    logger.warning("Error checking terminal state for %s: %s", clean_game_id, exp_err)
                    await asyncio.sleep(2.0)

            # Keep socket alive and listening if game reached terminal state
            while not stop_event.is_set():
                await asyncio.sleep(5)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for game ID '%s'", clean_game_id)
    except Exception as exc:
        logger.exception("Error in live WebSocket handler for game ID '%s': %s", clean_game_id, exc)
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        listener_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
