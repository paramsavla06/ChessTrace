"""
Health check endpoints.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter

from app.ml.collapse_model import get_model_diagnostics

router = APIRouter()


@router.get("/health", summary="System Health Check")
def health_check() -> dict[str, Any]:
    """Return API health status along with authoritative ML engine diagnostics."""
    diag = get_model_diagnostics()
    return {
        "status": "ok",
        "service": "ChessTrace API",
        "ml_engine": {
            "version": diag["active_model_version"],
            "authoritative_v2": diag["authoritative_v2"],
            "artifact_path": diag["artifact_path"],
            "loaded": diag["model_loaded"],
        },
    }
