"""Read-only server and configured-schema monitoring endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database import engine
from app.metrics import collect_server_metrics

router = APIRouter()


@router.get("/monitoring")
def monitoring() -> dict[str, Any]:
    """Return database identity, schema size, and available server counters."""
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set the DB_* values in the project .env file.",
        )

    try:
        with engine.connect() as conn:
            version, schema = conn.execute(text("SELECT VERSION(), DATABASE()")).one()
            table_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE()"
                )
            ).scalar_one()
            size_bytes = conn.execute(
                text(
                    "SELECT COALESCE(SUM(data_length + index_length), 0) "
                    "FROM information_schema.tables WHERE table_schema = DATABASE()"
                )
            ).scalar_one()
            server_metrics = collect_server_metrics(conn)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not read monitoring data from the configured database. "
                "Check that MySQL is running and the account can read this schema."
            ),
        ) from None

    return {
        "status": "connected",
        "version": version,
        "database": schema,
        "table_count": table_count,
        "approx_size_bytes": size_bytes,
        **server_metrics,
    }
