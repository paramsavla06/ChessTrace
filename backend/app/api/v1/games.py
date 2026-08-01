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
    
    from sqlalchemy import func
    from app.models.move import Move
    game_ids = [g.id for g in games]
    move_counts = dict(
        db.query(Move.game_id, func.count(Move.id))
        .filter(Move.game_id.in_(game_ids))
        .group_by(Move.game_id)
        .all()
    ) if game_ids else {}

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
            "move_count": move_counts.get(g.id, 0),
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
    Get detailed move-by-move timeline including Stockfish evaluation, position & time feature metrics.
    """
    repo = GameRepository(db)
    game = repo.get_by_id(game_id)

    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    timeline: list[dict[str, Any]] = []
    prev_white: list[Any] = []
    prev_black: list[Any] = []

    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    for idx, move in enumerate(game.moves):
        # Position BEFORE this move was played
        prev_fen = game.moves[idx - 1].fen if idx > 0 else start_fen
        prev_board = chess.Board(prev_fen)
        pos_feats = extract_position_features(prev_board)

        prev_same = prev_white if move.color.value == "white" else prev_black
        time_feats = extract_time_features(
            move,
            previous_moves_same_color=prev_same,
        )

        # Compute eval for PLAYED move and BEST move from DB-cached evaluations
        # to get the accuracy delta — same as Chess.com approach
        best_eval_cp = None
        played_eval_cp = None
        best_move_uci = None
        best_move_san = None
        eval_cp = None
        move_classification = "good"
        classification_label = ""
        best_move_label = ""

        if move.evaluations:
            ev_db = move.evaluations[0]
            eval_cp = ev_db.score_cp
            best_move_uci = ev_db.best_move

            # --- Compute played_eval_cp from THIS move's DB eval ---
            # DB stores score relative to side-to-move AFTER this move was played.
            # Normalize to White's perspective:
            if ev_db.score_cp is not None:
                after_board = chess.Board(move.fen)
                played_eval_cp = ev_db.score_cp if after_board.turn == chess.WHITE else -ev_db.score_cp
            elif ev_db.mate is not None:
                played_eval_cp = 200000 if ev_db.mate > 0 else -200000

            # --- Compute best_eval_cp from PREVIOUS move's DB eval ---
            # The position BEFORE this move = position AFTER the previous move.
            # The previous move's stored eval IS the eval of that position.
            if idx > 0:
                prev_move = game.moves[idx - 1]
                if prev_move.evaluations:
                    prev_ev = prev_move.evaluations[0]
                    if prev_ev.score_cp is not None:
                        # prev_ev.score_cp is relative to side-to-move after prev move
                        # side-to-move after prev move = the current mover
                        # Normalize to White's perspective:
                        prev_after_board = chess.Board(prev_move.fen)
                        best_eval_cp = prev_ev.score_cp if prev_after_board.turn == chess.WHITE else -prev_ev.score_cp
                    elif prev_ev.mate is not None:
                        best_eval_cp = 200000 if prev_ev.mate > 0 else -200000
            else:
                # First move of the game — starting position eval is ~0
                best_eval_cp = 0

        # Resolve best_move_san from prev_board
        if best_move_uci:
            try:
                bm_obj = chess.Move.from_uci(best_move_uci)
                best_move_san = prev_board.san(bm_obj)
            except Exception:
                best_move_san = best_move_uci

        # eval_cp = the White-normalized eval of the played position
        if played_eval_cp is not None:
            eval_cp = played_eval_cp
        elif eval_cp is not None and move.color.value == "black":
            eval_cp = -eval_cp  # normalize existing db score to White-relative

        # Calculate eval score & move classification using Chess.com official thresholds
        # Chess.com uses win-probability (Expected Points) delta — approximated via centipawn sigmoid
        # Centipawn delta thresholds (from Chess.com public docs):
        #   Excellent: 0–20cp, Good: 20–50cp, Inaccuracy: 50–100cp,
        #   Mistake: 100–200cp, Blunder: >200cp
        # Special categories:
        #   Book: opening move (move_number <= 10) matching engine top
        #   Great(!): move that rescues a losing position (best_eval ≤ -100cp → played_eval ≥ -30cp)
        #   Brilliant(!!): sound piece sacrifice that IS the engine's top move, position was NOT already winning

        if eval_cp is not None and best_eval_cp is not None:
            val_pawns = round(eval_cp / 100.0, 2)
            best_pawns = round(best_eval_cp / 100.0, 2)
            eval_score_str = f"+{val_pawns:.2f}" if val_pawns >= 0 else f"{val_pawns:.2f}"
            best_score_str = f"+{best_pawns:.2f}" if best_pawns >= 0 else f"{best_pawns:.2f}"

            # Centipawn loss vs engine best (always >= 0 unless depth anomaly, larger = worse move)
            if move.color.value == "white":
                cp_loss = best_eval_cp - eval_cp
                was_losing = best_pawns <= -1.0
                now_rescued = val_pawns >= -0.3
            else:
                cp_loss = eval_cp - best_eval_cp
                was_losing = best_pawns >= 1.0
                now_rescued = val_pawns <= 0.3

            # --- BOOK: opening move (first 10 moves) matching engine's top choice ---
            is_book = (
                move.move_number <= 10
                and move.uci == best_move_uci
            )

            # --- BRILLIANT: piece sacrifice that IS the engine best, position was NOT already winning ---
            # A sacrifice = move results in losing material but is still best
            played_uci_obj = chess.Move.from_uci(move.uci) if chess.Move.from_uci(move.uci) in prev_board.legal_moves else None
            is_capture = played_uci_obj and prev_board.is_capture(played_uci_obj)
            
            is_sacrifice = False
            if played_uci_obj:
                is_attacked = prev_board.is_attacked_by(not prev_board.turn, played_uci_obj.to_square)
                if is_capture:
                    # Capture: check if we give up more than we take AND the square is defended
                    from_piece = prev_board.piece_at(played_uci_obj.from_square)
                    to_piece = prev_board.piece_at(played_uci_obj.to_square)
                    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
                    if from_piece and to_piece:
                        our_val = piece_values.get(from_piece.piece_type, 0)
                        their_val = piece_values.get(to_piece.piece_type, 0)
                        is_sacrifice = (our_val > their_val) and is_attacked
                else:
                    # Non-capture: check if we move a piece to an attacked square where it is under-defended
                    # (A simple heuristic: moving any piece to an attacked square is a 'sacrifice' if engine says it's best)
                    is_sacrifice = is_attacked

            # For brilliant, check that the player wasn't already overwhelmingly winning
            already_winning = (best_pawns >= 1.5 if move.color.value == "white" else best_pawns <= -1.5)
            drawable = (val_pawns >= -0.5 if move.color.value == "white" else val_pawns <= 0.5)

            is_brilliant = (
                is_sacrifice
                and move.uci == best_move_uci  # must be engine's exact top move
                and not already_winning         # position was NOT already clearly winning
                and drawable                    # resulting position is at least drawable
                and cp_loss <= 30               # very close to or better than engine
            )

            # --- GREAT(!): move that rescues a losing or equal position significantly ---
            is_great = (
                not is_brilliant
                and not is_book
                and was_losing                   # was losing before
                and now_rescued                  # now equal or better after move
                and cp_loss <= 50                # close to engine best
            )

            if is_book:
                move_classification = "book"
                classification_label = f"{move.san} is a book move"
                best_move_label = f"{move.san} is theory ({eval_score_str})"
            elif is_brilliant:
                move_classification = "brilliant"
                classification_label = f"{move.san} is brilliant!!"
                best_move_label = f"{move.san} is the best move ({eval_score_str})"
            elif is_great:
                move_classification = "great"
                classification_label = f"{move.san} is a great move!"
                best_move_label = f"{move.san} saves the position ({eval_score_str})"
            elif move.uci == best_move_uci or cp_loss <= 10:
                move_classification = "best"
                classification_label = f"{move.san} is best move"
                best_move_label = f"{move.san} is best ({eval_score_str})"
            elif cp_loss <= 20:
                move_classification = "excellent"
                classification_label = f"{move.san} is excellent"
                best_move_label = f"{best_move_san or move.san} is best ({best_score_str})"
            elif cp_loss <= 50:
                move_classification = "good"
                classification_label = f"{move.san} played"
                best_move_label = f"{best_move_san or move.san} is best ({best_score_str})"
            elif cp_loss <= 100:
                move_classification = "inaccuracy"
                classification_label = f"{move.san} is an inaccuracy"
                best_move_label = f"{best_move_san or 'best move'} is best ({best_score_str})"
            elif cp_loss <= 200:
                move_classification = "mistake"
                classification_label = f"{move.san} is a mistake"
                best_move_label = f"{best_move_san or 'best move'} is best ({best_score_str})"
            elif cp_loss <= 300:
                move_classification = "miss"
                classification_label = f"{move.san} is a miss"
                best_move_label = f"{best_move_san or 'best move'} is best ({best_score_str})"
            else:
                move_classification = "blunder"
                classification_label = f"{move.san} is a blunder!"
                best_move_label = f"{best_move_san or 'best move'} is best ({best_score_str})"

        elif eval_cp is not None:
            val_pawns = round(eval_cp / 100.0, 2)
            eval_score_str = f"+{val_pawns:.2f}" if val_pawns >= 0 else f"{val_pawns:.2f}"
            move_classification = "good"
            classification_label = f"{move.san} played"
            best_move_label = f"{best_move_san or move.san} is best ({eval_score_str})"
        else:
            eval_score_str = "+0.25"
            classification_label = f"{move.san} played"
            best_move_label = f"{best_move_san or move.san} is recommended"

        timeline.append(
            {
                "move_number": move.move_number,
                "ply": move.ply,
                "color": move.color.value,
                "san": move.san,
                "uci": move.uci,
                "fen": move.fen,
                # Stockfish Engine metrics
                "eval_cp": eval_cp,
                "eval_score": eval_score_str,
                "best_move_san": best_move_san,
                "best_move_uci": best_move_uci,
                "move_classification": move_classification,
                "classification_label": classification_label,
                "best_move_label": best_move_label,
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


@router.get("/games/{game_id}/export-pgn", summary="Export annotated PGN file")
def export_annotated_pgn(game_id: int, db: Session = Depends(get_db)):
    """Export annotated PGN with embedded SHAP comments and collapse probabilities."""
    from fastapi.responses import Response

    repo = GameRepository(db)
    game = repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found")

    pgn_lines = [
        f'[Event "{game.event or "ChessTrace Game"}"]',
        f'[Site "{game.site or "ChessTrace"}"]',
        f'[Date "{game.game_date or "????.??.??"}"]',
        f'[White "{game.white_player.display_name if game.white_player else "White"}"]',
        f'[Black "{game.black_player.display_name if game.black_player else "Black"}"]',
        f'[Result "{game.result.value if hasattr(game.result, "value") else str(game.result)}"]',
        f'[TimeControl "{game.time_control or "-"}"]',
        "",
    ]

    move_tokens = []
    for m in game.moves:
        token = f"{m.move_number}. " if m.color.value == "white" else ""
        clk_str = f" {{ [%clk {(m.clock_after // 1000) if m.clock_after else 0}s] }}"
        token += f"{m.san}{clk_str}"
        move_tokens.append(token)

    move_tokens.append(game.result.value if hasattr(game.result, "value") else str(game.result))
    pgn_lines.append(" ".join(move_tokens))

    pgn_content = "\n".join(pgn_lines)
    return Response(
        content=pgn_content,
        media_type="application/x-chess-pgn",
        headers={"Content-Disposition": f'attachment; filename="chesstrace_game_{game_id}.pgn"'},
    )
