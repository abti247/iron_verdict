"""Session cleanup after external-mode tests — ``_end_session`` survives a
single connection error and names the failing step when it gives up.

Against Railway staging one teardown failed with a TLS read error while every
test had passed (#143). These tests run ``_end_session`` against the
in-process server and inject transport errors into its WebSocket connection.
"""

import httpx
import pytest

import tests.e2e.conftest as e2e_conftest
from tests.e2e.conftest import _end_session


@pytest.fixture()
def session_code(server_url):
    response = httpx.post(f"{server_url}/api/sessions", json={"name": "Cleanup"})
    return response.json()["session_code"]


def _failing_connect_ws(monkeypatch, failures):
    """Make the first *failures* WebSocket connections raise a TLS read error."""
    real_connect_ws = e2e_conftest.connect_ws
    calls = []

    def connect_ws(*args, **kwargs):
        calls.append(1)
        if len(calls) <= failures:
            raise httpx.ReadError("[SSL: WRONG_VERSION_NUMBER] wrong version number")
        return real_connect_ws(*args, **kwargs)

    monkeypatch.setattr(e2e_conftest, "connect_ws", connect_ws)
    return calls


def test_end_session_retries_after_transport_error(server_url, session_code, monkeypatch):
    """First connection fails with a TLS read error → a fresh connection
    joins, ends the session, and the lookup confirms it is gone."""
    calls = _failing_connect_ws(monkeypatch, failures=1)

    _end_session(server_url, session_code)

    assert len(calls) == 2
    assert httpx.get(f"{server_url}/api/sessions/{session_code}").status_code == 404


def test_end_session_gives_up_at_deadline_naming_the_step(server_url, session_code, monkeypatch):
    """Every connection fails → after the join deadline the error names the
    step and the transport error; the session is still open."""
    _failing_connect_ws(monkeypatch, failures=10_000)
    monkeypatch.setattr(e2e_conftest, "END_SESSION_JOIN_TIMEOUT_S", 0.3)
    monkeypatch.setattr(e2e_conftest, "END_SESSION_RETRY_INTERVAL_S", 0.05)

    with pytest.raises(AssertionError) as failure:
        _end_session(server_url, session_code)

    assert "connect" in str(failure.value)
    assert "WRONG_VERSION_NUMBER" in str(failure.value)
    assert httpx.get(f"{server_url}/api/sessions/{session_code}").status_code == 200
