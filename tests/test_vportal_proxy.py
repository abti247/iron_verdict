from fastapi.testclient import TestClient
from iron_verdict.main import app

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


def test_login_accepts_staging_host():
    # Allowlist passes — request reaches the 'not implemented' guard, not 400.
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
