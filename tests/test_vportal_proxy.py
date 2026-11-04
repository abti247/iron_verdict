import base64
import json
import logging

import pytest
import httpx
from fastapi.testclient import TestClient
from iron_verdict.main import app
from iron_verdict import vportal_proxy as proxy_module
from iron_verdict.logging_config import JsonFormatter

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
        # Exact match: legacy VPORTAL must go back under its own name, not as
        # __Host-VPORTAL (production still used VPORTAL on 2026-10-13, issue #101).
        assert request.headers.get("cookie", "") == "VPORTAL=cookie123"
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


def test_login_accepts_host_prefixed_session_cookie(mock_vportal):
    # Observed at staging 2026-10-13 (issue #101): VPortal renamed its session
    # cookie from VPORTAL to __Host-VPORTAL. The cookie must be sent back to
    # /auth/token under the name it arrived with.
    fake_jwt = _jwt_with_exp(9999999999)
    token_cookie_header = {}

    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        302,
        headers={
            "set-cookie": (
                "__Host-VPORTAL=hostcookie; expires=Wed, 21 Oct 2099 07:28:00 GMT; "
                "Max-Age=28800; path=/; secure; HttpOnly; SameSite=Lax"
            ),
            "location": "/dashboard",
        },
    )

    def token_response(request):
        token_cookie_header["value"] = request.headers.get("cookie", "")
        return httpx.Response(200, json={"access_token": fake_jwt})

    mock_vportal[("GET", "/auth/token")] = token_response

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "p"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == fake_jwt
    assert token_cookie_header["value"] == "__Host-VPORTAL=hostcookie"


def test_login_wrong_credentials_with_host_prefixed_cookie_surfaces_as_401(mock_vportal):
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        200,
        headers={"set-cookie": "__Host-VPORTAL=pre-auth-cookie; path=/; secure; HttpOnly"},
    )
    token_cookie_header = {}

    def token_response(request):
        token_cookie_header["value"] = request.headers.get("cookie", "")
        return httpx.Response(302, headers={"location": "/login?error=1"})

    mock_vportal[("GET", "/auth/token")] = token_response

    response = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "u", "credential": "wrong"},
    )
    assert response.status_code == 401
    assert token_cookie_header["value"] == "__Host-VPORTAL=pre-auth-cookie"


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


_LOGIN_BODY = {"host": "bvdk.vportal-online.de", "identity": "secret-user", "credential": "secret-pass"}


def _login_failed_records(caplog):
    return [r for r in caplog.records if r.getMessage() == "vportal_login_failed"]


def _assert_no_secrets_logged(caplog, *secrets):
    # Format through the production JSON formatter so the check covers exactly
    # what reaches the server log, extras included.
    formatter = JsonFormatter()
    output = "\n".join(formatter.format(r) for r in caplog.records)
    for secret in ("secret-user", "secret-pass", *secrets):
        assert secret not in output


# Why 424 and not 502 for upstream failures on /login (issue #100): Cloudflare
# replaces the body of origin 502 responses with its own error page, so the
# reason never reached the dialog. A non-5xx status passes through unchanged.

def test_login_no_cookie_returned_surfaces_as_424_with_reason_and_log(mock_vportal, caplog):
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        302,
        headers=[
            ("location", "/account/login?error=1"),
            ("set-cookie", "OTHER=other-cookie-value; Path=/"),
        ],
        text="<html>secret-body</html>",
    )

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == 424
    assert response.json()["detail"] == {"reason": "no_session_cookie"}
    records = _login_failed_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.reason == "no_session_cookie"
    assert record.host == "bvdk.vportal-online.de"
    assert record.login_status == 302
    assert record.login_location == "/account/login?error=1"
    assert record.cookie_names == ["OTHER"]
    _assert_no_secrets_logged(caplog, "other-cookie-value", "secret-body")


def test_login_token_exchange_failure_surfaces_as_424_with_upstream_status(mock_vportal, caplog):
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        200, headers={"set-cookie": "__Host-VPORTAL=session-cookie-value; Path=/"}
    )
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(
        500, text="secret-body", headers={"location": "/oops"}
    )

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == 424
    assert response.json()["detail"] == {"reason": "token_exchange_failed", "upstream_status": 500}
    records = _login_failed_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "token_exchange_failed"
    assert record.login_status == 200
    assert record.cookie_names == ["__Host-VPORTAL"]
    assert record.token_status == 500
    assert record.token_location == "/oops"
    _assert_no_secrets_logged(caplog, "session-cookie-value", "secret-body")


