import logging
import pytest
import httpx
from fastapi.testclient import TestClient
from iron_verdict.main import app


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate-limit counters so tests don't bleed into each other."""
    from iron_verdict.main import limiter
    limiter.reset()
    yield


client = TestClient(app)


def test_create_session_returns_code():
    response = client.post("/api/sessions", json={"name": "Test"})
    assert response.status_code == 200
    data = response.json()
    assert "session_code" in data
    assert len(data["session_code"]) == 8


def test_create_session_requires_name():
    response = client.post("/api/sessions", json={})
    assert response.status_code == 422


def test_create_session_rejects_empty_name():
    response = client.post("/api/sessions", json={"name": ""})
    assert response.status_code == 422


def test_create_session_rejects_whitespace_name():
    response = client.post("/api/sessions", json={"name": "   "})
    assert response.status_code == 422


def test_create_session_rate_limited_after_10_requests():
    """11th request from the same IP within an hour returns 429."""
    for i in range(10):
        r = client.post("/api/sessions", json={"name": f"S{i}"})
        assert r.status_code == 200, f"Request {i+1} should succeed, got {r.status_code}"

    r = client.post("/api/sessions", json={"name": "overflow"})
    assert r.status_code == 429


def test_health_returns_200():
    assert client.get("/health").status_code == 200


def test_security_headers_on_root():
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "cdn.jsdelivr.net" in csp
    assert "'unsafe-eval'" in csp  # Alpine.js requires eval for x-show/x-bind expression evaluation
    assert "fonts.googleapis.com" in csp
    assert "fonts.gstatic.com" in csp


def test_security_headers_on_api():
    response = client.post("/api/sessions", json={"name": "Test"})
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers


async def test_create_session_logs_info(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            resp = await ac.post("/api/sessions", json={"name": "TestMeet"})
    assert resp.status_code == 200
    messages = [r.getMessage() for r in caplog.records]
    assert any("session_created" in m for m in messages)
