from fastapi.testclient import TestClient
from judgeme.main import app

client = TestClient(app)


def test_create_session_returns_code():
    response = client.post("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_code" in data
    assert len(data["session_code"]) == 6
