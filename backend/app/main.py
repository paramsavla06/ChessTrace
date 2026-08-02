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

# Mount websocket directly on app to avoid APIRouter prefix/nesting bugs
from app.api.v1 import live_ws
app.include_router(live_ws.router, prefix="/api/v1")

from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err_msg = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"Unhandled Exception: {err_msg}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": err_msg},
        headers={"Access-Control-Allow-Origin": "*"}
    )
@app.get("/")
def root() -> dict[str, str]:
    """Root application greeting endpoint."""
    return {"message": f"Welcome to {PROJECT_NAME} API. Access API docs at /docs."}
