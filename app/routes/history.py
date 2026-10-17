"""Explicitly save and read DB-Pulse metric history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text

from app.database import engine
from app.metrics import collect_server_metrics
from app.models import MetricSnapshot

router = APIRouter(prefix="/history", tags=["history"])
HISTORY_DATABASE = "db_pulse_meta"


def _require_history_database() -> None:
    """Prevent history operations from connecting to a non-DB-Pulse database."""
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set the DB_* values in the project .env file.",
        )
    if engine.url.database != HISTORY_DATABASE:
        raise HTTPException(
            status_code=409,
            detail="Snapshot history is restricted to the DB-Pulse db_pulse_meta database.",
        )


def _utc_iso(value: datetime) -> str:
    """Format the naive UTC DATETIME stored in MySQL as an explicit UTC timestamp."""
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _row_to_dict(row: Any) -> dict[str, Any]:
    result = dict(row)
    if result.get("captured_at") is not None:
        result["captured_at"] = _utc_iso(result["captured_at"])
    if result.get("connection_utilization_percent") is not None:
        result["connection_utilization_percent"] = float(
            result["connection_utilization_percent"]
        )
    return result


@router.post("/snapshots", status_code=201)
def save_snapshot() -> dict[str, Any]:
    """Explicitly read the current counters and insert one DB-Pulse history row."""
    _require_history_database()
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        with engine.begin() as conn:
            selected_database = conn.execute(text("SELECT DATABASE()")).scalar_one()
            if selected_database != HISTORY_DATABASE:
                raise HTTPException(
                    status_code=409,
                    detail="Snapshot history is restricted to the DB-Pulse db_pulse_meta database.",
                )

            metrics = collect_server_metrics(conn)
            values = {
                "captured_at": captured_at,
                "connected_connections": metrics["connections"]["connected"],
                "running_connections": metrics["connections"]["running"],
                "max_connections": metrics["connections"]["max"],
                "connection_utilization_percent": metrics["connections"]["utilization_percent"],
                "server_uptime_seconds": metrics["server_uptime_seconds"],
                "queries_since_start": metrics["query_activity"]["queries_since_start"],
                "questions_since_start": metrics["query_activity"]["client_questions_since_start"],
                "server_metrics_available": metrics["server_metrics_available"],
                "metrics_warning": metrics["metrics_warning"],
            }
            result = conn.execute(MetricSnapshot.__table__.insert().values(**values))
            snapshot_id = result.inserted_primary_key[0]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not save the snapshot. Check MySQL connectivity and ensure the "
                "DB-Pulse history table is initialized with insert permission."
            ),
        ) from None

    return {
        "message": "Metric snapshot saved.",
        "snapshot": {
            "id": snapshot_id,
            **values,
            "captured_at": _utc_iso(captured_at),
            "connection_utilization_percent": (
                float(values["connection_utilization_percent"])
                if values["connection_utilization_percent"] is not None
                else None
            ),
        },
    }


@router.get("/snapshots")
def list_snapshots(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of recent snapshots (1-100)"),
) -> dict[str, Any]:
    """List recent snapshots from newest to oldest."""
    _require_history_database()

    try:
        with engine.connect() as conn:
            selected_database = conn.execute(text("SELECT DATABASE()")).scalar_one()
            if selected_database != HISTORY_DATABASE:
                raise HTTPException(
                    status_code=409,
                    detail="Snapshot history is restricted to the DB-Pulse db_pulse_meta database.",
                )
            rows = conn.execute(
                select(MetricSnapshot.__table__)
                .order_by(
                    MetricSnapshot.captured_at.desc(),
                    MetricSnapshot.id.desc(),
                )
                .limit(limit)
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not read snapshot history. Check MySQL connectivity and ensure the "
                "DB-Pulse history table exists and is readable."
            ),
        ) from None

    snapshots = [_row_to_dict(row) for row in rows]
    return {"count": len(snapshots), "limit": limit, "snapshots": snapshots}
