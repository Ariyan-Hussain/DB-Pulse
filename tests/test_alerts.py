from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.alerting import AlertThresholds, evaluate_alerts, load_alert_thresholds
from app.main import app
from app.routes import alerts as alerts_route

client = TestClient(app)


def metrics(*, connected=40, maximum=100, queries=1000, uptime=3600, available=True):
    return {
        "connections": {
            "connected": connected,
            "running": 2,
            "max": maximum,
            "utilization_percent": round(connected / maximum * 100, 2) if maximum else None,
        },
        "server_uptime_seconds": uptime,
        "query_activity": {
            "queries_since_start": queries,
            "client_questions_since_start": queries - 10 if queries is not None else None,
            "average_queries_per_second_since_start": None,
        },
        "server_metrics_available": available,
        "metrics_warning": None if available else "Counters unavailable",
    }


def snapshot(*, captured_at, queries=1000, uptime=3500):
    return {
        "captured_at": captured_at,
        "queries_since_start": queries,
        "server_uptime_seconds": uptime,
    }


def codes(alert_list):
    return {item["code"]: item for item in alert_list}


def test_normal_metrics_do_not_create_warning_or_critical_alerts():
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    previous = snapshot(captured_at=now - timedelta(minutes=5), queries=990, uptime=3300)
    results = evaluate_alerts(metrics(queries=1000, uptime=3600), AlertThresholds(), previous, now=now)
    assert not [item for item in results if item["severity"] in {"warning", "critical"}]


def test_connection_warning_includes_explanation_and_action():
    results = codes(evaluate_alerts(metrics(connected=80), AlertThresholds(), None))
    alert = results["CONNECTION_UTILIZATION_HIGH"]
    assert alert["severity"] == "warning"
    assert alert["observed_value"] == 80.0
    assert alert["threshold"] == 75.0
    assert alert["explanation"]
    assert alert["suggested_action"]


def test_connection_critical_and_low_headroom_alerts():
    results = codes(evaluate_alerts(metrics(connected=98), AlertThresholds(), None))
    assert results["CONNECTION_UTILIZATION_CRITICAL"]["severity"] == "critical"
    assert results["CONNECTION_CAPACITY_CRITICAL"]["observed_value"] == 2
    assert results["CONNECTION_CAPACITY_CRITICAL"]["severity"] == "critical"


def test_missing_metrics_are_reported_without_invented_values():
    missing = metrics(connected=None, maximum=None, queries=None, uptime=None, available=False)
    missing["connections"]["utilization_percent"] = None
    results = codes(evaluate_alerts(missing, AlertThresholds(), None))
    alert = results["MONITORING_METRICS_UNAVAILABLE"]
    assert alert["severity"] == "warning"
    assert alert["observed_value"] == "1 of 6"
    assert "CONNECTION_UTILIZATION_CRITICAL" not in results
    assert "CONNECTION_CAPACITY_CRITICAL" not in results


def test_partial_metrics_get_an_informational_alert():
    partial = metrics()
    partial["query_activity"]["client_questions_since_start"] = None
    results = codes(evaluate_alerts(partial, AlertThresholds(), None))
    assert results["MONITORING_METRICS_INCOMPLETE"]["severity"] == "info"


def test_query_change_uses_a_real_snapshot_interval():
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    previous = snapshot(captured_at=now - timedelta(minutes=2), queries=1000, uptime=3500)
    results = codes(evaluate_alerts(metrics(queries=2400, uptime=3620), AlertThresholds(), previous, now=now))
    alert = results["QUERY_ACTIVITY_INCREASED"]
    assert alert["observed_value"] == 700.0
    assert alert["threshold"] == 600.0
    assert "interval average" in alert["explanation"]


def test_query_counter_reset_is_not_reported_as_a_rate():
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    previous = snapshot(captured_at=now - timedelta(minutes=2), queries=5000, uptime=3500)
    results = codes(evaluate_alerts(metrics(queries=50, uptime=20), AlertThresholds(), previous, now=now))
    assert "QUERY_ACTIVITY_INCREASED" not in results
    assert results["QUERY_COUNTERS_NOT_COMPARABLE"]["severity"] == "info"


def test_threshold_configuration_defaults_and_invalid_values():
    defaults = load_alert_thresholds({})
    assert defaults.connection_warning_percent == 75
    assert defaults.connection_critical_percent == 90
    assert defaults.query_rate_warning_per_minute == 600
    try:
        load_alert_thresholds({
            "DB_PULSE_ALERT_CONNECTION_WARNING_PERCENT": "95",
            "DB_PULSE_ALERT_CONNECTION_CRITICAL_PERCENT": "80",
        })
    except ValueError as error:
        assert "warning < critical" in str(error)
        assert "95" not in str(error)
    else:
        raise AssertionError("Invalid threshold ordering should fail validation")


def test_alert_route_reuses_metrics_and_reads_history_without_writing(monkeypatch):
    class Result:
        def scalar_one(self):
            return "db_pulse_meta"

        def mappings(self):
            return self

        def first(self):
            return None

    class Connection:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement):
            self.statements.append(statement)
            return Result()

    class Engine:
        url = SimpleNamespace(database="db_pulse_meta")

        def __init__(self):
            self.connection = Connection()

        def connect(self):
            return self.connection

    engine = Engine()
    monkeypatch.setattr(alerts_route, "engine", engine)
    monkeypatch.setattr(alerts_route, "collect_server_metrics", lambda _connection: metrics())

    response = client.get("/alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["snapshot_saved"] is False
    assert body["history_comparison"] == "no_snapshots"
    assert "QUERY_COUNTER_BASELINE_MISSING" in {item["code"] for item in body["alerts"]}
    assert not any(getattr(statement, "is_insert", False) for statement in engine.connection.statements)


def test_alert_route_rejects_invalid_threshold_configuration(monkeypatch):
    monkeypatch.setenv("DB_PULSE_ALERT_CONNECTION_WARNING_PERCENT", "not-a-number-secret")
    response = client.get("/alerts")
    assert response.status_code == 500
    assert "not-a-number-secret" not in response.text


def test_alert_route_database_failure_is_sanitized(monkeypatch):
    class BrokenEngine:
        url = SimpleNamespace(database="db_pulse_meta")

        def connect(self):
            raise RuntimeError("private password and connection details")

    monkeypatch.setattr(alerts_route, "engine", BrokenEngine())
    response = client.get("/alerts")
    assert response.status_code == 503
    assert "private" not in response.text


def test_alert_route_refuses_other_databases_without_connecting(monkeypatch):
    class WrongDatabaseEngine:
        url = SimpleNamespace(database="unrelated_app_db")

        def connect(self):
            raise AssertionError("must not connect to unrelated database")

    monkeypatch.setattr(alerts_route, "engine", WrongDatabaseEngine())
    response = client.get("/alerts")
    assert response.status_code == 409
