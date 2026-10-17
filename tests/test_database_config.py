import pytest
from app.database import database_url

def test_database_url_uses_project_environment_names(monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_NAME", "db_pulse_meta")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    url = database_url()
    assert url.drivername == "mysql+pymysql"
    assert url.database == "db_pulse_meta"
    assert url.host == "127.0.0.1"

def test_database_url_reports_missing_names_without_values(monkeypatch):
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="Missing database settings"):
        database_url()


def test_database_url_rejects_invalid_port_without_echoing_it(monkeypatch):
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "db_pulse_meta")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_PORT", "not-a-port-secret")
    with pytest.raises(RuntimeError, match="DB_PORT must be a number") as error:
        database_url()
    assert "not-a-port-secret" not in str(error.value)
