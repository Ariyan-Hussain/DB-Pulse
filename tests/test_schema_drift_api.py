from fastapi.testclient import TestClient

from app.main import app
from app.routes import schema_drift as route


class Result:
    def __init__(self, row=None, scalar=None, rows=None, lastrowid=None):
        self._row, self._scalar, self._rows, self.lastrowid = row, scalar, rows or [], lastrowid
    def first(self): return self._row
    def scalar_one(self): return self._scalar
    def mappings(self): return self
    def all(self): return self._rows


class Connection:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT DATABASE()" in sql: return Result(scalar="db_pulse_meta")
        if "SELECT id FROM" in sql: return Result(row=None)
        if "information_schema.COLUMNS" in sql:
            return Result(rows=[{"TABLE_NAME":"sample", "COLUMN_NAME":"id", "COLUMN_TYPE":"int", "IS_NULLABLE":"NO", "COLUMN_DEFAULT":None, "COLUMN_KEY":"PRI", "ORDINAL_POSITION":1}])
        if "INSERT INTO" in sql:
            assert params["schema_name"] == "db_pulse_meta"
            return Result(lastrowid=7)
        raise AssertionError(sql)


class Engine:
    class Url: database = "db_pulse_meta"
    url = Url()
    def begin(self): return Connection()


def test_baseline_endpoint_saves_first_version(monkeypatch):
    monkeypatch.setattr(route, "engine", Engine())
    response = TestClient(app).post("/schema-drift/baseline", json={"confirm_replace": False})
    assert response.status_code == 201
    assert response.json()["baseline_id"] == 7
    assert response.json()["table_count"] == 1
    assert response.json()["column_count"] == 1
