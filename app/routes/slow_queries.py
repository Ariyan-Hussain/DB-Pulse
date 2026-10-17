"""Heuristic-only analysis of SQL text and slow-query log snippets."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas import AnalyzeRequest

router = APIRouter()
STATEMENT_PATTERN = re.compile(r"\b(SELECT|UPDATE|DELETE|INSERT)\b", re.IGNORECASE)
LOG_METRIC_PATTERN = re.compile(
    r"\b(Query_time|Lock_time|Rows_sent|Rows_examined):\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


def _log_metrics(query_text: str) -> dict[str, int | float]:
    metrics: dict[str, int | float] = {}
    for key, raw_value in LOG_METRIC_PATTERN.findall(query_text):
        value: int | float = float(raw_value) if "." in raw_value else int(raw_value)
        metrics[key.lower()] = value
    return metrics


@router.post("/slow-queries/analyze")
def analyze(body: AnalyzeRequest) -> dict[str, Any]:
    """Return explainable heuristics; never executes or plans user SQL."""
    query_text = body.query.strip()
    if not query_text or not STATEMENT_PATTERN.search(query_text):
        raise HTTPException(
            status_code=422,
            detail="Provide SQL text or a slow-query log snippet containing SELECT, UPDATE, DELETE, or INSERT.",
        )

    statement_match = STATEMENT_PATTERN.search(query_text)
    assert statement_match is not None
    statement_type = statement_match.group(1).upper()
    recommendations: list[dict[str, str]] = []

    if re.search(r"\bSELECT\s+\*", query_text, re.IGNORECASE):
        recommendations.append(
            {
                "pattern": "SELECT *",
                "suggestion": "List only the columns the application needs.",
                "reason": "Selecting every column can increase disk reads, memory use, and network traffic.",
            }
        )
    if statement_type == "SELECT" and not re.search(r"\bWHERE\b", query_text, re.IGNORECASE):
        recommendations.append(
            {
                "pattern": "SELECT without WHERE",
                "suggestion": "Check whether the query needs to read every row.",
                "reason": "A query without a filter may scan a large table; this depends on the intended result.",
            }
        )
    if re.search(r"\b(FROM|JOIN)\s+[\w.`]+", query_text, re.IGNORECASE):
        recommendations.append(
            {
                "pattern": "Index and plan review",
                "suggestion": "Use EXPLAIN in your SQL client and review indexes on filter and join columns.",
                "reason": "The text alone cannot show which access path MySQL chose or whether an index would help.",
            }
        )

    metrics = _log_metrics(query_text)
    examined = metrics.get("rows_examined")
    sent = metrics.get("rows_sent")
    examined_to_sent_ratio = (
        round(float(examined) / max(float(sent), 1), 2)
        if examined is not None and sent is not None and float(sent) > 0
        else None
    )
    if examined_to_sent_ratio is not None and examined_to_sent_ratio >= 10:
        recommendations.append(
            {
                "pattern": "Many rows examined per row returned",
                "suggestion": "Review the filter and join columns with EXPLAIN; consider whether a suitable index exists.",
                "reason": "The supplied log reports at least ten rows examined per row sent. This is a clue, not proof of a missing index.",
            }
        )

    if metrics:
        performance_note = (
            "Some counters were read from the supplied slow-query log text. "
            "This endpoint does not collect live Performance Schema data."
        )
    else:
        performance_note = (
            "No runtime performance counters were found in the input. This is a text-only heuristic review; "
            "use a slow-query log or EXPLAIN in MySQL for evidence about actual execution."
        )

    return {
        "statement_type": statement_type,
        "recommendations": recommendations,
        "performance_data": {
            **metrics,
            "rows_examined_to_rows_sent_ratio": examined_to_sent_ratio,
        },
        "performance_data_available": bool(metrics),
        "performance_note": performance_note,
        "safety_note": "The submitted text was not executed. Suggestions are educational checks, not guaranteed fixes.",
    }
