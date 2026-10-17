from fastapi.testclient import TestClient

from app.main import app
from app.routes import pool_monitor as route


def test_pool_route_handles_missing_engine(monkeypatch):
    monkeypatch.setattr(route, "engine", None)
    response = TestClient(app).get("/pool/status")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_pool_route_rejects_invalid_thresholds(monkeypatch):
    monkeypatch.setenv("DB_PULSE_POOL_WARNING_PERCENT", "90")
    monkeypatch.setenv("DB_PULSE_POOL_CRITICAL_PERCENT", "80")
    class Engine:
        pool = object()
    monkeypatch.setattr(route, "engine", Engine())
    response = TestClient(app).get("/pool/status")
    assert response.status_code == 500
    assert "threshold configuration" in response.json()["detail"]
