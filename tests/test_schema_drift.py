from app.schema_drift import compare_schema, index_columns


def col(kind="int", nullable=False, default=None, primary=False):
    return {"data_type": kind, "nullable": nullable, "default": default, "primary_key": primary, "ordinal_position": 1}


def test_index_columns_captures_requested_metadata():
    result = index_columns([{"TABLE_NAME": "users", "COLUMN_NAME": "id", "COLUMN_TYPE": "bigint unsigned", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "COLUMN_KEY": "PRI", "ORDINAL_POSITION": 1}])
    assert result["users"]["id"]["primary_key"] is True
    assert result["users"]["id"]["data_type"] == "bigint unsigned"


def test_index_columns_redacts_sensitive_defaults():
    rows = [
        {"TABLE_NAME": "settings", "COLUMN_NAME": "api_token", "COLUMN_TYPE": "varchar(100)", "IS_NULLABLE": "YES", "COLUMN_DEFAULT": "do-not-return", "COLUMN_KEY": "", "ORDINAL_POSITION": 1},
        {"TABLE_NAME": "settings", "COLUMN_NAME": "note", "COLUMN_TYPE": "varchar(100)", "IS_NULLABLE": "YES", "COLUMN_DEFAULT": "password=do-not-return", "COLUMN_KEY": "", "ORDINAL_POSITION": 2},
    ]
    result = index_columns(rows)["settings"]
    assert result["api_token"]["default"] == "[REDACTED]"
    assert result["api_token"]["default_redacted"] is True
    assert result["note"]["default"] == "[REDACTED]"
    assert "do-not-return" not in repr(result)


def test_compare_detects_added_removed_and_changed_schema_items():
    baseline = {"users": {"id": col("int", primary=True), "name": col("varchar(20)")}, "old": {"x": col()}}
    current = {"users": {"id": col("bigint", primary=True), "email": col("varchar(100)")}, "new": {"y": col()}}
    result = compare_schema(baseline, current)
    assert result["added_tables"] == ["new"]
    assert result["removed_tables"] == ["old"]
    assert result["added_columns"][0]["column"] == "email"
    assert result["removed_columns"][0]["column"] == "name"
    assert result["changed_columns"][0]["changed_fields"] == ["data_type"]
    assert result["unchanged"] is False


def test_compare_unchanged_schema():
    schema = {"users": {"id": col(primary=True)}}
    result = compare_schema(schema, schema)
    assert result["unchanged"] is True
    assert not result["changed_columns"]
from fastapi.testclient import TestClient

from app.main import app
from app.routes import schema_drift as route


class FakeUrl:
    database = "db_pulse_meta"


class FakeResult:
    def __init__(self, scalar=None, row=None):
        self.scalar = scalar
        self.row = row

    def scalar_one(self):
        return self.scalar

    def first(self):
        return self.row

    def mappings(self):
        return self


def test_audit_reports_missing_baseline_cleanly(monkeypatch):
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT DATABASE()" in sql: return FakeResult("db_pulse_meta")
            if "SELECT id, created_at" in sql: return FakeResult(row=None)
            raise AssertionError(sql)

    class Engine:
        url = FakeUrl()
        def connect(self): return Connection()

    monkeypatch.setattr(route, "engine", Engine())
    response = TestClient(app).get("/schema-drift/audit")
    assert response.status_code == 404
    assert "No approved schema baseline" in response.json()["detail"]


def test_audit_database_failure_does_not_leak_connection_details(monkeypatch):
    class Engine:
        url = FakeUrl()
        def connect(self): raise RuntimeError("password=hidden-value")

    monkeypatch.setattr(route, "engine", Engine())
    response = TestClient(app).get("/schema-drift/audit")
    assert response.status_code == 503
    assert "hidden-value" not in response.text
