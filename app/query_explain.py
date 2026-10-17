"""Safe, estimate-only MySQL EXPLAIN support."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

MAX_QUERY_LENGTH = 5_000
_FORBIDDEN_TOKENS = re.compile(
    r"\b(?:INTO|OUTFILE|DUMPFILE|PROCEDURE|CALL|LOAD_FILE|SLEEP|BENCHMARK|"
    r"GET_LOCK|RELEASE_LOCK|IS_FREE_LOCK|IS_USED_LOCK|FOR|LOCK|UNLOCK)\b|"
    r"@|:=",
    re.IGNORECASE,
)
_QUALIFIED_IDENTIFIER = re.compile(r"\b[A-Za-z_][\w$]*\s*\.\s*[A-Za-z_][\w$]*\b")


def validate_select_query(query: str) -> str:
    """Accept a deliberately small, single-statement SELECT subset."""
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty.")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=422, detail=f"Query must be at most {MAX_QUERY_LENGTH} characters.")
    candidate = query.strip()
    if "`" in candidate:
        raise HTTPException(status_code=422, detail="Quoted identifiers are outside the supported query subset.")
    if any(token in candidate for token in (";", "--", "#", "/*", "*/")):
        # A single optional final semicolon is harmless; all comments and internal
        # separators are rejected so input cannot append another statement.
        if candidate.endswith(";") and candidate.count(";") == 1 and not any(
            marker in candidate for marker in ("--", "#", "/*", "*/")
        ):
            candidate = candidate[:-1].rstrip()
        else:
            raise HTTPException(status_code=422, detail="Submit one SELECT statement without SQL comments or multiple statements.")
    if not re.match(r"^SELECT\b", candidate, re.IGNORECASE):
        raise HTTPException(status_code=422, detail="Only SELECT statements are supported; CTEs and other SQL forms are not currently supported.")
    if _FORBIDDEN_TOKENS.search(candidate) or _QUALIFIED_IDENTIFIER.search(candidate):
        raise HTTPException(status_code=422, detail="This SELECT uses a construct outside the supported safe query subset.")
    return candidate


def _plan_value(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def explain_select(connection: Any, query: str) -> dict[str, Any]:
    """Run EXPLAIN (never EXPLAIN ANALYZE) for a validated SELECT."""
    safe_query = validate_select_query(query)
    try:
        rows = connection.execute(text("EXPLAIN " + safe_query)).mappings().all()
    except DBAPIError as exc:
        code = exc.orig.args[0] if getattr(exc, "orig", None) is not None and getattr(exc.orig, "args", ()) else None
        if code in {1044, 1045, 1142, 1227}:
            raise HTTPException(status_code=403, detail="The MySQL account is not permitted to inspect this query plan.") from None
        raise HTTPException(status_code=422, detail="MySQL could not produce a plan for this SELECT. Check its syntax and supported constructs.") from None
    except Exception:
        raise HTTPException(status_code=422, detail="MySQL could not produce a plan for this SELECT. Check its syntax and supported constructs.") from None

    plan = []
    warnings = []
    for row in rows:
        item = {str(key): _plan_value(value) for key, value in dict(row).items()}
        plan.append(item)
        access = str(item.get("type") or "").upper()
        if access == "ALL":
            warnings.append("A plan step uses a full table scan; check whether suitable indexes are appropriate.")
        if item.get("rows") is not None:
            warnings.append("Estimated row counts are optimizer estimates, not measured rows or runtime.")
        if "Using temporary" in str(item.get("Extra") or ""):
            warnings.append("The plan indicates a temporary table may be used.")
    warnings = list(dict.fromkeys(warnings))
    return {
        "plan": plan,
        "warnings": warnings,
        "read_only": True,
        "explain_analyze_used": False,
        "limitations": [
            "EXPLAIN reports optimizer estimates and does not guarantee actual runtime performance.",
            "Plan fields vary by MySQL version, query shape, and account visibility.",
            "Only a single SELECT without comments, CTEs, or unsupported constructs is accepted.",
        ],
    }

