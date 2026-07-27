"""
Schema representing the result of analyzing one or more chess games.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AnalysisSummary:
    """
    Summary returned by AnalysisService after completing an analysis.

    Responsibilities
    ----------------
    - Report analysis statistics
    - Provide service-level feedback

    Non-responsibilities
    --------------------
    - Database operations
    - Engine evaluation
    - Feature extraction
    """

    processed: int
    analyzed: int
    skipped: int
    failed: int

    total_positions: int
    total_evaluations: int
