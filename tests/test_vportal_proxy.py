import base64
import json

import pytest
import httpx
from fastapi.testclient import TestClient
from iron_verdict.main import app
from iron_verdict import vportal_proxy as proxy_module

client = TestClient(app)


def _jwt_with_exp(exp: int) -> str:
    """Build a base64url-encoded JWT-shaped string with `exp` in the payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def test_login_rejects_unknown_host():
    response = client.post(
        "/api/vportal/login",
        json={"host": "attacker.com", "identity": "u", "credential": "p"},
    )
    assert response.status_code == 400
    assert "host" in response.json()["detail"].lower()


def test_login_rejects_localhost_without_test_mode():
    # Why: tests/e2e/conftest.py sets TEST_MODE=1 at import time so the proxy
    # talks to the fake VPortal server. That env var leaks across the whole
    # pytest process, so this test explicitly toggles the in-memory flag off
    # for the duration of the assertion.
    from iron_verdict import vportal_proxy as proxy_module
    original = proxy_module.settings.TEST_MODE
    proxy_module.settings.TEST_MODE = False
    try:
        response = client.post(
            "/api/vportal/login",
            json={"host": "localhost", "identity": "u", "credential": "p"},
        )
        assert response.status_code == 400
    finally:
        proxy_module.settings.TEST_MODE = original


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
        json={"host": "staging-bvdk.vportal-online.de", "identity": "u", "credential": "p"},
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


def test_graphql_accepts_known_operations(mock_vportal):
    # Allowlist check passes — request reaches the upstream call.
    # Return 200 so the endpoint terminates cleanly without a real network call.
    mock_vportal[("POST", "/graphql")] = lambda r: httpx.Response(200, json={"data": {}})
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "x",
            "query": "{ profile { competition { id } } }",
            "variables": {},
        },
    )
    assert response.status_code == 200


@pytest.fixture
def mock_vportal():
    """Inject a fake VPortal upstream. Yields the handler so tests can program it.

    Patches both the shared `_http_client` (used by graphql) and the login-time
    client factory (`_make_login_client`) so all outbound proxy traffic is
    routed through the same mock transport. Each login flow still gets a fresh
    AsyncClient with its own cookie jar, mirroring production.
    """
    handlers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key in handlers:
            return handlers[key](request)
        return httpx.Response(404, json={"error": "no handler"})

    transport = httpx.MockTransport(handler)

    original_http_client = proxy_module._http_client
    original_make_login_client = proxy_module._make_login_client

    proxy_module._http_client = httpx.AsyncClient(transport=transport)
    proxy_module._make_login_client = lambda: httpx.AsyncClient(transport=transport)
    try:
        yield handlers
    finally:
        proxy_module._http_client = original_http_client
        proxy_module._make_login_client = original_make_login_client


def test_login_success_returns_token_and_interval(mock_vportal, monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "4000")
    # Why: vportal_proxy.py captured its own `settings` reference at import.
    # If test_config.py reloaded the config module earlier in the run, the
    # `iron_verdict.config.settings` name now points at a different object
    # than the proxy is reading. Mutate the object the proxy actually sees.
    original = proxy_module.settings.VPORTAL_FETCH_INTERVAL_MS
    proxy_module.settings.VPORTAL_FETCH_INTERVAL_MS = 4000

    fake_jwt = _jwt_with_exp(9999999999)

    def login_response(request):
        # Real VPortal redirects on success; cookie's expires=... contains a
        # comma to verify the proxy doesn't naively split Set-Cookie on commas.
        return httpx.Response(
            302,
            headers={
                "set-cookie": "VPORTAL=cookie123; expires=Wed, 21 Oct 2099 07:28:00 GMT; Path=/; HttpOnly",
                "location": "/dashboard",
            },
        )

    def token_response(request):
        assert "VPORTAL=cookie123" in request.headers.get("cookie", "")
        # No top-level exp — mirrors real VPortal. exp must come from the JWT.
        return httpx.Response(200, json={"access_token": fake_jwt})

    mock_vportal[("POST", "/account/login")] = login_response
    mock_vportal[("GET", "/auth/token")] = token_response

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "p"},
    )
    try:
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == fake_jwt
        assert body["exp"] == 9999999999  # decoded from the JWT payload
        assert body["fetch_interval_ms"] == 4000
    finally:
        proxy_module.settings.VPORTAL_FETCH_INTERVAL_MS = original


def test_login_sends_multipart_form_data(mock_vportal):
    captured = {}

    def login_response(request):
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content
        return httpx.Response(
            200,
            headers={"set-cookie": "VPORTAL=abc; Path=/; HttpOnly"},
        )

    mock_vportal[("POST", "/account/login")] = login_response
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(
        200, json={"access_token": _jwt_with_exp(1234)}
    )

    client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "p"},
    )
    assert captured["content_type"].startswith("multipart/form-data")
    assert b"identity" in captured["body"]
    assert b"credential" in captured["body"]


def test_login_no_cookie_returned_surfaces_as_502(mock_vportal):
    # Defensive case: if /account/login ever returns no Set-Cookie at all,
    # surface that as 502 with a distinct error message.
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        401, json={"error": "invalid_credentials"}
    )

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "wrong"},
    )
    assert response.status_code == 502
    assert "cookie" in response.json()["detail"].lower()


def test_login_wrong_credentials_surfaces_as_401(mock_vportal):
    # Verified at staging 2026-05-19: real VPortal issues a pre-auth VPORTAL
    # cookie on /account/login even for wrong credentials, then rejects the
    # cookie at /auth/token. Map that path to a clean 401 so the modal can
    # show "Login failed — check username and password" instead of
    # "VPortal token exchange failed."
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        200,
        headers={"set-cookie": "VPORTAL=pre-auth-cookie; Path=/; HttpOnly"},
    )
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(401)

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "wrong"},
    )
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower()


def test_login_token_redirect_surfaces_as_401(mock_vportal):
    # Real VPortal returns 302 (redirect to /login) when /auth/token gets a
    # pre-auth cookie that can't be exchanged. httpx with follow_redirects=False
    # surfaces the 302 directly; map it to "Invalid VPortal credentials" same
    # as 401/403 so the modal renders the inline "Login failed" message.
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        200,
        headers={"set-cookie": "VPORTAL=pre-auth-cookie; Path=/; HttpOnly"},
    )
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(
        302, headers={"location": "/login?error=1"}
    )

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "wrong"},
    )
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower()


def test_graphql_forwards_query_and_auth(mock_vportal):
    captured = {}

    def gql_response(request):
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"data": {"profile": {"competition": {"id": "42"}}}})

    mock_vportal[("POST", "/graphql")] = gql_response

    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "jwt-xyz",
            "query": "{ profile { competition { id } } }",
            "variables": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"data": {"profile": {"competition": {"id": "42"}}}}
    assert captured["auth"] == "Bearer jwt-xyz"
    assert "profile" in captured["body"]


def test_graphql_propagates_401(mock_vportal):
    mock_vportal[("POST", "/graphql")] = lambda req: httpx.Response(401)
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "expired",
            "query": "{ profile { competition { id } } }",
            "variables": {},
        },
    )
    assert response.status_code == 401


def test_graphql_propagates_5xx_as_502(mock_vportal):
    mock_vportal[("POST", "/graphql")] = lambda req: httpx.Response(503)
    response = client.post(
        "/api/vportal/graphql",
        json={
            "host": "bvdk.vportal-online.de",
            "token": "x",
            "query": "{ profile { competition { id } } }",
            "variables": {},
        },
    )
    assert response.status_code == 502


def test_login_does_not_leak_cookie_jar_between_calls(mock_vportal):
    # Why: real VPortal treats an incoming Cookie: VPORTAL=<valid> as a session
    # refresh and ignores the form credentials. If the proxy shared a cookie
    # jar across login calls, a second operator typing garbage credentials
    # would inherit the previous operator's session — session-bleed.
    fake_jwt = _jwt_with_exp(9999999999)
    call_count = {"login": 0}
    second_login_request_cookies = {"value": None}

    def login_response(request):
        call_count["login"] += 1
        if call_count["login"] == 1:
            return httpx.Response(
                302,
                headers={
                    "set-cookie": "VPORTAL=A-cookie; Path=/; HttpOnly",
                    "location": "/dashboard",
                },
            )
        # Second login: capture whether the proxy forwarded any cookie
        second_login_request_cookies["value"] = request.headers.get("cookie", "")
        return httpx.Response(401)

    mock_vportal[("POST", "/account/login")] = login_response
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(
        200, json={"access_token": fake_jwt}
    )

    # First login: succeeds and would seed a jar on a shared client
    r1 = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "p"},
    )
    assert r1.status_code == 200

    # Second login: bad creds. With per-login client (the fix), no prior cookie
    # leaks into the outbound request; the upstream returns 401 with no cookie;
    # the proxy raises 502. Without the fix, the jar would carry VPORTAL=A-cookie
    # to the upstream and the response would refresh-and-return a valid cookie.
    r2 = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "wrong", "credential": "wrong"},
    )

    assert "VPORTAL" not in second_login_request_cookies["value"], (
        "Second login leaked a cookie from the first login's jar: "
        f"{second_login_request_cookies['value']!r}"
    )
    assert r2.status_code == 502
