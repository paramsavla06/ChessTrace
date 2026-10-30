"""
SHAP Narrative Explainability Engine for ChessTrace.

Generates human-readable explanations of win and collapse probability shifts
using SHAP TreeExplainer feature attributions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap

from app.features.position_features import PositionFeatures
from app.features.time_features import TimeFeatures
from app.ml.collapse_model import FEATURE_COLUMNS, WinCollapsePredictor

logger = logging.getLogger(__name__)

FEATURE_NAME_MAP = {
    "material_balance": "Material balance",
    "white_material": "White material",
    "black_material": "Black material",
    "white_mobility": "White piece mobility",
    "black_mobility": "Black piece mobility",
    "white_center_control": "White center control",
    "black_center_control": "Black center control",
    "white_pawn_shield": "White king pawn shield",
    "black_pawn_shield": "Black king pawn shield",
    "white_passed_pawns": "White passed pawns",
    "black_passed_pawns": "Black passed pawns",
    "white_isolated_pawns": "White isolated pawns",
    "black_isolated_pawns": "Black isolated pawns",
    "white_doubled_pawns": "White doubled pawns",
    "black_doubled_pawns": "Black doubled pawns",
    "think_time": "Move think time",
    "time_remaining": "Clock time remaining",
    "is_time_pressure_120s": "Under 2 minutes clock pressure",
    "is_time_pressure_60s": "Under 1 minute clock pressure",
    "is_time_pressure_30s": "Under 30 seconds clock stress",
    "time_usage_ratio": "Think time ratio",
    "running_avg_think_time": "Average thought pace",
    "think_time_deviation": "Rush/Overthink deviation",
}


@dataclass(slots=True, frozen=True)
class FeatureImpact:
    feature_key: str
    display_name: str
    shap_value: float
    feature_value: float


@dataclass(slots=True, frozen=True)
class ExplanationResult:
    narrative_summary: str
    top_positive_factors: list[FeatureImpact]
    top_negative_factors: list[FeatureImpact]


_SHARED_TREE_EXPLAINER: shap.TreeExplainer | None = None


def get_shared_tree_explainer(model: Any) -> shap.TreeExplainer | None:
    """Return globally cached SHAP TreeExplainer instance to avoid costly re-instantiation per request."""
    global _SHARED_TREE_EXPLAINER
    if _SHARED_TREE_EXPLAINER is not None:
        return _SHARED_TREE_EXPLAINER
    if model is not None:
        try:
            _SHARED_TREE_EXPLAINER = shap.TreeExplainer(model)
            logger.info("Initialized shared SHAP TreeExplainer successfully.")
        except Exception as exc:
            logger.warning("Could not initialize SHAP TreeExplainer: %s", exc)
    return _SHARED_TREE_EXPLAINER


class ShapExplainer:
    """
    SHAP TreeExplainer wrapper providing natural language predictions explanations.
    """

    def __init__(self, predictor: WinCollapsePredictor) -> None:
        self.predictor = predictor
        self._tree_explainer: shap.TreeExplainer | None = (
            get_shared_tree_explainer(predictor.model)
            if predictor.model is not None
            else None
        )

    def _heuristic_shap(self, X: pd.DataFrame) -> np.ndarray:
        """Heuristic SHAP proxy when TreeExplainer is unavailable."""
        shap_values = np.zeros(len(FEATURE_COLUMNS))
        for idx, col in enumerate(FEATURE_COLUMNS):
            val = float(X[col].iloc[0])
            if col == "material_balance":
                shap_values[idx] = val * 0.12
            elif col == "white_center_control":
                shap_values[idx] = val * 0.04
            elif col == "black_center_control":
                shap_values[idx] = -val * 0.04
            elif col == "white_mobility":
                shap_values[idx] = (val - 15.0) * 0.01
            elif col == "black_mobility":
                shap_values[idx] = -(val - 15.0) * 0.01
            elif col == "white_pawn_shield":
                shap_values[idx] = (val - 2.0) * 0.05
            elif col == "black_pawn_shield":
                shap_values[idx] = -(val - 2.0) * 0.05
            elif col == "is_time_pressure_30s" and val == 1:
                shap_values[idx] = -0.28
            elif col == "is_time_pressure_60s" and val == 1:
                shap_values[idx] = -0.18
            elif col == "think_time_deviation" and abs(val) > 1.5:
                shap_values[idx] = -0.12 if val > 0 else 0.08
        return shap_values

    def explain(
        self,
        pos_feats: PositionFeatures,
        time_feats: TimeFeatures,
    ) -> ExplanationResult:
        """
        Generate feature importance narrative explanation for position & time state.
        """
        X = self.predictor.feature_vector_from_dtos(pos_feats, time_feats)

        if self._tree_explainer is not None:
            # Use real SHAP values from trained tree model
            try:
                raw_shap = self._tree_explainer.shap_values(X, check_additivity=False)
                shap_values = np.array(raw_shap[0] if isinstance(raw_shap, list) else raw_shap).flatten()
            except Exception as exc:
                logger.warning("SHAP calculation error, falling back to heuristic: %s", exc)
                shap_values = self._heuristic_shap(X)
        else:
            shap_values = self._heuristic_shap(X)

        impacts: list[FeatureImpact] = []
        for idx, col in enumerate(FEATURE_COLUMNS):
            val = float(X[col].iloc[0])
            s_val = float(shap_values[idx]) if idx < len(shap_values) else 0.0
            impacts.append(
                FeatureImpact(
                    feature_key=col,
                    display_name=FEATURE_NAME_MAP.get(col, col),
                    shap_value=s_val,
                    feature_value=val,
                )
            )

        # Sort positive and negative contributors
        positive = sorted(
            [imp for imp in impacts if imp.shap_value > 0.001],
            key=lambda x: x.shap_value,
            reverse=True,
        )[:3]
        negative = sorted(
            [imp for imp in impacts if imp.shap_value < -0.001],
            key=lambda x: x.shap_value,
        )[:3]

        # Build rich narrative with actual feature values
        def _val_str(imp: FeatureImpact) -> str:
            """Format the raw feature value for display."""
            col = imp.feature_key
            v = imp.feature_value
            if col in ("is_time_pressure_30s", "is_time_pressure_60s", "is_time_pressure_120s"):
                return "active" if v == 1 else "inactive"
            if col in ("think_time", "time_remaining", "running_avg_think_time"):
                return f"{v:.1f}s"
            if col in ("time_usage_ratio", "think_time_deviation"):
                return f"{v:.2f}"
            return f"{v:.1f}"

        narrative_parts = []
        if positive:
            top_pos = positive[0]
            narrative_parts.append(
                f"{top_pos.display_name} ({_val_str(top_pos)}) is helping (+{top_pos.shap_value * 100:.1f}%)"
            )
        if len(positive) > 1:
            narrative_parts.append(
                f"{positive[1].display_name} ({_val_str(positive[1])}) also contributing (+{positive[1].shap_value * 100:.1f}%)"
            )
        if negative:
            top_neg = negative[0]
            narrative_parts.append(
                f"{top_neg.display_name} ({_val_str(top_neg)}) is a risk factor ({top_neg.shap_value * 100:.1f}%)"
            )
        if len(negative) > 1:
            narrative_parts.append(
                f"{negative[1].display_name} ({_val_str(negative[1])}) also hurting ({negative[1].shap_value * 100:.1f}%)"
            )

        if not narrative_parts:
            summary = "Position evaluation is balanced — material is even and clock usage is normal."
        else:
            summary = ". ".join(narrative_parts) + "."

        return ExplanationResult(
            narrative_summary=summary,
            top_positive_factors=positive,
            top_negative_factors=negative,
        )
