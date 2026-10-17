from fastapi.testclient import TestClient

from app.main import app
from app.routes import partitions

client = TestClient(app)


class FakeResult:
    def mappings(self):
        return self

    def all(self):
        return [{
            "TABLE_SCHEMA": "db_pulse_meta",
            "TABLE_NAME": "events",
            "PARTITION_NAME": "p0",
            "PARTITION_METHOD": "RANGE",
            "PARTITION_EXPRESSION": "id",
            "PARTITION_DESCRIPTION": "1000",
            "TABLE_ROWS": 20,
        }]


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        assert "information_schema.partitions" in str(statement)
        assert "PARTITION_NAME IS NOT NULL" in str(statement)
        return FakeResult()


class FakeEngine:
    def connect(self):
        return FakeConnection()


def test_partitions_returns_partition_metadata(monkeypatch):
    monkeypatch.setattr(partitions, "engine", FakeEngine())
    response = client.get("/partitions")
    assert response.status_code == 200
    assert response.json()["partitions"][0]["PARTITION_METHOD"] == "RANGE"


def test_partitions_database_error_is_safe(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("sensitive connection detail")

    monkeypatch.setattr(partitions, "engine", BrokenEngine())
    response = client.get("/partitions")
    assert response.status_code == 503
    assert "sensitive" not in response.text
