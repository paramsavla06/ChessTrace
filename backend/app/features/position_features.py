"""
Position feature extractor.

Extracts positional metrics from chess.Board objects for ML feature vectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import chess

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

CENTER_SQUARES = {chess.E4, chess.D4, chess.E5, chess.D5}


class GamePhase(str, Enum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


@dataclass(slots=True, frozen=True)
class PositionFeatures:
    material_balance: int
    white_material: int
    black_material: int
    game_phase: str
    white_mobility: int
    black_mobility: int
    white_center_control: int
    black_center_control: int
    white_pawn_shield: int
    black_pawn_shield: int
    white_passed_pawns: int
    black_passed_pawns: int
    white_isolated_pawns: int
    black_isolated_pawns: int
    white_doubled_pawns: int
    black_doubled_pawns: int


def extract_position_features(board: chess.Board) -> PositionFeatures:
    """
    Extract comprehensive positional features from a chess board state.

    Parameters
    ----------
    board
        Position to analyze.

    Returns
    -------
    PositionFeatures
        Extracted tabular positional feature DTO.
    """
    white_mat = sum(
        len(board.pieces(p_type, chess.WHITE)) * PIECE_VALUES[p_type]
        for p_type in PIECE_VALUES
    )
    black_mat = sum(
        len(board.pieces(p_type, chess.BLACK)) * PIECE_VALUES[p_type]
        for p_type in PIECE_VALUES
    )
    mat_balance = white_mat - black_mat

    # Game phase classification based on non-pawn material sum
    non_pawn_mat = sum(
        (len(board.pieces(p_type, chess.WHITE)) + len(board.pieces(p_type, chess.BLACK)))
        * PIECE_VALUES[p_type]
        for p_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )

    if non_pawn_mat > 28:
        phase = GamePhase.OPENING.value
    elif non_pawn_mat >= 14:
        phase = GamePhase.MIDDLEGAME.value
    else:
        phase = GamePhase.ENDGAME.value

    # Mobility
    turn_backup = board.turn
    board.turn = chess.WHITE
    white_mob = board.legal_moves.count()
    board.turn = chess.BLACK
    black_mob = board.legal_moves.count()
    board.turn = turn_backup

    # Center control
    white_center = sum(
        1 for sq in CENTER_SQUARES if board.is_attacked_by(chess.WHITE, sq)
    )
    black_center = sum(
        1 for sq in CENTER_SQUARES if board.is_attacked_by(chess.BLACK, sq)
    )

    # King pawn shield
    w_king_sq = board.king(chess.WHITE)
    b_king_sq = board.king(chess.BLACK)

    w_shield = 0
    if w_king_sq is not None:
        w_file, w_rank = chess.square_file(w_king_sq), chess.square_rank(w_king_sq)
        for f in range(max(0, w_file - 1), min(8, w_file + 2)):
            for r in range(w_rank + 1, min(8, w_rank + 3)):
                if board.piece_at(chess.square(f, r)) == chess.Piece(chess.PAWN, chess.WHITE):
                    w_shield += 1

    b_shield = 0
    if b_king_sq is not None:
        b_file, b_rank = chess.square_file(b_king_sq), chess.square_rank(b_king_sq)
        for f in range(max(0, b_file - 1), min(8, b_file + 2)):
            for r in range(max(0, b_rank - 2), b_rank):
                if board.piece_at(chess.square(f, r)) == chess.Piece(chess.PAWN, chess.BLACK):
                    b_shield += 1

    # Pawn structure (isolated, doubled, passed)
    w_pawns = board.pieces(chess.PAWN, chess.WHITE)
    b_pawns = board.pieces(chess.PAWN, chess.BLACK)

    w_files = [chess.square_file(sq) for sq in w_pawns]
    b_files = [chess.square_file(sq) for sq in b_pawns]

    w_doubled = len(w_files) - len(set(w_files))
    b_doubled = len(b_files) - len(set(b_files))

    w_isolated = sum(
        1
        for sq in w_pawns
        if not any(abs(f - chess.square_file(sq)) == 1 for f in w_files)
    )
    b_isolated = sum(
        1
        for sq in b_pawns
        if not any(abs(f - chess.square_file(sq)) == 1 for f in b_files)
    )

    # Passed pawns
    w_passed = 0
    for sq in w_pawns:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        blocked = False
        for enemy_sq in b_pawns:
            ef, er = chess.square_file(enemy_sq), chess.square_rank(enemy_sq)
            if abs(ef - f) <= 1 and er > r:
                blocked = True
                break
        if not blocked:
            w_passed += 1

    b_passed = 0
    for sq in b_pawns:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        blocked = False
        for enemy_sq in w_pawns:
            ef, er = chess.square_file(enemy_sq), chess.square_rank(enemy_sq)
            if abs(ef - f) <= 1 and er < r:
                blocked = True
                break
        if not blocked:
            b_passed += 1

    return PositionFeatures(
        material_balance=mat_balance,
        white_material=white_mat,
        black_material=black_mat,
        game_phase=phase,
        white_mobility=white_mob,
        black_mobility=black_mob,
        white_center_control=white_center,
        black_center_control=black_center,
        white_pawn_shield=w_shield,
        black_pawn_shield=b_shield,
        white_passed_pawns=w_passed,
        black_passed_pawns=b_passed,
        white_isolated_pawns=w_isolated,
        black_isolated_pawns=b_isolated,
        white_doubled_pawns=w_doubled,
        black_doubled_pawns=b_doubled,
    )
