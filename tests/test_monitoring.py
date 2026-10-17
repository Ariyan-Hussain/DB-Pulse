from fastapi.testclient import TestClient

from app.main import app
from app.routes import monitoring

client = TestClient(app)


class FakeResult:
    def __init__(self, *, one=None, scalar=None, rows=None):
        self._one = one
        self._scalar = scalar
        self._rows = rows or []

    def one(self):
        return self._one

    def scalar_one(self):
        return self._scalar

    def all(self):
        return self._rows


class FakeConnection:
    def __init__(self, *, deny_status=False):
        self.deny_status = deny_status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        sql = str(statement)
        if "SELECT VERSION()" in sql:
            return FakeResult(one=("8.0.test", "db_pulse_meta"))
        if "COUNT(*)" in sql:
            return FakeResult(scalar=4)
        if "COALESCE(SUM" in sql:
            return FakeResult(scalar=1024)
        if "SHOW GLOBAL STATUS" in sql:
            if self.deny_status:
                raise PermissionError("simulated restricted status access")
            return FakeResult(rows=[
                ("Threads_connected", "5"),
                ("Threads_running", "2"),
                ("Uptime", "100"),
                ("Queries", "500"),
                ("Questions", "450"),
            ])
        if "max_connections" in sql:
            return FakeResult(scalar=100)
        raise AssertionError(f"Unexpected query: {sql}")


class FakeEngine:
    def __init__(self, *, deny_status=False, fail_connect=False):
        self.deny_status = deny_status
        self.fail_connect = fail_connect

    def connect(self):
        if self.fail_connect:
            raise RuntimeError("simulated failure containing secret details")
        return FakeConnection(deny_status=self.deny_status)


def test_monitoring_returns_schema_and_server_metrics(monkeypatch):
    monkeypatch.setattr(monitoring, "engine", FakeEngine())
    response = client.get("/monitoring")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "db_pulse_meta"
    assert body["table_count"] == 4
    assert body["connections"] == {
        "connected": 5,
        "running": 2,
        "max": 100,
        "utilization_percent": 5.0,
    }
    assert body["server_uptime_seconds"] == 100
    assert body["query_activity"]["queries_since_start"] == 500
    assert body["query_activity"]["average_queries_per_second_since_start"] == 5.0
    assert body["server_metrics_available"] is True


def test_monitoring_keeps_core_health_when_global_metrics_are_unavailable(monkeypatch):
    monkeypatch.setattr(monitoring, "engine", FakeEngine(deny_status=True))
    response = client.get("/monitoring")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "connected"
    assert body["database"] == "db_pulse_meta"
    assert body["connections"]["connected"] is None
    assert body["server_metrics_available"] is False
    assert "global status" in body["metrics_warning"]


def test_monitoring_database_failure_is_safe(monkeypatch):
    monkeypatch.setattr(monitoring, "engine", FakeEngine(fail_connect=True))
    response = client.get("/monitoring")
    assert response.status_code == 503
    assert "secret" not in response.text
