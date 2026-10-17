"""SQLAlchemy pool status and bounded checkout-duration tracking."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event


@dataclass(frozen=True)
class PoolThresholds:
    warning_percent: float = 75.0
    critical_percent: float = 90.0


def load_pool_thresholds() -> PoolThresholds:
    def number(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"{name} must be a number between 1 and 100") from None
        if not 1 <= value <= 100:
            raise ValueError(f"{name} must be between 1 and 100")
        return value

    warning = number("DB_PULSE_POOL_WARNING_PERCENT", 75.0)
    critical = number("DB_PULSE_POOL_CRITICAL_PERCENT", 90.0)
    if critical <= warning:
        raise ValueError("DB_PULSE_POOL_CRITICAL_PERCENT must be greater than DB_PULSE_POOL_WARNING_PERCENT")
    return PoolThresholds(warning, critical)


_lock = threading.Lock()
_active_since: dict[int, float] = {}
_longest_completed_seconds: float | None = None
_attached_pool: Any | None = None


def _checkout(_dbapi_connection: Any, connection_record: Any, _connection_proxy: Any) -> None:
    with _lock:
        _active_since[id(connection_record)] = time.monotonic()


def _checkin(_dbapi_connection: Any, connection_record: Any) -> None:
    global _longest_completed_seconds
    with _lock:
        started = _active_since.pop(id(connection_record), None)
        if started is not None:
            duration = max(0.0, time.monotonic() - started)
            _longest_completed_seconds = max(_longest_completed_seconds or 0.0, duration)


def enable_checkout_tracking(pool: Any) -> bool:
    """Track only currently checked-out record IDs; never retain DB connections."""
    global _attached_pool
    if not hasattr(pool, "dispatch"):
        return False
    with _lock:
        if _attached_pool is pool:
            return True
        if _attached_pool is not None:
            return False
        try:
            event.listen(pool, "checkout", _checkout)
            event.listen(pool, "checkin", _checkin)
            _attached_pool = pool
        except Exception:
            return False
    return True


def checkout_duration_summary(pool: Any) -> dict[str, Any]:
    enabled = enable_checkout_tracking(pool)
    if not enabled:
        return {"available": False, "active_tracked": None, "longest_active_seconds": None, "longest_completed_seconds": None}
    now = time.monotonic()
    with _lock:
        active_durations = [max(0.0, now - value) for value in _active_since.values()]
        longest_active = max(active_durations) if active_durations else 0.0
        completed = _longest_completed_seconds
        active_count = len(_active_since)
    return {
        "available": True,
        "active_tracked": active_count,
        "longest_active_seconds": round(longest_active, 3),
        "longest_completed_seconds": round(completed, 3) if completed is not None else None,
    }


def clear_checkout_tracking() -> None:
    """Detach event hooks and clear bounded state during application shutdown."""
    global _attached_pool, _longest_completed_seconds
    with _lock:
        pool = _attached_pool
        if pool is not None:
            for name, fn in (("checkout", _checkout), ("checkin", _checkin)):
                try:
                    event.remove(pool, name, fn)
                except Exception:
                    pass
        _attached_pool = None
        _active_since.clear()
        _longest_completed_seconds = None


def _stat(pool: Any, method_name: str) -> int | float | None:
    method = getattr(pool, method_name, None)
    if not callable(method):
        return None
    try:
        value = method()
        return value if isinstance(value, (int, float)) else None
    except Exception:
        return None


def build_pool_status(pool: Any, thresholds: PoolThresholds) -> dict[str, Any]:
    size = _stat(pool, "size")
    checked_out = _stat(pool, "checkedout")
    checked_in = _stat(pool, "checkedin")
    overflow = _stat(pool, "overflow")
    timeout = getattr(pool, "_timeout", None)
    if not isinstance(timeout, (int, float)):
        timeout = None

    max_overflow = getattr(pool, "_max_overflow", None)
    capacity = (size + max_overflow) if isinstance(size, (int, float)) and isinstance(max_overflow, (int, float)) and max_overflow >= 0 else None
    utilization = None
    if isinstance(checked_out, (int, float)) and isinstance(capacity, (int, float)) and capacity > 0:
        utilization = round(checked_out / capacity * 100, 2)

    state = "normal"
    if utilization is not None:
        if utilization >= thresholds.critical_percent:
            state = "critical"
        elif utilization >= thresholds.warning_percent:
            state = "warning"
    return {
        "status": state,
        "statistics": {
            "pool_size": size,
            "checked_out": checked_out,
            "checked_in": checked_in,
            "overflow": overflow,
            "configured_timeout_seconds": timeout,
            "capacity_estimate": capacity,
            "utilization_percent": utilization,
        },
        "checkout_duration": checkout_duration_summary(pool),
        "thresholds": {"warning_percent": thresholds.warning_percent, "critical_percent": thresholds.critical_percent},
        "message": "Pool pressure is an operational signal; a high value alone does not prove a connection leak.",
        "read_only": True,
    }
