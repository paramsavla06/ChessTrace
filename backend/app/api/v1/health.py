"""
Health check endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="System Health Check")
def health_check() -> dict[str, str]:
    """Return API health status."""
    return {"status": "ok", "service": "ChessTrace API"}
