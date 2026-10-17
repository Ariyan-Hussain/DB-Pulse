"""Read-only view of current InnoDB transactions and lock waits."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database import engine

router = APIRouter()

ACTIVE_TRANSACTIONS_QUERY = text(
    "SELECT trx_id, trx_state, trx_started, trx_wait_started, "
    "trx_mysql_thread_id, trx_rows_locked, trx_rows_modified "
    "FROM information_schema.innodb_trx ORDER BY trx_started"
)
LOCK_WAITS_QUERY = text(
    "SELECT w.REQUESTING_ENGINE_TRANSACTION_ID AS waiting_transaction_id, "
    "waiting_trx.trx_mysql_thread_id AS waiting_thread_id, "
    "waiting_trx.trx_state AS waiting_state, "
    "waiting_trx.trx_started AS waiting_started, "
    "w.BLOCKING_ENGINE_TRANSACTION_ID AS blocking_transaction_id, "
    "blocking_trx.trx_mysql_thread_id AS blocking_thread_id, "
    "blocking_trx.trx_state AS blocking_state, "
    "blocking_trx.trx_started AS blocking_started, "
    "waiting_lock.OBJECT_SCHEMA AS schema_name, "
    "waiting_lock.OBJECT_NAME AS table_name, "
    "waiting_lock.INDEX_NAME AS index_name, "
    "waiting_lock.LOCK_TYPE AS waiting_lock_type, "
    "waiting_lock.LOCK_MODE AS waiting_lock_mode, "
    "blocking_lock.LOCK_MODE AS blocking_lock_mode "
    "FROM performance_schema.data_lock_waits AS w "
    "LEFT JOIN information_schema.innodb_trx AS waiting_trx "
    "ON waiting_trx.trx_id = w.REQUESTING_ENGINE_TRANSACTION_ID "
    "LEFT JOIN information_schema.innodb_trx AS blocking_trx "
    "ON blocking_trx.trx_id = w.BLOCKING_ENGINE_TRANSACTION_ID "
    "LEFT JOIN performance_schema.data_locks AS waiting_lock "
    "ON waiting_lock.ENGINE = w.ENGINE "
    "AND waiting_lock.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID "
    "LEFT JOIN performance_schema.data_locks AS blocking_lock "
    "ON blocking_lock.ENGINE = w.ENGINE "
    "AND blocking_lock.ENGINE_LOCK_ID = w.BLOCKING_ENGINE_LOCK_ID "
    "WHERE waiting_lock.OBJECT_SCHEMA = DATABASE()"
)


@router.get("/locks")
def locks() -> dict[str, Any]:
    """Return current transactions and, when permitted, current lock waits."""
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured. Set the DB_* values in the project .env file.",
        )

    try:
        with engine.connect() as conn:
            transactions = [
                dict(row)
                for row in conn.execute(ACTIVE_TRANSACTIONS_QUERY).mappings().all()
            ]
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not read current InnoDB transactions. Check MySQL connectivity and permissions.",
        ) from None

    try:
        with engine.connect() as conn:
            waits = [dict(row) for row in conn.execute(LOCK_WAITS_QUERY).mappings().all()]
        available = True
        message = (
            "Current lock waits are shown below."
            if waits
            else "No current lock waits were visible when this endpoint was checked."
        )
    except Exception:
        waits = []
        available = False
        message = (
            "Transaction details are available, but lock-wait details could not be read. "
            "The MySQL account may need access to Performance Schema lock tables."
        )

    return {
        "active_transactions": transactions,
        "lock_waits": waits,
        "lock_waits_available": available,
        "message": message,
        "scope_note": "This is a current snapshot of transactions and waits, not a history of past deadlocks.",
    }
