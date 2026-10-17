from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sql_text_gets_explained_suggestions_without_performance_claims():
    response = client.post("/slow-queries/analyze", json={"query": "SELECT * FROM users"})
    assert response.status_code == 200
    body = response.json()
    assert body["statement_type"] == "SELECT"
    assert {item["pattern"] for item in body["recommendations"]} >= {
        "SELECT *", "SELECT without WHERE", "Index and plan review"
    }
    assert body["performance_data_available"] is False
    assert "text-only" in body["performance_note"]
    assert "not executed" in body["safety_note"]


def test_slow_log_fields_are_reported_and_used_cautiously():
    query = "# Query_time: 1.25 Lock_time: 0.00 Rows_sent: 2 Rows_examined: 400\nSELECT id FROM users WHERE active = 1"
    response = client.post("/slow-queries/analyze", json={"query": query})
    assert response.status_code == 200
    body = response.json()
    assert body["performance_data"]["query_time"] == 1.25
    assert body["performance_data"]["rows_examined_to_rows_sent_ratio"] == 200
    assert any(item["pattern"] == "Many rows examined per row returned" for item in body["recommendations"])
    assert body["performance_data_available"] is True


def test_invalid_and_oversized_input_is_rejected():
    assert client.post("/slow-queries/analyze", json={"query": "hello"}).status_code == 422
    assert client.post("/slow-queries/analyze", json={"query": " "}).status_code == 422
    assert client.post("/slow-queries/analyze", json={"query": "SELECT 1" * 2000}).status_code == 422
    assert client.post("/slow-queries/analyze", json={"query": "SELECT 1", "extra": "x"}).status_code == 422
