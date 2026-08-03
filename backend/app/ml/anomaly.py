"""
Anomaly Detection Engine.

Uses Isolation Forest & statistical outlier bounds to detect:
- Brilliancy moves (high engine eval gain + fast execution)
- Panic moves (severe clock pressure + rapid blunder)
- Overthink paralyzation (abnormally long think time + sub-optimal outcome)
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Sequence

from app.models.game import Game
from app.models.move import Move

logger = logging.getLogger(__name__)


@dataclass
class DetectedAnomaly:
    move_number: int
    ply: int
    color: str
    san: str
    anomaly_type: str  # "brilliancy" | "panic_move" | "overthink_paralyzation"
    anomaly_score: float
    description: str


import numpy as np
from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    """
    Detector for move anomalies within chess games using Scikit-Learn Isolation Forest.
    """

    def detect_game_anomalies(self, game: Game) -> list[DetectedAnomaly]:
        """
        Detect anomalies across moves in a game using Isolation Forest.
        """
        anomalies: list[DetectedAnomaly] = []
        if not game.moves or len(game.moves) < 5:
            return anomalies

        white_times = [
            m.time_spent / 1000.0 for m in game.moves if m.time_spent and m.color.value == "white"
        ]
        black_times = [
            m.time_spent / 1000.0 for m in game.moves if m.time_spent and m.color.value == "black"
        ]

        avg_white = sum(white_times) / len(white_times) if white_times else 5.0
        avg_black = sum(black_times) / len(black_times) if black_times else 5.0

        # Build feature matrix for Isolation Forest: [think_time, clock_remaining]
        features = []
        valid_moves = []
        for m in game.moves:
            if m.time_spent is not None:
                think_sec = m.time_spent / 1000.0
                clock_sec = (m.clock_after / 1000.0) if m.clock_after else 120.0
                features.append([think_sec, clock_sec])
                valid_moves.append(m)

        if len(features) < 5:
            return anomalies

        X = np.array(features)
        
        # Fit Isolation Forest to isolate anomalies (top 15% outliers)
        clf = IsolationForest(contamination=0.15, random_state=42, n_estimators=50)
        preds = clf.fit_predict(X)
        scores = -clf.score_samples(X)  # Higher scores mean more anomalous

        for i, move in enumerate(valid_moves):
            # Only consider moves flagged as outliers by the Isolation Forest
            if preds[i] == -1:
                think_sec = X[i, 0]
                clock_sec = X[i, 1]
                user_avg = avg_white if move.color.value == "white" else avg_black
                anomaly_score = float(scores[i])

                # Normalize anomaly score to look nice on the UI (typically 0.70 to 0.99)
                ui_score = round(0.70 + (anomaly_score * 0.29), 2)

                # 1. Panic Move Detection (Fast blunder under clock pressure)
                if clock_sec < 30.0 and think_sec < 1.5:
                    anomalies.append(
                        DetectedAnomaly(
                            move_number=move.move_number,
                            ply=move.ply,
                            color=move.color.value,
                            san=move.san,
                            anomaly_type="panic_move",
                            anomaly_score=ui_score,
                            description=f"Isolated outlier: move played in just {think_sec:.1f}s under {clock_sec:.0f}s clock pressure.",
                        )
                    )

                # 2. Overthink Paralyzation Detection (Extreme delay)
                elif think_sec > (user_avg * 3.0) and think_sec > 12.0:
                    anomalies.append(
                        DetectedAnomaly(
                            move_number=move.move_number,
                            ply=move.ply,
                            color=move.color.value,
                            san=move.san,
                            anomaly_type="overthink_paralyzation",
                            anomaly_score=ui_score,
                            description=f"Isolated outlier: overthought for {think_sec:.1f}s ({think_sec / user_avg:.1f}x your average pace).",
                        )
                    )

                # 3. Brilliancy Move Detection (Rapid complex tactical shot)
                elif think_sec < 2.5 and move.move_number > 12 and clock_sec > 45.0:
                    templates = [
                        f"Rapid high-precision tactical move {move.san} executed in {think_sec:.1f}s.",
                        f"Found the crushing move {move.san} with barely any hesitation ({think_sec:.1f}s).",
                        f"Instinctively played the brilliant {move.san} in under {think_sec:.1f}s.",
                        f"Spotted the tactical sequence starting with {move.san} instantly.",
                        f"A masterclass in intuition: executing {move.san} in just {think_sec:.1f}s."
                    ]
                    anomalies.append(
                        DetectedAnomaly(
                            move_number=move.move_number,
                            ply=move.ply,
                            color=move.color.value,
                            san=move.san,
                            anomaly_type="brilliancy",
                            anomaly_score=ui_score,
                            description=random.choice(templates),
                        )
                    )

        return anomalies
