"""Read-only SQLAlchemy connection-pool status endpoint."""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.database import engine
from app.pool_monitor import build_pool_status, load_pool_thresholds

router = APIRouter(prefix="/pool", tags=["connection pool"])


@router.get("/status")
def pool_status() -> dict[str, Any]:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured. Set the DB_* values in the project .env file.")
    try:
        thresholds = load_pool_thresholds()
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid DB-Pulse pool threshold configuration. Check DB_PULSE_POOL_WARNING_PERCENT and DB_PULSE_POOL_CRITICAL_PERCENT.") from None
    try:
        return build_pool_status(engine.pool, thresholds)
    except Exception:
        raise HTTPException(status_code=503, detail="Could not inspect the application connection pool.") from None
