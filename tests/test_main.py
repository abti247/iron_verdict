import asyncio
import logging
import time
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


@pytest.mark.asyncio
async def test_websocket_disconnects_on_message_flood(session_code):
    """Sending >20 messages/second closes connection with code 1008."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            # Join (message #1)
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success — server has processed msg #1

            # Send 20 more messages in rapid succession (msgs #2–#21)
            # All within the same 1-second window → triggers the >20 limit
            for _ in range(20):
                await ws.send_json({"type": "ping"})

            # Give server a moment to process and close
            await asyncio.sleep(0.1)

            # Server must actively close the connection (not just timeout).
            # If receive_json times out it means the server did NOT disconnect → test fails.
            try:
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                pytest.fail("Expected server to close the connection with 1008, but it stayed open")
            except asyncio.TimeoutError:
                pytest.fail("Server did not disconnect the client (timed out waiting for close)")
            except Exception:
                pass  # Any WebSocket close exception means the server disconnected — test passes


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


# ---- Session creation logging ----

@pytest.mark.asyncio
async def test_create_session_logs_info(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            resp = await ac.post("/api/sessions", json={"name": "TestMeet"})
    assert resp.status_code == 200
    messages = [r.getMessage() for r in caplog.records]
    assert any("session_created" in m for m in messages)


# ---- WebSocket join logging ----

@pytest.mark.asyncio
async def test_ws_join_success_logs_role_and_session(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "role_joined"]
    assert len(records) == 1
    assert records[0].session_code == code
    assert records[0].role == "left_judge"


@pytest.mark.asyncio
async def test_ws_disconnect_logs_info(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    with caplog.at_level(logging.INFO, logger="judgeme"):
        async with httpx.AsyncClient(
            transport=ASGIWebSocketTransport(app=app), base_url="http://test"
        ) as ac:
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()
            # ws context exit triggers disconnect

    records = [r for r in caplog.records if r.getMessage() == "role_disconnected"]
    assert len(records) == 1
    assert records[0].session_code == code
    assert records[0].role == "left_judge"


@pytest.mark.asyncio
async def test_vote_lock_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "vote_lock", "color": "white"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "vote_locked"]
    assert len(records) == 1
    assert records[0].session_code == code
    assert records[0].position == "left"
    assert records[0].color == "white"


@pytest.mark.asyncio
async def test_timer_start_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "timer_start"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "timer_start"]
    assert len(records) == 1
    assert records[0].session_code == code


@pytest.mark.asyncio
async def test_session_end_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "end_session_confirmed"})
                try:
                    await ws.receive_json()
                except Exception:
                    pass

    records = [r for r in caplog.records if r.getMessage() == "session_ended"]
    assert len(records) == 1
    assert records[0].session_code == code


@pytest.mark.asyncio
async def test_origin_rejection_logs_warning(caplog, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://allowed.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="judgeme"):
            try:
                async with httpx_ws.aconnect_ws(
                    "ws://test/ws", ac,
                    headers={"origin": "https://evil.example.com"}
                ) as ws:
                    pass
            except Exception:
                pass

    records = [r for r in caplog.records if r.getMessage() == "origin_rejected"]
    assert len(records) == 1
    assert records[0].origin == "https://evil.example.com"


@pytest.mark.asyncio
async def test_timer_start_broadcasts_time_remaining_ms():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
            await ws.receive_json()  # join_success
            await ws.send_json({"type": "timer_start"})
            msg = await ws.receive_json()

    assert msg["type"] == "timer_start"
    assert "time_remaining_ms" in msg
    assert "server_timestamp" not in msg
    assert msg["time_remaining_ms"] == 60000


@pytest.mark.asyncio
async def test_timer_start_stores_timer_started_at():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
            await ws.receive_json()
            await ws.send_json({"type": "timer_start"})
            await ws.receive_json()

    assert session_manager.sessions[code]["timer_started_at"] is not None
    assert abs(session_manager.sessions[code]["timer_started_at"] - time.time()) < 2


@pytest.mark.asyncio
async def test_message_flood_logs_warning(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()
                for _ in range(25):
                    try:
                        await ws.send_json({"type": "vote_lock", "color": "white"})
                    except Exception:
                        break

    records = [r for r in caplog.records if r.getMessage() == "message_flood_disconnect"]
    assert len(records) == 1


@pytest.mark.asyncio
async def test_timer_reset_clears_timer_started_at():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
            await ws.receive_json()
            await ws.send_json({"type": "timer_start"})
            await ws.receive_json()
            await ws.send_json({"type": "timer_reset"})
            await ws.receive_json()

    assert session_manager.sessions[code]["timer_started_at"] is None
