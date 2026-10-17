from fastapi.testclient import TestClient

from app.main import app
from app.routes import locks

client = TestClient(app)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeConnection:
    def __init__(self, fail_waits=False):
        self.fail_waits = fail_waits

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        sql = str(statement)
        if "data_lock_waits" in sql:
            if self.fail_waits:
                raise PermissionError("restricted Performance Schema")
            return FakeResult([{
                "waiting_transaction_id": "trx-2",
                "waiting_thread_id": 22,
                "blocking_transaction_id": "trx-1",
                "blocking_thread_id": 11,
                "schema_name": "db_pulse_meta",
                "table_name": "sample",
            }])
        return FakeResult([{"trx_id": "trx-1", "trx_state": "RUNNING"}])


class FakeEngine:
    def __init__(self, *, fail_waits=False):
        self.fail_waits = fail_waits

    def connect(self):
        return FakeConnection(fail_waits=self.fail_waits)


def test_lock_wait_response_names_waiting_and_blocking_transactions(monkeypatch):
    monkeypatch.setattr(locks, "engine", FakeEngine())
    response = client.get("/locks")
    assert response.status_code == 200
    body = response.json()
    assert body["active_transactions"][0]["trx_id"] == "trx-1"
    assert body["lock_waits"][0]["waiting_transaction_id"] == "trx-2"
    assert body["lock_waits"][0]["blocking_transaction_id"] == "trx-1"
    assert body["lock_waits_available"] is True


def test_lock_wait_permission_error_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(locks, "engine", FakeEngine(fail_waits=True))
    response = client.get("/locks")
    assert response.status_code == 200
    body = response.json()
    assert body["active_transactions"]
    assert body["lock_waits"] == []
    assert body["lock_waits_available"] is False
    assert "Performance Schema" in body["message"]
