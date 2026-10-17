"""Threshold configuration and pure health-alert evaluation rules."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class AlertThresholds:
    connection_warning_percent: float = 75.0
    connection_critical_percent: float = 90.0
    near_max_warning_remaining: int = 10
    near_max_critical_remaining: int = 2
    query_rate_warning_per_minute: float = 600.0


def load_alert_thresholds(environ: Mapping[str, str] | None = None) -> AlertThresholds:
    """Read and validate supported thresholds; errors never include raw env values."""
    source = os.environ if environ is None else environ
    try:
        thresholds = AlertThresholds(
            connection_warning_percent=float(
                source.get("DB_PULSE_ALERT_CONNECTION_WARNING_PERCENT", "75")
            ),
            connection_critical_percent=float(
                source.get("DB_PULSE_ALERT_CONNECTION_CRITICAL_PERCENT", "90")
            ),
            near_max_warning_remaining=int(
                source.get("DB_PULSE_ALERT_NEAR_MAX_WARNING_REMAINING", "10")
            ),
            near_max_critical_remaining=int(
                source.get("DB_PULSE_ALERT_NEAR_MAX_CRITICAL_REMAINING", "2")
            ),
            query_rate_warning_per_minute=float(
                source.get("DB_PULSE_ALERT_QUERY_RATE_WARNING_PER_MINUTE", "600")
            ),
        )
    except (TypeError, ValueError):
        raise ValueError("Alert thresholds must use valid numeric values.") from None

    percent_values = (
        thresholds.connection_warning_percent,
        thresholds.connection_critical_percent,
    )
    if (
        not all(math.isfinite(value) for value in percent_values)
        or not 0 < thresholds.connection_warning_percent
        < thresholds.connection_critical_percent
        <= 100
    ):
        raise ValueError(
            "Connection thresholds must satisfy 0 < warning < critical <= 100."
        )
    if (
        thresholds.near_max_critical_remaining < 0
        or thresholds.near_max_warning_remaining
        <= thresholds.near_max_critical_remaining
    ):
        raise ValueError(
            "Remaining-connection thresholds must satisfy warning > critical >= 0."
        )
    if (
        not math.isfinite(thresholds.query_rate_warning_per_minute)
        or thresholds.query_rate_warning_per_minute <= 0
    ):
        raise ValueError("The query-rate threshold must be a positive finite number.")
    return thresholds


def threshold_summary(thresholds: AlertThresholds) -> dict[str, float | int]:
    """Return effective non-secret threshold values for transparent alert results."""
    return {
        "connection_warning_percent": thresholds.connection_warning_percent,
        "connection_critical_percent": thresholds.connection_critical_percent,
        "near_max_warning_remaining": thresholds.near_max_warning_remaining,
        "near_max_critical_remaining": thresholds.near_max_critical_remaining,
        "query_rate_warning_per_minute": thresholds.query_rate_warning_per_minute,
    }


def _alert(
    code: str,
    severity: str,
    title: str,
    metric: str,
    observed_value: Any,
    threshold: Any,
    explanation: str,
    suggested_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "metric": metric,
        "observed_value": observed_value,
        "threshold": threshold,
        "explanation": explanation,
        "suggested_action": suggested_action,
    }


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def evaluate_alerts(
    metrics: Mapping[str, Any],
    thresholds: AlertThresholds,
    previous_snapshot: Mapping[str, Any] | None,
    *,
    history_available: bool = True,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build explanatory alerts from current shared metrics and one stored snapshot."""
    alerts: list[dict[str, Any]] = []
    connections = metrics.get("connections") or {}
    query_activity = metrics.get("query_activity") or {}
    expected = {
        "connected_connections": connections.get("connected"),
        "running_connections": connections.get("running"),
        "max_connections": connections.get("max"),
        "server_uptime_seconds": metrics.get("server_uptime_seconds"),
        "queries_since_start": query_activity.get("queries_since_start"),
        "questions_since_start": query_activity.get("client_questions_since_start"),
    }
    available = [name for name, value in expected.items() if value is not None]
    missing = [name for name, value in expected.items() if value is None]

    if not available or not metrics.get("server_metrics_available", False):
        alerts.append(
            _alert(
                "MONITORING_METRICS_UNAVAILABLE",
                "warning",
                "MySQL monitoring counters are unavailable",
                "available_server_metrics",
                f"{len(available)} of {len(expected)}",
                "At least 1 current server metric",
                "DB-Pulse could not read the expected MySQL status counters, so connection and query health cannot be fully evaluated.",
                "Check MySQL global status permissions and confirm the server is reachable. No metric values were inferred.",
            )
        )
    elif missing:
        alerts.append(
            _alert(
                "MONITORING_METRICS_INCOMPLETE",
                "info",
                "Some MySQL monitoring metrics are missing",
                "available_server_metrics",
                f"{len(available)} of {len(expected)}",
                f"{len(expected)} available metrics",
                "Some counters were not returned: " + ", ".join(missing) + ".",
                "Check MySQL status visibility. Alerts for metrics with missing values are skipped.",
            )
        )

    utilization = connections.get("utilization_percent")
    if utilization is not None:
        if utilization >= thresholds.connection_critical_percent:
            alerts.append(
                _alert(
                    "CONNECTION_UTILIZATION_CRITICAL",
                    "critical",
                    "MySQL connection utilization is very high",
                    "connections.utilization_percent",
                    utilization,
                    thresholds.connection_critical_percent,
                    "The connected thread count has reached the critical utilization threshold. This can increase the chance that new clients cannot connect.",
                    "Review current client connections and application pooling. Investigate idle or unexpectedly growing connections before considering capacity changes.",
                )
            )
        elif utilization >= thresholds.connection_warning_percent:
            alerts.append(
                _alert(
                    "CONNECTION_UTILIZATION_HIGH",
                    "warning",
                    "MySQL connection utilization is elevated",
                    "connections.utilization_percent",
                    utilization,
                    thresholds.connection_warning_percent,
                    "Connection use is above the warning threshold. This is a risk signal, not proof that the server is failing.",
                    "Review connection-pool sizes and whether applications release connections promptly.",
                )
            )

    connected = connections.get("connected")
    maximum = connections.get("max")
    if connected is not None and maximum is not None and maximum > 0:
        remaining = max(maximum - connected, 0)
        if remaining <= thresholds.near_max_critical_remaining:
            alerts.append(
                _alert(
                    "CONNECTION_CAPACITY_CRITICAL",
                    "critical",
                    "Very few MySQL connections remain",
                    "connections.remaining",
                    remaining,
                    thresholds.near_max_critical_remaining,
                    "The number of unused connection slots is at or below the critical headroom threshold.",
                    "Check for connection leaks or unexpectedly high client counts. Avoid changing MySQL limits until the cause is understood.",
                )
            )
        elif remaining <= thresholds.near_max_warning_remaining:
            alerts.append(
                _alert(
                    "CONNECTION_CAPACITY_LOW",
                    "warning",
                    "MySQL connection capacity is nearly full",
                    "connections.remaining",
                    remaining,
                    thresholds.near_max_warning_remaining,
                    "Only a small number of connection slots remain, even if the percentage threshold has not been crossed.",
                    "Review client connection usage and pooling before capacity becomes constrained.",
                )
            )

    if not history_available:
        alerts.append(
            _alert(
                "QUERY_COUNTER_HISTORY_UNAVAILABLE",
                "info",
                "Query-counter comparison is unavailable",
                "query_activity.queries_since_start",
                query_activity.get("queries_since_start"),
                "A readable DB-Pulse history table and snapshot",
                "Current metrics are still checked, but the history table could not be read, so no counter-change alert was calculated.",
                "Check that db_pulse_metric_snapshots exists and the account can read it.",
            )
        )
    elif previous_snapshot is None:
        alerts.append(
            _alert(
                "QUERY_COUNTER_BASELINE_MISSING",
                "info",
                "No query-counter baseline is available yet",
                "query_activity.queries_since_start",
                query_activity.get("queries_since_start"),
                "At least one prior snapshot",
                "Cumulative query counters need a saved timestamped snapshot to calculate change over a real interval.",
                "Save a snapshot with POST /history/snapshots, then check alerts again after some time has passed.",
            )
        )
    else:
        current_queries = query_activity.get("queries_since_start")
        previous_queries = previous_snapshot.get("queries_since_start")
        current_uptime = metrics.get("server_uptime_seconds")
        previous_uptime = previous_snapshot.get("server_uptime_seconds")
        snapshot_time = _as_utc(previous_snapshot.get("captured_at"))
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)
        elapsed_seconds = (
            (current_time - snapshot_time).total_seconds()
            if snapshot_time is not None
            else None
        )
        comparable = (
            isinstance(current_queries, int)
            and isinstance(previous_queries, int)
            and isinstance(current_uptime, int)
            and isinstance(previous_uptime, int)
            and current_queries >= previous_queries
            and current_uptime >= previous_uptime
            and elapsed_seconds is not None
            and elapsed_seconds > 0
        )
        if comparable:
            delta = current_queries - previous_queries
            rate_per_minute = round(delta / elapsed_seconds * 60, 2)
            if rate_per_minute >= thresholds.query_rate_warning_per_minute:
                alerts.append(
                    _alert(
                        "QUERY_ACTIVITY_INCREASED",
                        "warning",
                        "Query activity between snapshots is elevated",
                        "query_activity.queries_per_minute_since_snapshot",
                        rate_per_minute,
                        thresholds.query_rate_warning_per_minute,
                        f"MySQL's cumulative Queries counter increased by {delta} over {round(elapsed_seconds, 1)} seconds. This is an interval average across the whole server, not an instantaneous rate.",
                        "Review workload changes and use MySQL statement statistics or application logs to identify which clients account for the increase.",
                    )
                )
        else:
            alerts.append(
                _alert(
                    "QUERY_COUNTERS_NOT_COMPARABLE",
                    "info",
                    "Query counters could not be compared safely",
                    "query_activity.queries_since_start",
                    current_queries,
                    "A prior counter and positive time interval on the same server uptime",
                    "A counter, uptime, timestamp, or interval was missing or moved backward. This can happen after a MySQL restart or when metrics are incomplete.",
                    "Save a fresh snapshot and compare again after a positive interval. No query-rate alert was inferred.",
                )
            )

    return alerts
