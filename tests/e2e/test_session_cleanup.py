"""Session cleanup after external-mode tests — ``_end_session`` survives a
single connection error and names the failing step when it gives up.

Against Railway staging one teardown failed with a TLS read error while every
test had passed (#143). These tests run ``_end_session`` against the
in-process server and inject transport errors into its WebSocket connection.
"""

import httpx
import pytest
from httpx_ws import WebSocketNetworkError

import tests.e2e.conftest as e2e_conftest
from tests.e2e.conftest import _end_session


@pytest.fixture()
def session_code(server_url):
    response = httpx.post(f"{server_url}/api/sessions", json={"name": "Cleanup"})
    assert response.status_code == 200
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


def test_end_session_retries_after_network_error_on_open_websocket(
    server_url, session_code, monkeypatch
):
    """The upgrade succeeds but reading the join reply fails (httpx_ws reports
    it as ``WebSocketNetworkError``) → a fresh connection ends the session."""
    real_connect_ws = e2e_conftest.connect_ws
    calls = []

    class FailingReads:
        def __init__(self, ws):
            self._ws = ws

        def __getattr__(self, name):
            return getattr(self._ws, name)

        def receive_text(self, *args, **kwargs):
            raise WebSocketNetworkError()

    class FirstConnectionFails:
        def __init__(self, *args, **kwargs):
            self._cm = real_connect_ws(*args, **kwargs)

        def __enter__(self):
            ws = self._cm.__enter__()
            return FailingReads(ws) if len(calls) == 1 else ws

        def __exit__(self, *exc):
            return self._cm.__exit__(*exc)

    def connect_ws(*args, **kwargs):
        calls.append(1)
        return FirstConnectionFails(*args, **kwargs)

    monkeypatch.setattr(e2e_conftest, "connect_ws", connect_ws)

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
