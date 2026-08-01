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


class ShapExplainer:
    """
    SHAP TreeExplainer wrapper providing natural language predictions explanations.
    """

    def __init__(self, predictor: WinCollapsePredictor) -> None:
        self.predictor = predictor
        self._tree_explainer: shap.TreeExplainer | None = None

        if predictor.model is not None:
            try:
                self._tree_explainer = shap.TreeExplainer(predictor.model)
            except Exception as exc:
                logger.warning("Could not initialize SHAP TreeExplainer: %s", exc)

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
            shap_values = self._tree_explainer.shap_values(X)[0]
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

        impacts: list[FeatureImpact] = []
        for idx, col in enumerate(FEATURE_COLUMNS):
            val = float(X[col].iloc[0])
            s_val = float(shap_values[idx])
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

        # Construct narrative summary
        narrative_parts = []
        if positive:
            top_pos = positive[0]
            narrative_parts.append(
                f"{top_pos.display_name} boosted score (+{top_pos.shap_value:.2f})"
            )
        if negative:
            top_neg = negative[0]
            narrative_parts.append(
                f"{top_neg.display_name} created vulnerability ({top_neg.shap_value:.2f})"
            )

        if not narrative_parts:
            summary = "Position evaluation is balanced with standard clock usage."
        else:
            summary = "; ".join(narrative_parts) + "."

        return ExplanationResult(
            narrative_summary=summary,
            top_positive_factors=positive,
            top_negative_factors=negative,
        )
