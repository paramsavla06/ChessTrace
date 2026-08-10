"""
PGN and game import endpoints.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.schemas.import_summary import ImportSummary
from app.services.import_services import ImportService
from app.services.lichess_service import LichessService

router = APIRouter()


@router.post("/upload/pgn", response_model=ImportSummary, summary="Upload PGN file")
def upload_pgn_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportSummary:
    """
    Upload a PGN file and import contained chess games into the database.
    """
    if not file.filename or not file.filename.lower().endswith((".pgn", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be a .pgn file.")

    try:
        content = file.file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pgn") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        service = ImportService(db)
        summary = service.import_file(tmp_path)
        tmp_path.unlink(missing_ok=True)

        return summary

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed importing PGN file: {exc}") from exc


@router.post("/upload/lichess/{username}", response_model=ImportSummary, summary="Fetch Lichess user games")
def fetch_lichess_games(
    username: str,
    max_games: int = 500,
    db: Session = Depends(get_db),
) -> ImportSummary:
    """
    Fetch and import public games with clock data for a Lichess user.
    """
    try:
        service = LichessService(db)
        return service.import_user_games(username, max_games=max_games)
    except ValueError as exc:
        status_code = 429 if "rate limit" in str(exc).lower() else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed fetching games for Lichess user '{username}': {exc}"
        ) from exc
