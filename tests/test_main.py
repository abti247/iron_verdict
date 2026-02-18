import asyncio
import pytest
import httpx
import httpx_ws
from httpx_ws.transport import ASGIWebSocketTransport
from fastapi.testclient import TestClient
from judgeme.main import app, session_manager
from judgeme.config import settings


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate-limit counters so tests don't bleed into each other."""
    try:
        from judgeme.main import limiter
        limiter._storage.reset()
    except (ImportError, AttributeError):
        pass
    yield


client = TestClient(app)


@pytest.fixture
async def session_code():
    """Create a fresh session and return its code."""
    code = await session_manager.create_session("Test Session")
    yield code
    if code in session_manager.sessions:
        session_manager.delete_session(code)


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


@pytest.mark.asyncio
async def test_settings_update_stored_in_session(session_code):
    """Head judge can update settings via settings_update message."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({
                "type": "settings_update",
                "showExplanations": True,
                "liftType": "deadlift"
            })
            # Give the server a moment to process
            await asyncio.sleep(0.1)
            # Check session state directly
            session = session_manager.sessions[session_code]
            assert session["settings"]["show_explanations"] is True
            assert session["settings"]["lift_type"] == "deadlift"


@pytest.mark.asyncio
async def test_show_results_includes_settings(session_code):
    """show_results broadcast includes current settings."""
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as left_client, \
               httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as center_client, \
               httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as right_client, \
               httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as display_client:

        async with httpx_ws.aconnect_ws("ws://test/ws", left_client) as left_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", center_client) as center_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", right_client) as right_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", display_client) as display_ws:

            await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await left_ws.receive_json()
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await center_ws.receive_json()
            await right_ws.send_json({"type": "join", "session_code": session_code, "role": "right_judge"})
            await right_ws.receive_json()
            await display_ws.send_json({"type": "join", "session_code": session_code, "role": "display"})
            await display_ws.receive_json()

            # Head judge sets lift type to bench
            await center_ws.send_json({"type": "settings_update", "showExplanations": True, "liftType": "bench"})
            await asyncio.sleep(0.1)

            # All judges lock votes
            await left_ws.send_json({"type": "vote_lock", "color": "white"})
            await center_ws.send_json({"type": "vote_lock", "color": "red"})
            await right_ws.send_json({"type": "vote_lock", "color": "white"})

            async def collect_messages(ws, count=5):
                msgs = []
                for _ in range(count):
                    try:
                        msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                        msgs.append(msg)
                    except asyncio.TimeoutError:
                        break
                return msgs

            display_msgs = await collect_messages(display_ws)
            show_results = next((m for m in display_msgs if m.get("type") == "show_results"), None)

            assert show_results is not None
            assert "showExplanations" in show_results
            assert "liftType" in show_results
            assert show_results["showExplanations"] is True
            assert show_results["liftType"] == "bench"


@pytest.mark.asyncio
async def test_settings_update_invalid_lift_type_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({
                "type": "settings_update",
                "showExplanations": False,
                "liftType": "powerclean"
            })
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "error"


@pytest.mark.asyncio
async def test_vote_lock_invalid_color_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "vote_lock", "color": "HACKED"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "error"
            assert "color" in msg["message"].lower()


@pytest.mark.asyncio
async def test_vote_lock_missing_color_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "vote_lock"})  # no color field
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "error"
            assert "color" in msg["message"].lower()


@pytest.mark.asyncio
async def test_display_cap_rejects_when_full(monkeypatch):
    """Setting DISPLAY_CAP=0 immediately rejects any display join."""
    monkeypatch.setattr(settings, "DISPLAY_CAP", 0)
    code = await session_manager.create_session("Cap Test")
    try:
        async with httpx.AsyncClient(
            transport=ASGIWebSocketTransport(app=app), base_url="http://test"
        ) as ac:
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "display"})
                response = await ws.receive_json()
                assert response["type"] == "join_error"
                assert "cap" in response["message"].lower()
    finally:
        session_manager.delete_session(code)


def test_create_session_rate_limited_after_10_requests():
    """11th request from the same IP within an hour returns 429."""
    for i in range(10):
        r = client.post("/api/sessions", json={"name": f"S{i}"})
        assert r.status_code == 200, f"Request {i+1} should succeed, got {r.status_code}"

    r = client.post("/api/sessions", json={"name": "overflow"})
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_websocket_rejects_wrong_origin(monkeypatch):
    """WS connection with wrong Origin is closed with code 1008."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://app.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        try:
            async with httpx_ws.aconnect_ws(
                "ws://test/ws", ac, headers={"origin": "https://evil.com"}
            ) as ws:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                pytest.fail(f"Expected connection to be closed, got message: {msg}")
        except asyncio.TimeoutError:
            pytest.fail("Expected WebSocket close on origin mismatch, got timeout")
        except Exception:
            pass  # Connection was closed/rejected as expected (1008 close)


@pytest.mark.asyncio
async def test_websocket_accepts_matching_origin(monkeypatch, session_code):
    """WS connection with correct Origin is accepted normally."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://app.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws(
            "ws://test/ws", ac, headers={"origin": "https://app.example.com"}
        ) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            msg = await ws.receive_json()
            assert msg["type"] == "join_success"
