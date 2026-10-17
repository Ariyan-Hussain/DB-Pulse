"""Read-only health alert endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text

from app.alerting import evaluate_alerts, load_alert_thresholds, threshold_summary
from app.database import engine
from app.metrics import collect_server_metrics
from app.models import MetricSnapshot

router = APIRouter(tags=["alerts"])
HISTORY_DATABASE = "db_pulse_meta"


@router.get("/alerts")
def alerts() -> dict[str, Any]:
    """Evaluate current metrics and existing history without writing a snapshot."""
    try:
        thresholds = load_alert_thresholds()
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=(
                "Invalid DB-Pulse alert threshold configuration. Check the documented "
                "DB_PULSE_ALERT_* values and their allowed ranges."
            ),
        ) from None

    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set the DB_* values in the project .env file.",
        )
    if engine.url.database != HISTORY_DATABASE:
        raise HTTPException(
            status_code=409,
            detail="Alert history comparison is restricted to the DB-Pulse db_pulse_meta database.",
        )

    history_available = True
    previous_snapshot = None
    try:
        with engine.connect() as connection:
            selected_database = connection.execute(text("SELECT DATABASE()")).scalar_one()
            if selected_database != HISTORY_DATABASE:
                raise HTTPException(
                    status_code=409,
                    detail="Alert history comparison is restricted to the DB-Pulse db_pulse_meta database.",
                )
            current_metrics = collect_server_metrics(connection)
            try:
                previous_snapshot = connection.execute(
                    select(MetricSnapshot.__table__)
                    .order_by(
                        MetricSnapshot.captured_at.desc(),
                        MetricSnapshot.id.desc(),
                    )
                    .limit(1)
                ).mappings().first()
            except Exception:
                # Current health alerts still work if history has not been
                # initialized or the account cannot read its table.
                history_available = False
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not read current MySQL monitoring data. Check database connectivity and permissions.",
        ) from None

    evaluated = evaluate_alerts(
        current_metrics,
        thresholds,
        previous_snapshot,
        history_available=history_available,
    )
    return {
        "status": "evaluated",
        "alert_count": len(evaluated),
        "history_comparison": (
            "available" if previous_snapshot is not None and history_available
            else "no_snapshots" if history_available
            else "unavailable"
        ),
        "thresholds": threshold_summary(thresholds),
        "alerts": evaluated,
        "read_only": True,
        "snapshot_saved": False,
    }
