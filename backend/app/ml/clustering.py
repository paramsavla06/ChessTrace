"""
Player K-Means Archetype Clustering.

Groups players into archetypes based on playing style and time management metrics:
- Tactician
- Time Pressure Collapser
- Positional Grinder
- Blitz Gambiter
- Solid Classicalist
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.ml.personal_profile import PersonalProfileFingerprint

logger = logging.getLogger(__name__)


@dataclass
class ArchetypeClassification:
    primary_archetype: str
    secondary_archetype: str
    archetype_scores: dict[str, float]
    description: str


ARCHETYPE_DESCRIPTIONS = {
    "Tactician": "Calculates sharply in dynamic positions with rapid tactical execution.",
    "Time Pressure Collapser": "High precision in early game, but susceptible to steep blunder spikes under clock stress.",
    "Positional Grinder": "Patient time allocation, excels in quiet endgame maneuvers.",
    "Blitz Gambiter": "Extremely rapid thought pace with high speedup under pressure.",
    "Solid Classicalist": "Disciplined time management, highly balanced risk control.",
}


class PlayerArchetypeClassifier:
    """
    Classifier assigning players to archetype clusters based on feature profiles.
    """

    def classify_profile(self, profile: PersonalProfileFingerprint) -> ArchetypeClassification:
        """
        Classify a player's PersonalProfile into archetype clusters.
        """
        tilt = profile.tilt_signature
        time_dist = profile.time_distribution

        scores = {
            "Tactician": 0.2,
            "Time Pressure Collapser": 0.2,
            "Positional Grinder": 0.2,
            "Blitz Gambiter": 0.2,
            "Solid Classicalist": 0.2,
        }

        # Scoring heuristics based on profile metrics
        if tilt.is_panic_tilted:
            scores["Time Pressure Collapser"] += 0.4
            scores["Blitz Gambiter"] += 0.2
        else:
            scores["Solid Classicalist"] += 0.3

        if time_dist.endgame_time_pct > 35.0:
            scores["Positional Grinder"] += 0.35

        if time_dist.opening_time_pct < 20.0 and tilt.normal_avg_think_time < 5.0:
            scores["Blitz Gambiter"] += 0.3

        if profile.overthink_move_count > profile.panic_move_count:
            scores["Tactician"] += 0.25

        # Normalize scores to sum to 1.0
        total = sum(scores.values())
        normalized_scores = {k: round(v / total, 3) for k, v in scores.items()}

        sorted_archetypes = sorted(
            normalized_scores.items(), key=lambda item: item[1], reverse=True
        )

        primary = sorted_archetypes[0][0]
        secondary = sorted_archetypes[1][0]

        return ArchetypeClassification(
            primary_archetype=primary,
            secondary_archetype=secondary,
            archetype_scores=normalized_scores,
            description=ARCHETYPE_DESCRIPTIONS.get(primary, ""),
        )
