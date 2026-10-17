from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routes import history

client = TestClient(app)


class Result:
    def __init__(self, *, scalar=None, rows=None, inserted_id=None):
        self.scalar = scalar
        self.rows = rows or []
        self.inserted_primary_key = [inserted_id] if inserted_id is not None else []

    def scalar_one(self):
        return self.scalar

    def all(self):
        return self.rows

    def mappings(self):
        return self


class Connection:
    def __init__(self, *, fail_metrics=False, fail_insert=False, fail_select=False, rows=None):
        self.fail_metrics = fail_metrics
        self.fail_insert = fail_insert
        self.fail_select = fail_select
        self.rows = rows or []
        self.inserted_values = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        sql = str(statement)
        if "SELECT DATABASE()" in sql:
            return Result(scalar="db_pulse_meta")
        if "SHOW GLOBAL STATUS" in sql:
            if self.fail_metrics:
                raise PermissionError("restricted global status")
            return Result(rows=[
                ("Threads_connected", "4"),
                ("Threads_running", "1"),
                ("Uptime", "3600"),
                ("Queries", "720"),
                ("Questions", "600"),
            ])
        if getattr(statement, "is_insert", False):
            if self.fail_insert:
                raise RuntimeError("private connection detail")
            self.inserted_values = statement.compile().params
            return Result(inserted_id=7)
        if getattr(statement, "is_select", False):
            if self.fail_select:
                raise RuntimeError("private history database detail")
            return Result(rows=self.rows)
        if "max_connections" in sql:
            return Result(scalar=100)
        raise AssertionError(f"Unexpected statement: {sql}")


class Engine:
    def __init__(self, connection, database="db_pulse_meta"):
        self.connection = connection
        self.url = SimpleNamespace(database=database)
        self.connect_calls = 0

    def begin(self):
        self.connect_calls += 1
        return self.connection

    def connect(self):
        self.connect_calls += 1
        return self.connection


def test_save_snapshot_writes_only_selected_metrics(monkeypatch):
    connection = Connection()
    engine = Engine(connection)
    monkeypatch.setattr(history, "engine", engine)

    response = client.post("/history/snapshots")

    assert response.status_code == 201
    body = response.json()
    assert body["snapshot"]["id"] == 7
    assert body["snapshot"]["connected_connections"] == 4
    assert body["snapshot"]["max_connections"] == 100
    assert body["snapshot"]["connection_utilization_percent"] == 4.0
    assert body["snapshot"]["queries_since_start"] == 720
    assert body["snapshot"]["captured_at"].endswith("Z")
    assert connection.inserted_values["server_metrics_available"] is True
    assert set(connection.inserted_values) == {
        "captured_at", "connected_connections", "running_connections", "max_connections",
        "connection_utilization_percent", "server_uptime_seconds", "queries_since_start",
        "questions_since_start", "server_metrics_available", "metrics_warning",
    }


def test_save_snapshot_records_unavailable_metrics_as_null(monkeypatch):
    connection = Connection(fail_metrics=True)
    monkeypatch.setattr(history, "engine", Engine(connection))

    response = client.post("/history/snapshots")

    assert response.status_code == 201
    assert response.json()["snapshot"]["server_metrics_available"] is False
    assert response.json()["snapshot"]["connected_connections"] is None
    assert "global status" in response.json()["snapshot"]["metrics_warning"]


def test_list_recent_snapshots(monkeypatch):
    row = {
        "id": 7,
        "captured_at": datetime(2026, 10, 17, 12, 0, 0),
        "connected_connections": 4,
        "running_connections": 1,
        "max_connections": 100,
        "connection_utilization_percent": 4,
        "server_uptime_seconds": 3600,
        "queries_since_start": 720,
        "questions_since_start": 600,
        "server_metrics_available": True,
        "metrics_warning": None,
    }
    monkeypatch.setattr(history, "engine", Engine(Connection(rows=[row])))

    response = client.get("/history/snapshots?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["limit"] == 5
    assert body["snapshots"][0]["captured_at"] == "2026-10-17T12:00:00Z"
    assert body["snapshots"][0]["connection_utilization_percent"] == 4.0


def test_empty_history_is_a_successful_empty_list(monkeypatch):
    monkeypatch.setattr(history, "engine", Engine(Connection(rows=[])))

    response = client.get("/history/snapshots")

    assert response.status_code == 200
    assert response.json() == {"count": 0, "limit": 20, "snapshots": []}


def test_invalid_history_limits_are_rejected_before_database_access(monkeypatch):
    engine = Engine(Connection())
    monkeypatch.setattr(history, "engine", engine)

    assert client.get("/history/snapshots?limit=0").status_code == 422
    assert client.get("/history/snapshots?limit=101").status_code == 422
    assert engine.connect_calls == 0


def test_snapshot_database_failures_do_not_expose_details(monkeypatch):
    monkeypatch.setattr(history, "engine", Engine(Connection(fail_insert=True)))

    response = client.post("/history/snapshots")

    assert response.status_code == 503
    assert "private" not in response.text


def test_history_is_refused_for_a_non_db_pulse_database(monkeypatch):
    engine = Engine(Connection(), database="unrelated_app_db")
    monkeypatch.setattr(history, "engine", engine)

    response = client.post("/history/snapshots")

    assert response.status_code == 409
    assert engine.connect_calls == 0


def test_history_read_failure_does_not_expose_database_details(monkeypatch):
    monkeypatch.setattr(history, "engine", Engine(Connection(fail_select=True)))

    response = client.get("/history/snapshots")

    assert response.status_code == 503
    assert "private" not in response.text
