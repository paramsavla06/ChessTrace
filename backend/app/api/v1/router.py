"""
API v1 Router registry.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import analysis, games, health, live_ws, upload

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(upload.router, tags=["Upload & Import"])
api_v1_router.include_router(games.router, tags=["Games"])
api_v1_router.include_router(analysis.router, tags=["Analysis & ML"])
api_v1_router.include_router(live_ws.router, tags=["Live WebSocket Spectating"])