@pytest.mark.parametrize(
    "token_response",
    [
        httpx.Response(200, json={"token_type": "bearer"}),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, text="<html>secret-body</html>", headers={"content-type": "text/html"}),
    ],
    ids=["no-access-token", "json-array", "html"],
)
def test_login_token_response_without_access_token_surfaces_as_424(mock_vportal, caplog, token_response):
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        200, headers={"set-cookie": "VPORTAL=session-cookie-value; Path=/"}
    )
    mock_vportal[("GET", "/auth/token")] = lambda r: token_response

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == 424
    assert response.json()["detail"] == {"reason": "missing_access_token"}
    records = _login_failed_records(caplog)
    assert len(records) == 1
    assert records[0].reason == "missing_access_token"
    assert records[0].token_status == 200
    assert records[0].content_type == token_response.headers.get("content-type")
    _assert_no_secrets_logged(caplog, "session-cookie-value", "secret-body")


@pytest.mark.parametrize("failing_path", ["/account/login", "/auth/token"])
@pytest.mark.parametrize("error_cls", [httpx.ConnectError, httpx.ReadTimeout])
def test_login_transport_error_surfaces_as_424_unreachable(mock_vportal, caplog, failing_path, error_cls):
    def fail(request):
        raise error_cls("boom")

    mock_vportal[("POST", "/account/login")] = (
        fail if failing_path == "/account/login"
        else lambda r: httpx.Response(200, headers={"set-cookie": "VPORTAL=session-cookie-value; Path=/"})
    )
    mock_vportal[("GET", "/auth/token")] = fail

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == 424
    assert response.json()["detail"] == {"reason": "unreachable"}
    records = _login_failed_records(caplog)
    assert len(records) == 1
    assert records[0].reason == "unreachable"
    assert records[0].error == error_cls.__name__
    assert records[0].upstream_path == failing_path
    _assert_no_secrets_logged(caplog, "session-cookie-value")


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


