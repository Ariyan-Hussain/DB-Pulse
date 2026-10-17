from types import SimpleNamespace

import pytest

from app.pool_monitor import PoolThresholds, build_pool_status, load_pool_thresholds


class FullPool:
    _timeout = 10
    _max_overflow = 5
    def __init__(self, checkedout): self._checkedout = checkedout
    def size(self): return 5
    def checkedout(self): return self._checkedout
    def checkedin(self): return 5 - self._checkedout if self._checkedout <= 5 else 0
    def overflow(self): return max(0, self._checkedout - 5)


def test_pool_status_normal_warning_and_critical():
    assert build_pool_status(FullPool(2), PoolThresholds())["status"] == "normal"
    assert build_pool_status(FullPool(8), PoolThresholds())["status"] == "warning"
    assert build_pool_status(FullPool(10), PoolThresholds())["status"] == "critical"


def test_pool_status_keeps_unsupported_statistics_unavailable():
    result = build_pool_status(SimpleNamespace(), PoolThresholds())
    assert result["statistics"]["pool_size"] is None
    assert result["statistics"]["utilization_percent"] is None
    assert result["status"] == "normal"
    assert result["checkout_duration"]["available"] is False


def test_pool_threshold_validation(monkeypatch):
    monkeypatch.setenv("DB_PULSE_POOL_WARNING_PERCENT", "85")
    monkeypatch.setenv("DB_PULSE_POOL_CRITICAL_PERCENT", "80")
    with pytest.raises(ValueError):
        load_pool_thresholds()
