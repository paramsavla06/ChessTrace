"""
ChessTrace FastAPI Application Entry Point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import BACKEND_CORS_ORIGINS, PROJECT_NAME
from app.core.logging import setup_logging
from app.database.connection import engine
from app.database.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan events."""
    setup_logging()
    init_db(engine)
    yield


app = FastAPI(
    title=PROJECT_NAME,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware Configuration
if BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root application greeting endpoint."""
    return {"message": f"Welcome to {PROJECT_NAME} API. Access API docs at /docs."}