@pytest.mark.parametrize("token_status", [302, 401, 403])
def test_login_token_rejection_logs_statuses_without_secrets(mock_vportal, caplog, token_status):
    # Issue #100: a missing role may look exactly like a wrong password (302 to
    # the login page). The dialog stays "check username and password", but the
    # log keeps the statuses and redirect target to tell the two apart.
    mock_vportal[("POST", "/account/login")] = lambda r: httpx.Response(
        302,
        headers={"set-cookie": "VPORTAL=session-cookie-value; Path=/", "location": "/dashboard"},
    )
    mock_vportal[("GET", "/auth/token")] = lambda r: httpx.Response(
        token_status, headers={"location": "/login?error=1"}, text="secret-body"
    )

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == 401
    records = [r for r in caplog.records if r.getMessage() == "vportal_login_rejected"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.INFO
    assert record.host == "bvdk.vportal-online.de"
    assert record.login_status == 302
    assert record.login_location == "/dashboard"
    assert record.cookie_names == ["VPORTAL"]
    assert record.token_status == token_status
    assert record.token_location == "/login?error=1"
    assert not _login_failed_records(caplog)
    _assert_no_secrets_logged(caplog, "session-cookie-value", "secret-body")


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


_GRAPHQL_BODY = {
    "host": "bvdk.vportal-online.de",
    "token": "x",
    "query": "{ profile { competition { id } } }",
    "variables": {},
}


def _failing_then(errors, final_response=None):
    """Handler that raises each error in turn, then returns `final_response`.

    Records every call in `.calls` so tests can assert the retry count.
    """
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return final_response

    handler.calls = calls
    return handler


@pytest.mark.parametrize(
    "error_cls",
    [httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout, httpx.ReadError],
)
def test_graphql_retries_once_on_transport_error(mock_vportal, error_cls, caplog):
    handler = _failing_then(
        [error_cls("Server disconnected without sending a response")],
        httpx.Response(200, json={"data": {"profile": {"competition": {"id": 7}}}}),
    )
    mock_vportal[("POST", "/graphql")] = handler

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        response = client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert response.status_code == 200
    assert response.json() == {"data": {"profile": {"competition": {"id": 7}}}}
    assert len(handler.calls) == 2
    records = [r for r in caplog.records if r.getMessage() == "vportal_transport_retry"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].error == error_cls.__name__
    assert records[0].host == "bvdk.vportal-online.de"
    assert not [r for r in caplog.records if r.getMessage() == "vportal_upstream_unreachable"]


def test_graphql_two_transport_errors_surface_as_502_with_log(mock_vportal, caplog):
    handler = _failing_then([
        httpx.RemoteProtocolError("Server disconnected without sending a response"),
        httpx.ConnectError("Connection refused"),
    ])
    mock_vportal[("POST", "/graphql")] = handler

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert response.status_code == 502
    assert response.json()["detail"] == "VPortal upstream unreachable"
    assert len(handler.calls) == 2
    records = [r for r in caplog.records if r.getMessage() == "vportal_upstream_unreachable"]
    assert len(records) == 1
    assert records[0].error == "ConnectError"
    assert records[0].host == "bvdk.vportal-online.de"


@pytest.mark.parametrize("status", [401, 503])
def test_graphql_does_not_retry_http_error_responses(mock_vportal, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    mock_vportal[("POST", "/graphql")] = handler

    response = client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert response.status_code == (401 if status == 401 else 502)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "upstream_response, content_type",
    [
        (
            httpx.Response(200, content=b"<html>secret-body maintenance</html>",
                           headers={"content-type": "text/html"}),
            "text/html",
        ),
        (httpx.Response(302, headers={"location": "/login"}), None),
    ],
    ids=["200-html", "302-empty"],
)
def test_graphql_non_json_response_surfaces_as_502_with_log(
    mock_vportal, caplog, upstream_response, content_type
):
    calls = []

    def handler(request):
        calls.append(request)
        return upstream_response

    mock_vportal[("POST", "/graphql")] = handler

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        response = client.post(
            "/api/vportal/graphql", json={**_GRAPHQL_BODY, "token": "secret-token"}
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "VPortal upstream invalid response"
    assert len(calls) == 1
    records = [r for r in caplog.records if r.getMessage() == "vportal_upstream_invalid_response"]
    assert len(records) == 1
    assert records[0].host == "bvdk.vportal-online.de"
    assert records[0].upstream_status == upstream_response.status_code
    assert records[0].content_type == content_type
    _assert_no_secrets_logged(caplog, "secret-token", "secret-body")


def test_graphql_passes_through_json_from_other_statuses(mock_vportal):
    body = {"errors": [{"message": "forbidden"}]}
    mock_vportal[("POST", "/graphql")] = lambda req: httpx.Response(403, json=body)

    response = client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert response.status_code == 200
    assert response.json() == body


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
    # the proxy raises 424. Without the fix, the jar would carry VPORTAL=A-cookie
    # to the upstream and the response would refresh-and-return a valid cookie.
    r2 = client.post(
        "/api/vportal/login",
        json={"host": "bvdk.vportal-online.de", "identity": "wrong", "credential": "wrong"},
    )

    assert "VPORTAL" not in second_login_request_cookies["value"], (
        "Second login leaked a cookie from the first login's jar: "
        f"{second_login_request_cookies['value']!r}"
    )
    assert r2.status_code == 424


# ---- Metrics (#181) ----
# Every upstream outcome is counted under a fixed result label, so /metrics
# shows failing or slow BVDK calls without reading the logs.

from iron_verdict import metrics  # noqa: E402

_COOKIE = {"set-cookie": "VPORTAL=session-cookie-value; Path=/"}


def _sample(name, **labels):
    return metrics.registry.get_sample_value(name, labels) or 0.0


def _raise(error_cls):
    def handler(request):
        raise error_cls("boom")
    return handler


_LOGIN_SCENARIOS = {
    "ok": (
        lambda r: httpx.Response(200, headers=_COOKIE),
        lambda r: httpx.Response(200, json={"access_token": _jwt_with_exp(1)}),
        200,
    ),
    "rejected": (lambda r: httpx.Response(200, headers=_COOKIE), lambda r: httpx.Response(302), 401),
    "unreachable": (_raise(httpx.ConnectError), None, 424),
    "no_session_cookie": (lambda r: httpx.Response(200), None, 424),
    "token_exchange_failed": (lambda r: httpx.Response(200, headers=_COOKIE), lambda r: httpx.Response(500), 424),
    "missing_access_token": (lambda r: httpx.Response(200, headers=_COOKIE), lambda r: httpx.Response(200, json={}), 424),
}


@pytest.mark.parametrize("result", list(_LOGIN_SCENARIOS))
def test_login_counted_once_by_result_and_timed(mock_vportal, result):
    login_handler, token_handler, expected_status = _LOGIN_SCENARIOS[result]
    mock_vportal[("POST", "/account/login")] = login_handler
    if token_handler:
        mock_vportal[("GET", "/auth/token")] = token_handler
    before = {r: _sample("iron_verdict_vportal_logins_total", result=r) for r in metrics.VPORTAL_LOGIN_RESULTS}
    before_count = _sample("iron_verdict_vportal_upstream_duration_seconds_count", endpoint="login")

    response = client.post("/api/vportal/login", json=_LOGIN_BODY)

    assert response.status_code == expected_status
    after = {r: _sample("iron_verdict_vportal_logins_total", result=r) for r in metrics.VPORTAL_LOGIN_RESULTS}
    assert {r: after[r] - before[r] for r in after} == {r: (1 if r == result else 0) for r in after}
    assert _sample("iron_verdict_vportal_upstream_duration_seconds_count", endpoint="login") == before_count + 1


_GRAPHQL_SCENARIOS = {
    "ok": (lambda r: httpx.Response(200, json={"data": {}}), 200),
    "token_rejected": (lambda r: httpx.Response(401), 401),
    "upstream_error": (lambda r: httpx.Response(503), 502),
    "unreachable": (_raise(httpx.ConnectError), 502),
    "invalid_response": (lambda r: httpx.Response(200, text="<html>", headers={"content-type": "text/html"}), 502),
}


@pytest.mark.parametrize("result", list(_GRAPHQL_SCENARIOS))
def test_graphql_counted_once_by_result_and_timed(mock_vportal, result):
    handler, expected_status = _GRAPHQL_SCENARIOS[result]
    mock_vportal[("POST", "/graphql")] = handler
    before = {r: _sample("iron_verdict_vportal_graphql_requests_total", result=r) for r in metrics.VPORTAL_GRAPHQL_RESULTS}
    before_count = _sample("iron_verdict_vportal_upstream_duration_seconds_count", endpoint="graphql")

    response = client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert response.status_code == expected_status
    after = {r: _sample("iron_verdict_vportal_graphql_requests_total", result=r) for r in metrics.VPORTAL_GRAPHQL_RESULTS}
    assert {r: after[r] - before[r] for r in after} == {r: (1 if r == result else 0) for r in after}
    # One observation per proxy request, also when it took a retry.
    assert _sample("iron_verdict_vportal_upstream_duration_seconds_count", endpoint="graphql") == before_count + 1


def test_graphql_json_from_other_status_counted_as_ok(mock_vportal):
    """A 403 with a JSON body reaches the display as JSON, so it is not a proxy failure."""
    mock_vportal[("POST", "/graphql")] = lambda r: httpx.Response(403, json={"errors": []})
    before = _sample("iron_verdict_vportal_graphql_requests_total", result="ok")
    assert client.post("/api/vportal/graphql", json=_GRAPHQL_BODY).status_code == 200
    assert _sample("iron_verdict_vportal_graphql_requests_total", result="ok") == before + 1


@pytest.mark.parametrize(
    "errors, final_response, result",
    [
        ([httpx.RemoteProtocolError("stale")], httpx.Response(200, json={"data": {}}), "ok"),
        ([httpx.RemoteProtocolError("stale"), httpx.ConnectError("down")], None, "unreachable"),
    ],
)
def test_graphql_transport_retry_counted(mock_vportal, errors, final_response, result):
    mock_vportal[("POST", "/graphql")] = _failing_then(errors, final_response)
    before_retries = _sample("iron_verdict_vportal_transport_retries_total")
    before_result = _sample("iron_verdict_vportal_graphql_requests_total", result=result)

    client.post("/api/vportal/graphql", json=_GRAPHQL_BODY)

    assert _sample("iron_verdict_vportal_transport_retries_total") == before_retries + 1
    assert _sample("iron_verdict_vportal_graphql_requests_total", result=result) == before_result + 1


def test_requests_rejected_before_upstream_not_counted(mock_vportal):
    """Unknown hosts and mutations never reach VPortal; they show up in the 4xx count instead."""
    names = [
        ("iron_verdict_vportal_upstream_duration_seconds_count", {"endpoint": "login"}),
        ("iron_verdict_vportal_upstream_duration_seconds_count", {"endpoint": "graphql"}),
    ]
    before = [_sample(n, **l) for n, l in names]

    assert client.post("/api/vportal/login", json={**_LOGIN_BODY, "host": "evil.example.com"}).status_code == 400
    assert client.post(
        "/api/vportal/graphql", json={**_GRAPHQL_BODY, "query": "mutation { x }"}
    ).status_code == 400

    assert [_sample(n, **l) for n, l in names] == before
