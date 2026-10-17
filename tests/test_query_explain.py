from fastapi.testclient import TestClient

from app.main import app
from app.routes import query_explain as route


class FakeResult:
    def mappings(self):
        return self

    def all(self):
        return [{"id": 1, "select_type": "SIMPLE", "table": "users", "type": "ALL", "possible_keys": None, "key": None, "rows": 42, "Extra": "Using where"}]


class FakeConnection:
    def __init__(self):
        self.statement = None

    def execute(self, statement):
        self.statement = str(statement)
        return FakeResult()


def test_validate_select_rejects_non_select_and_multiple_statements():
    from fastapi import HTTPException
    from app.query_explain import validate_select_query

    for query in ("", "DELETE FROM users", "SELECT 1; DROP TABLE users", "SELECT * FROM t -- comment", "WITH x AS (SELECT 1) SELECT * FROM x", "SELECT * FROM other_schema.users"):
        try:
            validate_select_query(query)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError(f"accepted unsupported query: {query!r}")


def test_explain_returns_structured_estimate_without_analyze():
    connection = FakeConnection()
    from app.query_explain import explain_select

    result = explain_select(connection, "SELECT * FROM users")
    assert connection.statement == "EXPLAIN SELECT * FROM users"
    assert result["read_only"] is True
    assert result["explain_analyze_used"] is False
    assert result["plan"][0]["rows"] == 42
    assert any("full table scan" in warning for warning in result["warnings"])


def test_explain_route_database_failure_is_generic(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("password=do-not-leak")

    monkeypatch.setattr(route, "engine", BrokenEngine())
    response = TestClient(app).post("/queries/explain", json={"query": "SELECT 1"})
    assert response.status_code == 503
    assert "do-not-leak" not in response.text


def test_explain_route_rejects_invalid_query_before_connection(monkeypatch):
    class NoConnectEngine:
        def connect(self):
            raise AssertionError("connection must not be opened")

    monkeypatch.setattr(route, "engine", NoConnectEngine())
    response = TestClient(app).post("/queries/explain", json={"query": "DROP TABLE users"})
    assert response.status_code == 422



def test_explain_permission_error_is_safe_and_specific():
    from fastapi import HTTPException
    from sqlalchemy.exc import DBAPIError
    from app.query_explain import explain_select

    class DeniedConnection:
        def execute(self, statement):
            raise DBAPIError(str(statement), None, Exception(1142, "secret detail"))

    try:
        explain_select(DeniedConnection(), "SELECT 1")
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "secret detail" not in exc.detail
    else:
        raise AssertionError("permission error should become HTTP 403")
