"""
Player Similarity Network Engine.

Computes Cosine Similarity across player feature vectors to connect players
with similar playing styles, thought paces, and time degradation signatures.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Sequence

from app.ml.personal_profile import PersonalProfileFingerprint

logger = logging.getLogger(__name__)


@dataclass
class SimilarPlayerMatch:
    username: str
    similarity_score_pct: float
    shared_traits: list[str]


class PlayerSimilarityEngine:
    """
    Engine calculating Cosine Similarity across player fingerprint vectors.
    """

    def __init__(self) -> None:
        # Reference dataset of known player style fingerprints
        self.reference_database: dict[str, dict[str, float]] = {
            "MagnusCarlsen": {"avg_think": 6.5, "tilt": 0.05, "endgame_time": 0.40, "panic_ratio": 0.02},
            "HikaruNakamura": {"avg_think": 3.2, "tilt": 0.12, "endgame_time": 0.25, "panic_ratio": 0.05},
            "DanielNaroditsky": {"avg_think": 4.1, "tilt": 0.15, "endgame_time": 0.30, "panic_ratio": 0.04},
            "FabianoCaruana": {"avg_think": 8.2, "tilt": 0.08, "endgame_time": 0.35, "panic_ratio": 0.03},
            "AlirezaFirouzja": {"avg_think": 3.8, "tilt": 0.22, "endgame_time": 0.28, "panic_ratio": 0.08},
        }

    def _profile_to_vector(self, profile: PersonalProfileFingerprint) -> dict[str, float]:
        total_moves = max(1, len(profile.accuracy_vs_clock))
        return {
            "avg_think": profile.tilt_signature.normal_avg_think_time,
            "tilt": profile.tilt_signature.tilt_speedup_percentage / 100.0,
            "endgame_time": profile.time_distribution.endgame_time_pct / 100.0,
            "panic_ratio": profile.panic_move_count / (total_moves * 20.0),
        }

    def _cosine_similarity(self, vec1: dict[str, float], vec2: dict[str, float]) -> float:
        keys = set(vec1.keys()).union(vec2.keys())
        dot = sum(vec1.get(k, 0.0) * vec2.get(k, 0.0) for k in keys)
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    def find_similar_players(
        self,
        profile: PersonalProfileFingerprint,
        top_n: int = 3,
    ) -> list[SimilarPlayerMatch]:
        """
        Find top N most similar player profiles based on Cosine Similarity.
        """
        user_vec = self._profile_to_vector(profile)
        matches: list[SimilarPlayerMatch] = []

        for name, ref_vec in self.reference_database.items():
            if name.lower() == profile.player_name.lower():
                continue

            sim = self._cosine_similarity(user_vec, ref_vec)
            score_pct = round(min(99.9, max(50.0, sim * 100.0)), 1)

            traits: list[str] = []
            if abs(user_vec["avg_think"] - ref_vec["avg_think"]) < 2.0:
                traits.append("Similar thought pace")
            if abs(user_vec["endgame_time"] - ref_vec["endgame_time"]) < 0.1:
                traits.append("Matching endgame time allocation")
            if abs(user_vec["tilt"] - ref_vec["tilt"]) < 0.1:
                traits.append("Resilient tilt signature under pressure")

            matches.append(
                SimilarPlayerMatch(
                    username=name,
                    similarity_score_pct=score_pct,
                    shared_traits=traits if traits else ["General playing style match"],
                )
            )

        matches.sort(key=lambda m: m.similarity_score_pct, reverse=True)
        return matches[:top_n]
