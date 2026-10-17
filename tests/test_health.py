from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_root(): assert client.get("/").json()["message"] == "Welcome to DB-Pulse"
def test_health(): assert client.get("/health").json()["status"] == "healthy"
def test_import_and_routes(): assert {"/monitoring", "/locks", "/partitions", "/slow-queries/analyze", "/history/snapshots", "/alerts"} <= set(app.openapi()["paths"])
