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


import numpy as np
from sklearn.cluster import KMeans

class PlayerArchetypeClassifier:
    """
    Classifier assigning players to archetype clusters based on feature profiles using K-Means.
    """

    def __init__(self) -> None:
        # Reference GM seed dataset to anchor the 5 clusters
        # Features: [norm_think_pace, tilt_factor, endgame_alloc, panic_ratio]
        self.seed_data = {
            "Solid Classicalist": [0.45, 0.05, 0.40, 0.02],
            "Blitz Gambiter": [0.20, 0.12, 0.25, 0.05],
            "Tactician": [0.25, 0.15, 0.30, 0.04],
            "Positional Grinder": [0.65, 0.08, 0.35, 0.03],
            "Time Pressure Collapser": [0.22, 0.25, 0.28, 0.08],
        }
        self.archetype_names = list(self.seed_data.keys())
        self.X_train = np.array(list(self.seed_data.values()))
        
        # Fit K-Means on the seed data
        self.kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
        self.kmeans.fit(self.X_train)
        
        # Map cluster labels back to archetype names
        self.cluster_to_name = {}
        for i, label in enumerate(self.kmeans.labels_):
            self.cluster_to_name[label] = self.archetype_names[i]

    def _extract_vector(self, profile: PersonalProfileFingerprint) -> np.ndarray:
        norm_think = max(0.0, min(1.0, profile.tilt_signature.normal_avg_think_time / 15.0))
        tilt = max(0.0, min(1.0, (profile.tilt_signature.tilt_speedup_percentage + 50.0) / 150.0))
        endgame = max(0.0, min(1.0, profile.time_distribution.endgame_time_pct / 100.0))
        panic = max(0.0, min(1.0, profile.panic_move_count / max(1, profile.total_games_analyzed * 10)))
        return np.array([norm_think, tilt, endgame, panic])

    def classify_profile(self, profile: PersonalProfileFingerprint) -> ArchetypeClassification:
        """
        Classify a player's PersonalProfile into archetype clusters using Scikit-Learn KMeans.
        """
        user_vec = self._extract_vector(profile)
        
        # Predict primary cluster
        cluster_id = self.kmeans.predict(user_vec.reshape(1, -1))[0]
        primary_archetype = self.cluster_to_name[cluster_id]
        
        # Compute distances to all centroids to get normalized probability scores and secondary archetype
        distances = self.kmeans.transform(user_vec.reshape(1, -1))[0]
        
        # Convert distances to similarity scores (closer = higher score)
        # Add small epsilon to avoid division by zero
        similarities = 1.0 / (distances + 1e-6)
        total_sim = np.sum(similarities)
        normalized_scores = {
            self.cluster_to_name[i]: round(float(sim / total_sim), 3)
            for i, sim in enumerate(similarities)
        }
        
        sorted_archetypes = sorted(
            normalized_scores.items(), key=lambda item: item[1], reverse=True
        )
        
        secondary_archetype = sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else primary_archetype

        return ArchetypeClassification(
            primary_archetype=primary_archetype,
            secondary_archetype=secondary_archetype,
            archetype_scores=normalized_scores,
            description=ARCHETYPE_DESCRIPTIONS.get(primary_archetype, ""),
        )
