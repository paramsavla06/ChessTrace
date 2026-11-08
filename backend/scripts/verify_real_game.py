"""
End-to-End Real Database Game Verification Script.

Tests the full ML inference stack with real data from PostgreSQL:
1. Loads Game ID 1 (or first available game) from PostgreSQL.
2. Extracts position and time features across plies.
3. Tests WinCollapsePredictor (V2 XGBoost model with V1 fallback).
4. Verifies semantic fields: expected_score, black_expected_score, collapse_risk_index.
5. Verifies backward-compatible aliases: win_probability, collapse_probability.
6. Tests EloSimulatorManager loading across all 7 ELO tiers.
7. Tests ShapExplainer feature importance and narrative generation.
8. Tests V1 fallback simulation to verify graceful degradation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
from app.database.session import SessionLocal
from app.models.game import Game
from app.models.move import Move
from app.features.position_features import extract_position_features
from app.features.time_features import extract_time_features
from app.ml.collapse_model import WinCollapsePredictor, PredictionResult
from app.ml.elo_model import EloSimulatorManager
from app.ml.explainer import ShapExplainer


def run_verification():
    print("=" * 70)
    print(" ChessTrace V2 End-to-End Real Game Integration Verification ".center(70))
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Fetch Game 1 from PostgreSQL
        game = db.query(Game).filter(Game.id == 1).first()
        if not game:
            game = db.query(Game).first()
            if not game:
                print("[ERROR] No games found in database!")
                return False

        print(f"\n[1] Fetched Game ID {game.id}:")
        print(f"    Event: {game.event}")
        print(f"    White: {game.white_player.display_name} ({getattr(game.white_player, 'elo', 'N/A')})")
        print(f"    Black: {game.black_player.display_name} ({getattr(game.black_player, 'elo', 'N/A')})")
        print(f"    Result: {game.result.value}")
        print(f"    Total Moves: {len(game.moves)}")

        # 2. Test WinCollapsePredictor loading
        print("\n[2] Initializing WinCollapsePredictor (expecting V2 model)...")
        from app.ml.collapse_model import resolve_model_weights_path
        active_weights = resolve_model_weights_path()
        predictor = WinCollapsePredictor()
        print(f"    Predictor model loaded: {type(predictor.model)}")
        print(f"    Active weights path: {active_weights}")
        assert predictor.model is not None, "Predictor model must not be None"
        assert active_weights is not None and "v2" in str(active_weights), f"Expected V2 weights, got {active_weights}"

        # 3. Test EloSimulatorManager loading
        print("\n[3] Initializing EloSimulatorManager (expecting all 7 V2 models)...")
        elo_mgr = EloSimulatorManager()
        loaded_buckets = list(elo_mgr.elo_models.keys())
        print(f"    Loaded ELO buckets ({len(loaded_buckets)}): {loaded_buckets}")
        expected_buckets = ["<1000", "1000-1200", "1200-1400", "1400-1600", "1600-1800", "1800-2000", "2000+"]
        for b in expected_buckets:
            assert b in loaded_buckets, f"Missing ELO bucket: {b}"

        # 4. Step through first 10 moves
        print("\n[4] Running inference on first 10 plies of Game ID {}:".format(game.id))
        board = chess.Board()
        prev_white: list[Move] = []
        prev_black: list[Move] = []

        moves_to_test = sorted(game.moves, key=lambda m: m.ply)[:10]

        for move in moves_to_test:
            # Push move to board
            m_obj = board.parse_uci(move.uci) if move.uci else board.parse_san(move.san)
            board.push(m_obj)

            pos_f = extract_position_features(board)
            prev_moves = prev_white if move.color.value == "white" else prev_black
            time_f = extract_time_features(
                move,
                previous_moves_same_color=prev_moves,
                initial_clock_seconds=180,
            )

            pred: PredictionResult = predictor.predict(
                pos_f,
                time_f,
                eval_cp=0.0,
                turn=board.turn,
            )

            # Assertions on PredictionResult
            assert 0.0 <= pred.expected_score <= 1.0, f"Expected score out of bounds: {pred.expected_score}"
            assert 0.0 <= pred.black_expected_score <= 1.0, f"Black expected score out of bounds: {pred.black_expected_score}"
            assert abs((pred.expected_score + pred.black_expected_score) - 1.0) < 1e-4, "Sum of expected scores must be 1.0"
            assert 0.0 <= pred.collapse_risk_index <= 1.0, f"Collapse risk out of bounds: {pred.collapse_risk_index}"
            assert 0.0 <= pred.black_collapse_risk_index <= 1.0, f"Black collapse risk out of bounds: {pred.black_collapse_risk_index}"
            assert pred.win_probability == pred.expected_score, "Backward alias win_probability mismatch"
            assert pred.collapse_probability == pred.collapse_risk_index, "Backward alias collapse_probability mismatch"

            print(
                f"    Ply {move.ply:>2} ({move.color.value[0].upper()} {move.san:<5}) | "
                f"E[White]: {pred.expected_score:.4f} | E[Black]: {pred.black_expected_score:.4f} | "
                f"CollapseRisk(W): {pred.collapse_risk_index:.4f} | CollapseRisk(B): {pred.black_collapse_risk_index:.4f} | "
                f"Clock: {time_f.time_remaining:.1f}s | StressMult: {pred.time_pressure_risk_multiplier:.2f}x"
            )

            if move.color.value == "white":
                prev_white.append(move)
            else:
                prev_black.append(move)

        # 5. Test SHAP Explainer
        print("\n[5] Testing SHAP Explainer on move 5...")
        move_5 = moves_to_test[4]
        # board is at move 10, create board at move 5
        b5 = chess.Board()
        for m in moves_to_test[:5]:
            m_o = b5.parse_uci(m.uci) if m.uci else b5.parse_san(m.san)
            b5.push(m_o)
        pos_f5 = extract_position_features(b5)
        time_f5 = extract_time_features(move_5, previous_moves_same_color=prev_white[:2], initial_clock_seconds=180)

        explainer = ShapExplainer(predictor)
        explanation = explainer.explain(pos_f5, time_f5)

        print(f"    Narrative summary: {explanation.narrative_summary}")
        print("    Top positive factors:")
        for factor in explanation.top_positive_factors[:3]:
            print(f"      + {factor.display_name}: SHAP = {factor.shap_value:+.4f} (value={factor.feature_value})")
        print("    Top negative factors:")
        for factor in explanation.top_negative_factors[:3]:
            print(f"      - {factor.display_name}: SHAP = {factor.shap_value:+.4f} (value={factor.feature_value})")

        assert len(explanation.top_positive_factors) + len(explanation.top_negative_factors) > 0, "SHAP should produce contributing factors"

        # 6. Test EloSimulatorManager simulation across tiers
        print("\n[6] Testing ELO Simulator simulation across tiers on move 5 position...")
        for bucket in expected_buckets:
            # Test direct bucket-specific model prediction
            tier_pred = elo_mgr.elo_models[bucket].predict(pos_f5, time_f5, eval_cp=0.0, turn=b5.turn)
            # Test high-level human move simulation
            sim = elo_mgr.predict_for_elo(b5, pos_f5, time_f5, target_elo_bucket=bucket)
            top_cand = sim.top_candidate_moves[0] if sim.top_candidate_moves else None
            cand_info = f"{top_cand.san} ({top_cand.probability:.2%})" if top_cand else "None"
            print(
                f"    Tier {bucket:>9}: E[Score]={tier_pred.expected_score:.4f} | "
                f"CollapseRisk={tier_pred.collapse_risk_index:.4f} | "
                f"TopPredictedMove={cand_info}"
            )
            assert 0.0 <= tier_pred.expected_score <= 1.0

        # 7. Test V1 fallback mechanism
        print("\n[7] Testing V1 Fallback mechanism...")
        v1_path = Path(__file__).resolve().parent.parent / "app" / "ml" / "weights" / "collapse_xgboost.json"
        if v1_path.exists():
            import xgboost as xgb
            v1_model = xgb.XGBRegressor()
            v1_model.load_model(str(v1_path))
            v1_predictor = WinCollapsePredictor(model=v1_model)
            v1_pred = v1_predictor.predict(pos_f5, time_f5, eval_cp=0.0, turn=b5.turn)
            print(f"    V1 Fallback model loaded successfully from: {v1_path}")
            print(f"    V1 E[Score]: {v1_pred.expected_score:.4f}, V1 CollapseRisk: {v1_pred.collapse_risk_index:.4f}")
            assert 0.0 <= v1_pred.expected_score <= 1.0
        else:
            print("    [NOTE] V1 model not present, skipping fallback check.")

        print("\n" + "=" * 70)
        print(" VERIFICATION COMPLETE: ALL INTEGRATION CHECKS PASSED ".center(70))
        print("=" * 70)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
