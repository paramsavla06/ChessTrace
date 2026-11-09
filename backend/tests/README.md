# ChessTrace — Backend Test Suite

This directory contains the automated test suite for the ChessTrace backend.
All tests are 100% hermetic: they run in-memory without requiring a live PostgreSQL instance, external network access, or Stockfish engine binaries.

---

## Quick Start

### Run the entire test suite via pytest
```bash
cd backend
python -m pytest tests/ -v
```

### Run a specific test module
```bash
cd backend
python -m pytest tests/test_model_freeze_and_v2_enforcement.py -v
```

### Run any test file directly via Python
Every test file is configured with `sys.path` resolution and an entrypoint:
```bash
python backend/tests/test_features.py
python backend/tests/test_full_pipeline.py
```

---

## Test Inventory & Coverage Map

| Test Module | Tests | Type | Scope & Description |
|---|:---:|:---:|---|
| [`test_features.py`](test_features.py) | 2 | Unit | **Feature Engineering**: Validates position features (material balance, mobility, pawn structure, center control, game phase) and clock telemetry features (think time, remaining time, time pressure flags, deviation). |
| [`test_split_utils.py`](test_split_utils.py) | 5 | Unit | **Data Partitioning**: Validates group-based 3-way game splits (70/15/15), mathematical disjointness across train/val/test splits, determinism, and absence of data leakage across ELO sub-brackets. |
| [`test_prepare_dataset.py`](test_prepare_dataset.py) | 7 | Unit / Integration | **Data Pipeline**: Validates streaming PGN parsing, SHA-256 fallback game IDs, atomic Parquet chunking, checkpointing & resumability, deduplication, and malformed PGN robustness. |
| [`test_ml_pipeline.py`](test_ml_pipeline.py) | 5 | Integration | **ML Core**: Validates `WinCollapsePredictor` score bounds `[0, 1]`, `ShapExplainer` feature attributions, `PersonalProfileGenerator`, model cache isolation, V2 resolution, and presence of all 7 ELO models. |
| [`test_model_freeze_and_v2_enforcement.py`](test_model_freeze_and_v2_enforcement.py) | 10 | Regression / Security | **Model Freeze Enforcement**: Strictly guarantees that no `.fit()` or retraining is ever triggered during startup or inference, V2 models are authoritative, file hashes are immutable, and silent fallbacks are blocked. |
| [`test_advanced_ml.py`](test_advanced_ml.py) | 3 | Integration | **Advanced Analytics**: Tests all 6 analytical engines (`EloSimulator`, `AnomalyDetector`, `PlayerArchetypeClassifier`, `PlayerSimilarityEngine`, `CrossGamePatternDetector`) and `/what-if`, `/elo-sim` API endpoints. |
| [`test_api_app.py`](test_api_app.py) | 4 | Integration | **FastAPI Endpoints**: Tests root (`/`), health check (`/api/v1/health`), game list (`/api/v1/games`), and ML prediction endpoint (`/api/v1/analysis/predict`). |
| [`test_parser_pipeline.py`](test_parser_pipeline.py) | 1 | Integration | **PGN Ingestion**: Hermetic in-memory SQLite test validating end-to-end ingestion of PGN into `Game`, `Move`, `Player`, and `Evaluation` relational tables. |
| [`test_full_pipeline.py`](test_full_pipeline.py) | 1 | End-to-End | **Full Stack Pipeline**: In-memory end-to-end flow from raw PGN parsing through database storage, feature extraction, WinCollapsePredictor inference, and SHAP narrative generation. |

**Total Tests**: **38 tests**, all passing.

---

## Architectural & Safety Principles

1. **Hermetic & Isolated**: Tests use in-memory SQLite engines (`sqlite:///:memory:`) and synthetic/sample PGN fixtures so that unit and integration tests run reliably in CI and offline.
2. **Zero In-flight Retraining**: `test_model_freeze_and_v2_enforcement.py` monitors XGBoost methods to assert that training (`.fit()`, `.train()`) is never called by application or inference logic.
3. **Artifact Integrity**: V2 model weights in `backend/app/ml/weights/v2/` are verified for immutability; test fixtures do not modify frozen model weights on disk.
4. **Dual Execution Support**: Every test file can be executed either via standard `pytest` runner or directly as an executable Python script (`python tests/<file>.py`).
