"""Admin utilities: database export / import (SQLite only)."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


def _sqlite_path() -> Path:
    """Resolve the SQLite database file path from DATABASE_URL."""
    url = settings.database_url
    if not url.startswith("sqlite"):
        raise HTTPException(
            status_code=400,
            detail="Database export/import is only supported when using SQLite.",
        )
    # sqlite:///./crm.db  → relative   sqlite:////abs/path/crm.db → absolute
    raw = url.split("///", 1)[-1]
    p = Path(raw)
    if not p.is_absolute():
        # Resolve relative to the backend working directory
        p = Path.cwd() / p
    return p.resolve()


@router.get("/db/export", summary="Download the SQLite database file")
def export_database() -> FileResponse:
    db_path = _sqlite_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found.")

    # Copy to a temp file so the live DB isn't held open during download
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    shutil.copy2(db_path, tmp.name)

    return FileResponse(
        path=tmp.name,
        media_type="application/octet-stream",
        filename="crm_export.db",
        background=None,
    )


@router.post("/db/import", summary="Replace the SQLite database with an uploaded file")
async def import_database(file: UploadFile) -> dict[str, str]:
    db_path = _sqlite_path()

    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Please upload a .db file.")

    # Write to a temp file first, validate it's a SQLite DB, then swap
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    try:
        contents = await file.read()
        if len(contents) < 16:
            raise HTTPException(status_code=400, detail="File is too small to be a valid SQLite database.")
        # SQLite magic header: "SQLite format 3\000"
        if contents[:16] != b"SQLite format 3\x00":
            raise HTTPException(status_code=400, detail="File does not appear to be a valid SQLite database.")
        tmp.write(contents)
        tmp.flush()
        tmp.close()

        # Backup current DB then replace
        backup_path = str(db_path) + ".bak"
        if db_path.exists():
            shutil.copy2(db_path, backup_path)
        shutil.move(tmp.name, db_path)
    except HTTPException:
        os.unlink(tmp.name)
        raise
    except Exception as exc:
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    return {"status": "ok", "message": "Database imported successfully. Restart the app to apply changes."}
