"""
Game retrieval endpoints.
"""

from __future__ import annotations

from typing import Any
import chess
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.repositories.game_repository import GameRepository

router = APIRouter()


@router.get("/games", summary="List stored games")
def list_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    username: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List games with optional pagination and player username filter."""
    repo = GameRepository(db)
    games = repo.list_games(skip=skip, limit=limit, username=username)

    return [
        {
            "id": g.id,
            "site": g.site,
            "event": g.event,
            "date": str(g.game_date) if g.game_date else None,
            "white_player": g.white_player.display_name if g.white_player else None,
            "black_player": g.black_player.display_name if g.black_player else None,
            "white_elo": g.white_elo,
            "black_elo": g.black_elo,
            "result": g.result.value,
            "eco": g.eco,
            "time_control": g.time_control,
            "move_count": len(g.moves),
        }
        for g in games
    ]


@router.get("/games/{game_id}", summary="Get game details")
def get_game(
    game_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve complete game details by ID."""
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)

    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    return {
        "id": game.id,
        "site": game.site,
        "event": game.event,
        "date": str(game.game_date) if game.game_date else None,
        "white_player": game.white_player.display_name if game.white_player else None,
        "black_player": game.black_player.display_name if game.black_player else None,
        "white_elo": game.white_elo,
        "black_elo": game.black_elo,
        "result": game.result.value,
        "eco": game.eco,
        "opening": game.opening,
        "time_control": game.time_control,
        "pgn_hash": game.pgn_hash,
        "move_count": len(game.moves),
    }


@router.get("/games/{game_id}/timeline", summary="Get game move timeline")
def get_game_timeline(
    game_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Get detailed move-by-move timeline including position and time feature metrics.
    """
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)

    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    timeline: list[dict[str, Any]] = []

    prev_white: list[Any] = []
    prev_black: list[Any] = []

    for move in game.moves:
        board = chess.Board(move.fen)
        pos_feats = extract_position_features(board)

        prev_same = prev_white if move.color.value == "white" else prev_black
        time_feats = extract_time_features(
            move,
            previous_moves_same_color=prev_same,
        )

        timeline.append(
            {
                "move_number": move.move_number,
                "ply": move.ply,
                "color": move.color.value,
                "san": move.san,
                "uci": move.uci,
                "fen": move.fen,
                # Position metrics
                "material_balance": pos_feats.material_balance,
                "game_phase": pos_feats.game_phase,
                "white_mobility": pos_feats.white_mobility,
                "black_mobility": pos_feats.black_mobility,
                "white_pawn_shield": pos_feats.white_pawn_shield,
                "black_pawn_shield": pos_feats.black_pawn_shield,
                # Time metrics
                "think_time_sec": time_feats.think_time,
                "time_remaining_sec": time_feats.time_remaining,
                "is_time_pressure_120s": time_feats.is_time_pressure_120s,
                "is_time_pressure_60s": time_feats.is_time_pressure_60s,
                "is_time_pressure_30s": time_feats.is_time_pressure_30s,
                "time_usage_ratio": time_feats.time_usage_ratio,
                "time_control": time_feats.time_control,
            }
        )

        if move.color.value == "white":
            prev_white.append(move)
        else:
            prev_black.append(move)

    return timeline


@router.get("/players", summary="List stored players")
def list_players(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List players stored in the database with optional pagination."""
    from app.repositories.player_repository import PlayerRepository

    repo = PlayerRepository(db)
    players = repo.list_players(skip=skip, limit=limit)

    return [
        {
            "id": p.id,
            "name": p.name,
            "normalized_name": p.normalized_name,
            "fide_id": p.fide_id,
            "title": p.title,
            "country": p.country,
        }
        for p in players
    ]


@router.get("/players/{username}", summary="Get player details")
def get_player(username: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get single player profile by username with total games count."""
    from app.repositories.player_repository import PlayerRepository
    from app.repositories.game_repository import GameRepository

    player_repo = PlayerRepository(db)
    player = player_repo.get_by_name(username)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player '{username}' not found")

    game_repo = GameRepository(db)
    games = game_repo.list_games(username=username, limit=1000)

    return {
        "id": player.id,
        "name": player.name,
        "normalized_name": player.normalized_name,
        "fide_id": player.fide_id,
        "title": player.title,
        "country": player.country,
        "total_games_stored": len(games),
    }


@router.delete("/games/{game_id}", summary="Delete game by ID")
def delete_game(game_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete a stored game and its associated moves and evaluations by ID."""
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    db.delete(game)
    db.commit()

    return {"message": f"Successfully deleted game ID {game_id}"}
