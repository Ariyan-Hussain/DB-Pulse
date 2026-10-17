from fastapi.testclient import TestClient

from app.main import app
from app.routes import query_explain as route


class Result:
    def mappings(self): return self
    def all(self): return [{"table": None, "type": None, "rows": 1}]


class Connection:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, statement):
        assert str(statement).startswith("EXPLAIN SELECT 1")
        return Result()


class Engine:
    def connect(self): return Connection()


def test_explain_route_returns_successful_plan(monkeypatch):
    monkeypatch.setattr(route, "engine", Engine())
    response = TestClient(app).post("/queries/explain", json={"query": "SELECT 1"})
    assert response.status_code == 200
    assert response.json()["plan"][0]["rows"] == 1
