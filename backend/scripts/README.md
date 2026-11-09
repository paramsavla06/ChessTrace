# ChessTrace — Backend ML & Utility Scripts

This directory contains standalone operational scripts for dataset preparation, validation, model training, evaluation, database seeding, and real-game verification.

---

## Script Index & Recommended Pipeline Order

```
[Raw PGN]
   │
   ▼
1. prepare_dataset.py   ──▶ Streams binary PGN & writes Parquet chunks
   │
   ▼
2. validate_dataset.py  ──▶ Asserts 0 nulls, 0 duplicates, valid schema
   │
   ▼
3. train_models.py      ──▶ 3-way disjoint split & trains 8 XGBoost models
   │
   ▼
4. evaluate_models.py   ──▶ Evaluates on held-out test partition
   │
   ▼
5. verify_real_game.py  ──▶ Real database end-to-end inference verification
```

---

### 1. `prepare_dataset.py`
High-throughput streaming PGN parser and feature extraction pipeline.
* **Input**: Raw Lichess standard PGN file (e.g. `data/raw/lichess_db_standard_rated_2017-11.pgn`)
* **Output**: Atomic Parquet chunks under `data/processed/v2/` + checkpoint in `data/checkpoints/`
* **Features**: Resumable from byte offset, SHA-256 fallback game IDs, cross-chunk duplicate detection.
* **Usage**:
  ```bash
  python backend/scripts/prepare_dataset.py --max-games 200000 --resume
  ```

---

### 2. `validate_dataset.py`
Quality gate validating all generated Parquet chunks before model training.
* **Input**: `data/processed/v2/`
* **Checks**: Zero null values, zero infinite values, zero duplicate game IDs, schema conformity, outcome distribution, clock telemetry percentage.
* **Usage**:
  ```bash
  python backend/scripts/validate_dataset.py --data-dir data/processed/v2 --target-games 200000
  ```

---

### 3. `train_models.py`
Trains the V2 XGBoost model suite using a strict three-way disjoint group-based split.
* **Input**: `data/processed/v2/`
* **Output**:
  * `collapse_xgboost.json` (General model)
  * 7 ELO-specific models (`elo_xgboost_<bucket>.json`)
  * `test_partition.parquet` (held-out test split, untouched during training)
  * `model_manifest.json`
* **Split Proportions**: Train (70%), Early-Stopping Validation (15%), Final Test (15%).
* **Memory Optimization**: Streams chunk-by-chunk with downcasted dtypes (`int8`, `float32`).
* **Usage**:
  ```bash
  python backend/scripts/train_models.py --data-dir data/processed/v2 --weights-dir backend/app/ml/weights/v2
  ```

---

### 4. `evaluate_models.py`
Independent offline evaluation executed exclusively on the held-out test partition.
* **Input**: `backend/app/ml/weights/v2/test_partition.parquet` + trained model JSON weights
* **Output**: `backend/reports/evaluation_report_v2.json`
* **Metrics**: RMSE, MAE, R², median absolute error, residuals.
* **Breakdowns**: By game phase (opening/middlegame/endgame), ELO tier, clock telemetry presence, and time control.
* **Usage**:
  ```bash
  python backend/scripts/evaluate_models.py --weights-dir backend/app/ml/weights/v2
  ```

---

### 5. `verify_real_game.py`
End-to-end integration script that runs inference against real PostgreSQL database games.
* **Tests**:
  1. Loads Game ID 1 (or first available game) from database.
  2. Extracts position and time features across plies.
  3. Tests `WinCollapsePredictor` (V2 XGBoost model).
  4. Tests `EloSimulatorManager` across all 7 rating tiers.
  5. Tests `ShapExplainer` feature attributions and narrative generation.
  6. Tests V1 fallback simulation.
* **Usage**:
  ```bash
  python backend/scripts/verify_real_game.py
  ```

---

### 6. `seed_database.py` (alias: `test_database.py`)
Development database smoke test and reference seed script.
* **Action**: Truncates existing database tables and seeds a standard Magnus Carlsen vs Hikaru Nakamura reference game with full plies, clocks, and evaluations.
* **Usage**:
  ```bash
  python backend/scripts/seed_database.py
  ```
