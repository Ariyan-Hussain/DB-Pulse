"""Shared read-only collection of MySQL server status counters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

STATUS_QUERY = text(
    "SHOW GLOBAL STATUS WHERE Variable_name IN "
    "('Threads_connected', 'Threads_running', 'Uptime', 'Queries', 'Questions')"
)
MAX_CONNECTIONS_QUERY = text("SELECT @@GLOBAL.max_connections")


def _number(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def collect_server_metrics(connection: Any) -> dict[str, Any]:
    """Read optional MySQL counters; return null metrics instead of raising on denied status access."""
    try:
        status = {
            str(name).lower(): value
            for name, value in connection.execute(STATUS_QUERY).all()
        }
        max_connections = _number(connection.execute(MAX_CONNECTIONS_QUERY).scalar_one())
        warning = None
    except Exception:
        status = {}
        max_connections = None
        warning = "MySQL server counters are unavailable; check access to global status."

    connected = _number(status.get("threads_connected"))
    running = _number(status.get("threads_running"))
    uptime = _number(status.get("uptime"))
    queries = _number(status.get("queries"))
    questions = _number(status.get("questions"))
    utilization = (
        round(connected / max_connections * 100, 2)
        if connected is not None and max_connections is not None and max_connections > 0
        else None
    )
    return {
        "connections": {
            "connected": connected,
            "running": running,
            "max": max_connections,
            "utilization_percent": utilization,
        },
        "server_uptime_seconds": uptime,
        "query_activity": {
            "queries_since_start": queries,
            "client_questions_since_start": questions,
            "average_queries_per_second_since_start": (
                round(queries / uptime, 3)
                if queries is not None and uptime is not None and uptime > 0
                else None
            ),
            "note": "Counters are cumulative since MySQL started; the rate is a lifetime average, not an instantaneous rate.",
        },
        "server_metrics_available": warning is None,
        "metrics_warning": warning,
    }
