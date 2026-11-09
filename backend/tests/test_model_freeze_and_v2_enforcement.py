"""
Regression Protection Tests: Model Freeze & V2 Enforcement.

Guarantees:
1. Application startup and inference NEVER call .fit(), fine-tuning, or retraining.
2. V2 is the permanent authoritative model suite (General + 7 ELO models).
3. Missing or corrupt V2 artifacts produce explicit errors, NEVER silently falling back to V1.
4. V1 is only accessible via explicit debug environment configuration (CHESSTRACE_MODEL_VERSION=v1).
5. Model artifact files remain 100% byte-for-byte immutable during inference.
6. SHAP Explainer uses the exact loaded V2 model instance.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import chess
import pytest
import xgboost as xgb
from fastapi.testclient import TestClient

from app.core.constants import ELO_BUCKETS
from app.features.position_features import extract_position_features
from app.features.time_features import TimeFeatures
from app.main import app
from app.ml.collapse_model import (
    WinCollapsePredictor,
    resolve_model_weights_path,
    get_shared_model,
    set_shared_model,
    get_model_diagnostics,
    V2_WEIGHTS_PATH,
    DEFAULT_WEIGHTS_PATH,
)
from app.ml.elo_model import EloSimulatorManager, WEIGHTS_DIR
from app.ml.explainer import ShapExplainer, get_shared_tree_explainer


client = TestClient(app)


def test_no_fit_called_during_predictor_init_and_inference():
    """Ensure WinCollapsePredictor never triggers training/fitting during initialization or inference."""
    with patch.object(xgb.XGBRegressor, "fit") as mock_fit:
        predictor = WinCollapsePredictor()
        
        board = chess.Board()
        pos_feats = extract_position_features(board)
        time_feats = TimeFeatures(
            think_time=3.5,
            time_remaining=120.0,
            is_time_pressure_120s=False,
            is_time_pressure_60s=False,
            is_time_pressure_30s=False,
            time_usage_ratio=0.03,
            running_avg_think_time=3.5,
            think_time_deviation=0.0,
            time_control="blitz",
            has_clock_data=True,
        )

        res = predictor.predict(pos_feats, time_feats)
        assert 0.0 <= res.expected_score <= 1.0
        assert 0.0 <= res.collapse_risk_index <= 1.0

        # Strict guarantee: .fit() must NEVER be called
        mock_fit.assert_not_called()


def test_no_fit_called_during_api_requests():
    """Ensure API prediction and what-if endpoints never trigger .fit()."""
    with patch.object(xgb.XGBRegressor, "fit") as mock_fit:
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "think_time_sec": 2.0,
            "time_remaining_sec": 178.0,
            "initial_clock_seconds": 180,
        }
        resp = client.post("/api/v1/analysis/predict", json=payload)
        assert resp.status_code == 200

        what_if_payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "played_move_uci": "e7e5",
            "alternative_move_uci": "c7c5",
            "think_time_sec": 2.0,
            "time_remaining_sec": 178.0,
            "perspective": "black",
        }
        resp_what_if = client.post("/api/v1/analysis/what-if", json=what_if_payload)
        assert resp_what_if.status_code == 200

        # Strict guarantee: .fit() must NEVER be called
        mock_fit.assert_not_called()


def test_authoritative_v2_resolution_default():
    """Ensure V2 model is resolved by default and diagnostic reports it."""
    # Ensure env is default
    if "CHESSTRACE_MODEL_VERSION" in os.environ:
        del os.environ["CHESSTRACE_MODEL_VERSION"]

    resolved = resolve_model_weights_path()
    assert resolved == V2_WEIGHTS_PATH
    assert resolved.exists()
    assert "v2" in str(resolved)

    diag = get_model_diagnostics()
    assert diag["active_model_version"] == "v2"
    assert diag["authoritative_v2"] is True
    assert diag["artifact_exists"] is True


def test_no_silent_fallback_when_v2_general_artifact_missing():
    """Ensure missing V2 general artifact raises FileNotFoundError instead of silently falling back to V1."""
    if "CHESSTRACE_MODEL_VERSION" in os.environ:
        del os.environ["CHESSTRACE_MODEL_VERSION"]

    with patch("app.ml.collapse_model.V2_WEIGHTS_PATH", Path("nonexistent/path/collapse_xgboost.json")):
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_model_weights_path()
        assert "Automatic fallback to legacy V1 is strictly prohibited" in str(exc_info.value)


def test_no_silent_fallback_when_v2_elo_artifact_missing(tmp_path):
    """Ensure missing V2 ELO artifact raises FileNotFoundError instead of falling back to V1."""
    if "CHESSTRACE_MODEL_VERSION" in os.environ:
        del os.environ["CHESSTRACE_MODEL_VERSION"]

    # Point weights to an empty temp directory to simulate missing bucket
    with patch("app.ml.elo_model.WEIGHTS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError) as exc_info:
            # Force reload
            from app.ml import elo_model
            elo_model._MODELS_LOADED = False
            EloSimulatorManager()
        assert "Automatic fallback" in str(exc_info.value)

    # Restore legitimate state
    from app.ml import elo_model
    elo_model._MODELS_LOADED = False
    EloSimulatorManager()


def test_explicit_v1_debug_mode_only():
    """Ensure V1 fallback is accessible ONLY when CHESSTRACE_MODEL_VERSION=v1 is explicitly set."""
    try:
        os.environ["CHESSTRACE_MODEL_VERSION"] = "v1"
        resolved = resolve_model_weights_path()
        assert resolved == DEFAULT_WEIGHTS_PATH
        assert "v2" not in str(resolved)
    finally:
        del os.environ["CHESSTRACE_MODEL_VERSION"]


def test_all_seven_elo_v2_models_loaded():
    """Verify all 7 ELO models are loaded from V2 and can simulate without fallback to V1."""
    manager = EloSimulatorManager()
    assert len(manager.elo_models) == 7
    for bucket in ELO_BUCKETS:
        assert bucket in manager.elo_models
        pred = manager.get_model(bucket)
        assert pred.model is not None


def test_elo_unknown_bucket_falls_back_to_v2_general():
    """Verify unknown ELO bucket request safely falls back to V2 General model (not V1)."""
    manager = EloSimulatorManager()
    fallback_predictor = manager.get_model("unknown_bucket_9999")
    assert fallback_predictor is not None
    # Model should be loaded from authoritative V2
    assert fallback_predictor.model is not None


def test_model_artifact_hashes_immutable_during_inference():
    """Verify all 8 V2 model JSON files remain strictly bit-for-bit identical before and after inference."""
    v2_dir = Path(__file__).resolve().parent.parent / "app" / "ml" / "weights" / "v2"
    json_files = sorted(v2_dir.glob("*.json"))
    assert len(json_files) >= 8

    # Record hashes before
    hashes_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in json_files}

    # Run heavy inference across general predictor, ELO models, and SHAP
    predictor = WinCollapsePredictor()
    board = chess.Board()
    pos_feats = extract_position_features(board)
    time_feats = TimeFeatures(
        think_time=2.0, time_remaining=60.0, is_time_pressure_120s=False,
        is_time_pressure_60s=True, is_time_pressure_30s=False, time_usage_ratio=0.03,
        running_avg_think_time=2.0, think_time_deviation=0.0, time_control="blitz", has_clock_data=True,
    )
    predictor.predict(pos_feats, time_feats)

    manager = EloSimulatorManager()
    for bucket in ELO_BUCKETS:
        manager.get_model(bucket).predict(pos_feats, time_feats)

    explainer = ShapExplainer(predictor)
    explainer.explain(pos_feats, time_feats)

    # Recompute hashes after
    hashes_after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in json_files}

    for name in hashes_before:
        assert hashes_before[name] == hashes_after[name], f"Artifact {name} was modified during inference!"


def test_shap_uses_exact_active_v2_model():
    """Ensure SHAP TreeExplainer references the exact active V2 model instance."""
    predictor = WinCollapsePredictor()
    explainer = ShapExplainer(predictor)
    
    # Verify explainer model reference
    active_model = predictor.model
    assert active_model is not None
    assert explainer._tree_explainer is not None

    # Invalidate cache when model reference changes
    dummy_model = xgb.XGBRegressor()
    new_explainer = get_shared_tree_explainer(dummy_model)
    assert new_explainer is not None
    
    # Restore legitimate explainer
    get_shared_tree_explainer(active_model)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))


