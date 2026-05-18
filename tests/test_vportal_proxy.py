import pytest
import httpx
from fastapi.testclient import TestClient
from iron_verdict.main import app
from iron_verdict import vportal_proxy as proxy_module

client = TestClient(app)


def test_login_rejects_unknown_host():
    response = client.post(
        "/api/vportal/login",
        json={"host": "attacker.com", "identity": "u", "credential": "p"},
    )
    assert response.status_code == 400
    assert "host" in response.json()["detail"].lower()


def test_login_rejects_localhost_without_test_mode():
    response = client.post(
        "/api/vportal/login",
        json={"host": "localhost", "identity": "u", "credential": "p"},
    )
    assert response.status_code == 400


def test_graphql_rejects_unknown_host():
    response = client.post(
        "/api/vportal/graphql",
        json={"host": "evil.example.com", "token": "x", "query": "{}", "variables": {}},
    )
    assert response.status_code == 400


def test_login_accepts_staging_host(mock_vportal):
    # Allowlist passes — request reaches the upstream call (not rejected with 400).
    # Return 401 so the endpoint terminates cleanly without a real network call.
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(401)

    response = client.post(
        "/api/vportal/login",
        json={"host": "staging.vportal-online.de", "identity": "u", "credential": "p"},
    )
    assert response.status_code != 400


def test_graphql_rejects_mutation():
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "x",
            "query": "mutation updateCompetitionAthleteAttempt { id }",
            "variables": {},
        },
    )
    assert response.status_code == 400
    assert "operation" in response.json()["detail"].lower()


def test_graphql_rejects_unknown_query():
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "x",
            "query": "{ secretAdminQuery { id } }",
            "variables": {},
        },
    )
    assert response.status_code == 400


def test_graphql_accepts_known_operations(monkeypatch):
    # We can't reach upstream from here — the proxy still returns 501 until Task 7,
    # but the allowlist check should fire first and let the request through to the impl.
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "x",
            "query": "{ profile { competition { id } } }",
            "variables": {},
        },
    )
    # Allowlist passed; we hit the 'not implemented' guard.
    assert response.status_code == 501


@pytest.fixture
def mock_vportal():
    """Inject a fake VPortal upstream. Yields the handler so tests can program it."""
    handlers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key in handlers:
            return handlers[key](request)
        return httpx.Response(404, json={"error": "no handler"})

    original = proxy_module._http_client
    proxy_module._http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield handlers
    finally:
        proxy_module._http_client = original


def test_login_success_returns_token_and_interval(mock_vportal, monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "4000")
    # Force settings to re-read for this test
    from iron_verdict import config
    config.settings.VPORTAL_FETCH_INTERVAL_MS = 4000

    def login_response(request):
        return httpx.Response(
            200,
            headers={"set-cookie": "VPORTAL=cookie123; Path=/; HttpOnly"},
        )

    def token_response(request):
        assert request.headers.get("cookie") == "VPORTAL=cookie123"
        return httpx.Response(200, json={"access_token": "jwt-xyz", "exp": 9999999999})

    mock_vportal[("POST", "/account/login")] = login_response
    mock_vportal[("GET", "/auth/token")] = token_response

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "p"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "jwt-xyz"
    assert body["fetch_interval_ms"] == 4000


def test_login_failed_credentials_returns_401(mock_vportal):
    def login_response(request):
        return httpx.Response(401, json={"error": "invalid_credentials"})

    mock_vportal[("POST", "/account/login")] = login_response

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "wrong"},
    )
    assert response.status_code == 401
