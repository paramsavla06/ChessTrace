"""
Top-level API Router registry.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.router import api_v1_router
from app.core.config import API_V1_STR

api_router = APIRouter()
api_router.include_router(api_v1_router, prefix=API_V1_STR)
