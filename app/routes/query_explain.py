"""Endpoint for safe, estimate-only query plans."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import engine
from app.query_explain import explain_select, validate_select_query

router = APIRouter(prefix="/queries", tags=["query plans"])


class ExplainRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000, description="One supported SELECT statement; not executed by DB-Pulse")


@router.post("/explain")
def explain_query(request: ExplainRequest) -> dict[str, Any]:
    safe_query = validate_select_query(request.query)
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured. Set the DB_* values in the project .env file.")
    try:
        with engine.connect() as connection:
            return explain_select(connection, safe_query)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to MySQL for query plan inspection. Check connectivity and permissions.") from None

