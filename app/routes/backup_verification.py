"""Non-executing backup file preflight endpoint."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backup_verification import load_settings, preflight_backup

router = APIRouter(prefix="/backups", tags=["backup preflight"])


class BackupPreflightRequest(BaseModel):
    backup_filename: str = Field(min_length=1, max_length=255, description="Filename inside DB_PULSE_BACKUP_DIR; never a path")


@router.post("/verify")
def verify_backup(request: BackupPreflightRequest) -> dict[str, Any]:
    try:
        settings = load_settings()
    except ValueError:
        raise HTTPException(status_code=503, detail="Backup preflight is not configured. Set a valid DB_PULSE_BACKUP_DIR and documented size/timeout limits.") from None
    try:
        return preflight_backup(request.backup_filename, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Backup file or configured backup directory was not found.") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except OSError:
        raise HTTPException(status_code=503, detail="Backup file could not be inspected. Check local file permissions.") from None
