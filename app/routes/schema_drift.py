"""Read-only schema drift audit with explicit DB-Pulse-owned baselines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.database import engine
from app.schema_drift import compare_schema, index_columns

router = APIRouter(prefix="/schema-drift", tags=["schema drift"])
BASELINE_TABLE = "db_pulse_schema_baselines"


class BaselineRequest(BaseModel):
    confirm_replace: bool = False


def _configured_schema(connection: Any) -> str:
    schema = connection.execute(text("SELECT DATABASE()")).scalar_one()
    if not schema or engine is None or schema != engine.url.database:
        raise HTTPException(status_code=409, detail="Schema audit is restricted to the configured database.")
    return str(schema)


def _read_schema(connection: Any, schema: str) -> dict[str, dict[str, dict[str, Any]]]:
    rows = connection.execute(
        text("""
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                   COLUMN_DEFAULT, COLUMN_KEY, ORDINAL_POSITION
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema_name
              AND TABLE_NAME <> :excluded_table
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """),
        {"schema_name": schema, "excluded_table": BASELINE_TABLE},
    ).mappings().all()
    return index_columns(rows)


def _history_table_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(f"Schema baseline storage is unavailable. Initialize the DB-Pulse-owned {BASELINE_TABLE} table in db_pulse_meta as documented, then check SELECT and INSERT permissions."),
    )


@router.post("/baseline", status_code=201)
def save_baseline(request: BaselineRequest) -> dict[str, Any]:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured. Set the DB_* values in the project .env file.")
    if engine.url.database != "db_pulse_meta":
        raise HTTPException(status_code=409, detail="Schema baseline storage is restricted to db_pulse_meta.")
    try:
        with engine.begin() as connection:
            schema = _configured_schema(connection)
            existing = connection.execute(text(f"SELECT id FROM `{BASELINE_TABLE}` ORDER BY id DESC LIMIT 1")).first()
            if existing is not None and not request.confirm_replace:
                raise HTTPException(status_code=409, detail="A schema baseline already exists. Set confirm_replace=true to create a new approved baseline version.")
            metadata = _read_schema(connection, schema)
            result = connection.execute(
                text(f"INSERT INTO `{BASELINE_TABLE}` (created_at, schema_name, metadata_json) VALUES (:created_at, :schema_name, :metadata_json)"),
                {
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "schema_name": schema,
                    "metadata_json": json.dumps(metadata, sort_keys=True),
                },
            )
            baseline_id = result.lastrowid
    except HTTPException:
        raise
    except Exception:
        raise _history_table_error() from None
    return {"message": "Schema baseline saved.", "baseline_id": baseline_id, "schema": schema, "table_count": len(metadata), "column_count": sum(map(len, metadata.values()))}


@router.get("/audit")
def audit_schema() -> dict[str, Any]:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured. Set the DB_* values in the project .env file.")
    if engine.url.database != "db_pulse_meta":
        raise HTTPException(status_code=409, detail="Schema baseline storage is restricted to db_pulse_meta.")
    try:
        with engine.connect() as connection:
            schema = _configured_schema(connection)
            baseline = connection.execute(text(f"SELECT id, created_at, schema_name, metadata_json FROM `{BASELINE_TABLE}` ORDER BY id DESC LIMIT 1")).mappings().first()
            if baseline is None:
                raise HTTPException(status_code=404, detail="No approved schema baseline exists. Create one with POST /schema-drift/baseline.")
            if baseline["schema_name"] != schema:
                raise HTTPException(status_code=409, detail="The saved baseline belongs to a different configured schema.")
            current = _read_schema(connection, schema)
    except HTTPException:
        raise
    except Exception:
        raise _history_table_error() from None

    old_metadata = baseline["metadata_json"]
    if isinstance(old_metadata, str):
        old_metadata = json.loads(old_metadata)
    differences = compare_schema(old_metadata, current)
    audit_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "baseline_id": baseline["id"],
        "baseline_created_at": baseline["created_at"].replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "audited_at": audit_time,
        "schema": schema,
        "differences": differences,
        "note": "Metadata comparison reports structural differences; it cannot identify who made a change or whether it was unauthorized without separate MySQL audit logs.",
    }

