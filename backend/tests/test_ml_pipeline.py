from __future__ import annotations

import chess
from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.ml.collapse_model import WinCollapsePredictor
from app.ml.explainer import ShapExplainer
from app.ml.personal_profile import generate_personal_profile
from app.models.game import Game
from app.models.move import Move, MoveColor
from app.models.player import Player


def test_win_collapse_predictor_and_shap():
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
    pos_feats = extract_position_features(board)

    move = Move(
        game_id=1,
        move_number=3,
        ply=5,
        color=MoveColor.WHITE,
        san="Bb5",
        uci="f1b5",
        fen="r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        time_spent=3,
        clock_after=25,  # 25 seconds remaining (time pressure < 30s)
    )

    time_feats = extract_time_features(move, previous_moves_same_color=[])

    predictor = WinCollapsePredictor()
    pred = predictor.predict(pos_feats, time_feats)

    assert 0.0 <= pred.win_probability <= 1.0
    assert 0.0 <= pred.collapse_probability <= 1.0
    assert pred.time_pressure_risk_multiplier == 2.4

    explainer = ShapExplainer(predictor)
    exp = explainer.explain(pos_feats, time_feats)

    assert exp.narrative_summary != ""
    assert isinstance(exp.top_positive_factors, list)
    assert isinstance(exp.top_negative_factors, list)


def test_personal_profile_generator():
    player_white = Player(id=1, display_name="TestPlayer", normalized_name="testplayer")
    player_black = Player(id=2, display_name="Opponent", normalized_name="opponent")

    move1 = Move(
        move_number=1,
        ply=1,
        color=MoveColor.WHITE,
        san="e4",
        uci="e2e4",
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        time_spent=2000,
        clock_after=178000,
    )
    move2 = Move(
        move_number=2,
        ply=3,
        color=MoveColor.WHITE,
        san="Nf3",
        uci="g1f3",
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 2",
        time_spent=15000,  # Slow think
        clock_after=163000,
        is_capture=True,
    )
    move3 = Move(
        move_number=3,
        ply=5,
        color=MoveColor.WHITE,
        san="Bb5",
        uci="f1b5",
        fen="r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        time_spent=500,  # Panic fast move post-loss
        clock_after=162500,
    )

    game = Game(
        id=101,
        white_player=player_white,
        black_player=player_black,
        white_player_id=1,
        black_player_id=2,
        moves=[move1, move2, move3],
    )

    profile = generate_personal_profile("TestPlayer", [game])

    assert profile.player_name == "TestPlayer"
    assert profile.total_games_analyzed == 1
    assert len(profile.accuracy_vs_clock) == 4
    assert profile.time_distribution.opening_time_pct == 100.0


if __name__ == "__main__":
    test_win_collapse_predictor_and_shap()
    test_personal_profile_generator()
    print("All ML pipeline tests passed!")
