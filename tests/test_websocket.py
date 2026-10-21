import asyncio
import copy
import logging
import time
import pytest
import httpx
import httpx_ws
from httpx_ws.transport import ASGIWebSocketTransport
from iron_verdict.main import app, session_manager
from iron_verdict.config import settings


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate-limit counters so tests don't bleed into each other."""
    from iron_verdict.main import limiter
    limiter.reset()
    yield


@pytest.fixture
async def session_code():
    """Create a fresh session and return its code."""
    code = await session_manager.create_session("Test Session")
    yield code
    if code in session_manager.sessions:
        session_manager.delete_session(code)


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
                "showExplanations": False,
                "liftType": "deadlift"
            })
            # Give the server a moment to process
            await asyncio.sleep(0.1)
            # Check session state directly
            session = session_manager.sessions[session_code]
            assert session["settings"]["show_explanations"] is False
            assert session["settings"]["lift_type"] == "deadlift"


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


async def test_settings_update_without_show_explanations_defaults_to_true(session_code):
    session_manager.update_settings(session_code, False, "squat")
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "settings_update", "liftType": "bench"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "settings_update"
            assert msg["showExplanations"] is True
            assert session_manager.sessions[session_code]["settings"]["show_explanations"] is True


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


async def test_settings_update_broadcasts_to_all_clients(session_code):
    """settings_update message should be broadcast to all connected clients."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as center_client, \
           httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as left_client, \
           httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as right_client:

        async with httpx_ws.aconnect_ws("ws://test/ws", center_client) as center_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", left_client) as left_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", right_client) as right_ws:

            # All judges join
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await right_ws.send_json({"type": "join", "session_code": session_code, "role": "right_judge"})

            # Consume join_success messages
            await center_ws.receive_json()
            await left_ws.receive_json()
            await right_ws.receive_json()

            # Head judge sends settings_update
            await center_ws.send_json({
                "type": "settings_update",
                "showExplanations": False,
                "liftType": "bench",
                "requireReasons": True
            })

            async def collect_until_settings_update(ws):
                for _ in range(5):
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    if msg.get("type") == "settings_update":
                        return msg
                raise AssertionError("settings_update not received")

            msg_left = await collect_until_settings_update(left_ws)
            msg_right = await collect_until_settings_update(right_ws)

            assert msg_left["type"] == "settings_update"
            assert msg_left["showExplanations"] is False
            assert msg_left["liftType"] == "bench"
            assert msg_left["requireReasons"] is True

            assert msg_right["type"] == "settings_update"
            assert msg_right["showExplanations"] is False
            assert msg_right["liftType"] == "bench"
            assert msg_right["requireReasons"] is True

            # Drain remaining queued messages before context teardown to avoid
            # race between disconnect broadcasts and connection close
            for ws in (center_ws, left_ws, right_ws):
                try:
                    while True:
                        await asyncio.wait_for(ws.receive_json(), timeout=0.05)
                except (asyncio.TimeoutError, Exception):
                    pass


async def test_vote_lock_invalid_color_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "vote_lock", "color": "HACKED"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "invalid"
            assert "color" in msg["message"].lower()


async def test_vote_lock_missing_color_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "vote_lock"})  # no color field
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "invalid"
            assert "color" in msg["message"].lower()


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


async def _join(ws, code, role, token=None):
    msg = {"type": "join", "session_code": code, "role": role}
    if token:
        msg["reconnect_token"] = token
    await ws.send_json(msg)
    return await asyncio.wait_for(ws.receive_json(), timeout=1.0)


async def test_websocket_cap_rejects_join_with_1013_and_logs(monkeypatch, session_code, caplog):
    monkeypatch.setattr(settings, "MAX_WEBSOCKETS", 2)
    caplog.set_level(logging.WARNING, logger="iron_verdict")
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as left_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", ac) as center_ws:
            assert (await _join(left_ws, session_code, "left_judge"))["type"] == "join_success"
            assert (await _join(center_ws, session_code, "center_judge"))["type"] == "join_success"

            for role in ("display", "right_judge"):
                async with httpx_ws.aconnect_ws("ws://test/ws", ac) as extra_ws:
                    response = await _join(extra_ws, session_code, role)
                    assert response == {"type": "join_error", "message": "Server at capacity"}
                    with pytest.raises(httpx_ws.WebSocketDisconnect) as closed:
                        await asyncio.wait_for(extra_ws.receive_json(), timeout=1.0)
                    assert closed.value.code == 1013

    # The rejected judge must not hold its position.
    assert session_manager.sessions[session_code]["judges"]["right"]["connected"] is False
    cap_logs = [r for r in caplog.records if r.message == "websocket_cap_reached"]
    assert [r.role for r in cap_logs] == ["display", "right_judge"]
    assert all(r.limit == 2 for r in cap_logs)


async def test_websocket_cap_admits_token_reconnect_while_old_socket_registered(monkeypatch, session_code):
    monkeypatch.setattr(settings, "MAX_WEBSOCKETS", 2)
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as old_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", ac) as center_ws:
            token = (await _join(old_ws, session_code, "left_judge"))["reconnect_token"]
            assert (await _join(center_ws, session_code, "center_judge"))["type"] == "join_success"

            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as new_ws:
                response = await _join(new_ws, session_code, "left_judge", token)
                assert response["type"] == "join_success"
                assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is True


async def test_websocket_cap_admits_token_reconnect_after_old_socket_released(monkeypatch, session_code):
    monkeypatch.setattr(settings, "MAX_WEBSOCKETS", 1)
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as old_ws:
            token = (await _join(old_ws, session_code, "left_judge"))["reconnect_token"]
        for _ in range(20):
            if not session_manager.sessions[session_code]["judges"]["left"]["connected"]:
                break
            await asyncio.sleep(0.05)
        assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is False

        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as display_ws:
            assert (await _join(display_ws, session_code, "display"))["type"] == "join_success"
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as new_ws:
                response = await _join(new_ws, session_code, "left_judge", token)
                assert response["type"] == "join_success"


async def test_websocket_cap_rejects_judge_with_wrong_token(monkeypatch, session_code):
    monkeypatch.setattr(settings, "MAX_WEBSOCKETS", 1)
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as display_ws:
            assert (await _join(display_ws, session_code, "display"))["type"] == "join_success"
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as judge_ws:
                response = await _join(judge_ws, session_code, "left_judge", "0" * 32)
                assert response == {"type": "join_error", "message": "Server at capacity"}


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


# ---- Session creation logging ----

async def test_ws_join_success_logs_role_and_session(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "role_joined"]
    assert len(records) == 1
    assert records[0].session_code == code
    assert records[0].role == "left_judge"


async def test_ws_join_logs_cloudflare_client_ip_not_x_forwarded_for(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    headers = {"CF-Connecting-IP": "198.51.100.7", "X-Forwarded-For": "203.0.113.1"}
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac, headers=headers) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "role_joined"]
    assert records[0].client_ip == "198.51.100.7"


async def test_ws_disconnect_logs_info(caplog):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
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


async def test_vote_lock_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "vote_lock", "color": "white"})
                await asyncio.sleep(0.1)  # log is written during processing; no response expected with <3 judges locked

    records = [r for r in caplog.records if r.getMessage() == "vote_locked"]
    assert len(records) == 1
    assert records[0].session_code == code
    assert records[0].position == "left"
    assert records[0].color == "white"


async def test_timer_start_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "timer_start"})
                await ws.receive_json()

    records = [r for r in caplog.records if r.getMessage() == "timer_start"]
    assert len(records) == 1
    assert records[0].session_code == code


async def test_session_end_logs_info(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
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


async def test_origin_rejection_logs_warning(caplog, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://allowed.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="iron_verdict"):
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


async def test_message_flood_logs_warning(caplog):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="iron_verdict"):
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


async def test_join_success_time_remaining_ms_when_timer_not_running():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
            msg = await ws.receive_json()

    assert msg["type"] == "join_success"
    assert msg["session_state"]["time_remaining_ms"] is None


async def test_join_success_time_remaining_ms_when_timer_running():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        # Head judge starts timer
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": code, "role": "center_judge"})
            await ws.receive_json()
            await ws.send_json({"type": "timer_start"})
            await ws.receive_json()

        # New client joins mid-timer
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws2:
            await ws2.send_json({"type": "join", "session_code": code, "role": "left_judge"})
            msg = await ws2.receive_json()

    assert msg["type"] == "join_success"
    trms = msg["session_state"]["time_remaining_ms"]
    assert trms is not None
    assert 58000 <= trms <= 60000


# ---- Reason selection ----

async def test_vote_lock_reason_stored_in_session():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    session_code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success
            await ws.send_json({"type": "vote_lock", "color": "yellow", "reason": "reasons.bench.yellow.buttocksUp"})
            await asyncio.sleep(0.1)  # no response expected with <3 judges locked

    assert session_manager.sessions[session_code]["judges"]["left"]["current_reason"] == "reasons.bench.yellow.buttocksUp"


async def test_vote_lock_requires_reason_when_mandatory():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    session_code = resp.json()["session_code"]

    session_manager.sessions[session_code]["settings"]["require_reasons"] = True

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success
            await ws.send_json({"type": "vote_lock", "color": "yellow"})  # no reason
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "reason_required"
            assert "Reason required" in msg["message"]


async def test_vote_lock_white_no_reason_ok_when_mandatory():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    session_code = resp.json()["session_code"]

    session_manager.sessions[session_code]["settings"]["require_reasons"] = True

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success
            await ws.send_json({"type": "vote_lock", "color": "white"})  # no reason, white is fine
            # No response expected (all_locked requires all 3 judges); tolerate timeout
            try:
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    assert session_manager.sessions[session_code]["judges"]["left"]["locked"] is True


async def test_ws_logs_include_conn_id(session_code, caplog):
    """All log records from one WS connection share a conn_id."""
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        async with httpx.AsyncClient(
            transport=ASGIWebSocketTransport(app=app), base_url="http://test"
        ) as ac:
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({
                    "type": "join",
                    "session_code": session_code,
                    "role": "center_judge",
                })
                await ws.receive_json()  # join_success

    # Find records emitted during this connection
    ws_records = [r for r in caplog.records if hasattr(r, "conn_id")]
    assert len(ws_records) >= 1, "Expected at least one log record with conn_id"

    conn_ids = {r.conn_id for r in ws_records}
    assert len(conn_ids) == 1, f"Expected one conn_id, got: {conn_ids}"

    conn_id = conn_ids.pop()
    assert len(conn_id) == 16, "conn_id should be 16 hex chars"


async def test_show_results_includes_reasons():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    session_code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as left_ac, \
    httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as center_ac, \
    httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as right_ac:

        async with httpx_ws.aconnect_ws("ws://test/ws", left_ac) as left_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", center_ac) as center_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", right_ac) as right_ws:

            await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await left_ws.receive_json()  # join_success
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await center_ws.receive_json()  # join_success
            await right_ws.send_json({"type": "join", "session_code": session_code, "role": "right_judge"})
            await right_ws.receive_json()  # join_success

            await left_ws.send_json({"type": "vote_lock", "color": "yellow", "reason": "reasons.bench.yellow.buttocksUp"})
            await center_ws.send_json({"type": "vote_lock", "color": "white"})
            await right_ws.send_json({"type": "vote_lock", "color": "yellow", "reason": "reasons.bench.yellow.incompleteLift"})

            # Collect messages from right_ws until we find show_results
            show_results_msg = None
            for _ in range(20):
                try:
                    msg = await asyncio.wait_for(right_ws.receive_json(), timeout=1.0)
                    if msg["type"] == "show_results":
                        show_results_msg = msg
                        break
                except asyncio.TimeoutError:
                    break

            assert show_results_msg is not None
            assert "reasons" in show_results_msg
            assert show_results_msg["reasons"]["left"] == "reasons.bench.yellow.buttocksUp"
            assert show_results_msg["reasons"]["center"] is None
            assert show_results_msg["reasons"]["right"] == "reasons.bench.yellow.incompleteLift"


async def test_join_success_includes_reconnect_token(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            msg = await ws.receive_json()
    assert msg["type"] == "join_success"
    assert "reconnect_token" in msg
    assert isinstance(msg["reconnect_token"], str)
    assert len(msg["reconnect_token"]) == 32


async def test_join_success_session_state_excludes_reconnect_tokens(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            msg = await ws.receive_json()
    assert msg["type"] == "join_success"
    for judge in msg["session_state"]["judges"].values():
        assert "reconnect_token" not in judge


async def test_reconnect_with_valid_token_replaces_stale_connection(session_code):
    """New connection with correct token should succeed even while old connection is open."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac1, httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac2:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac1) as old_ws:
            await old_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            join_msg = await old_ws.receive_json()
            assert join_msg["type"] == "join_success"
            token = join_msg["reconnect_token"]

            # New connection joins with matching token while old is still open
            async with httpx_ws.aconnect_ws("ws://test/ws", ac2) as new_ws:
                await new_ws.send_json({
                    "type": "join",
                    "session_code": session_code,
                    "role": "left_judge",
                    "reconnect_token": token,
                })
                new_join_msg = await asyncio.wait_for(new_ws.receive_json(), timeout=1.0)
                assert new_join_msg["type"] == "join_success"

                # Give old ws disconnect handler time to run
                await asyncio.sleep(0.2)

                # Session must still show left as connected (identity guard worked)
                assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is True


async def test_reconnect_with_wrong_token_rejected(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac1, httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac2:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac1) as old_ws:
            await old_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await old_ws.receive_json()  # join_success

            async with httpx_ws.aconnect_ws("ws://test/ws", ac2) as new_ws:
                await new_ws.send_json({
                    "type": "join",
                    "session_code": session_code,
                    "role": "left_judge",
                    "reconnect_token": "0" * 32,
                })
                msg = await asyncio.wait_for(new_ws.receive_json(), timeout=1.0)
                assert msg["type"] == "join_error"
                assert "already taken" in msg["message"].lower()


async def test_judge_disconnect_broadcasts_status_update(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as center_client, httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as left_client:
        async with httpx_ws.aconnect_ws("ws://test/ws", center_client) as center_ws:
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await center_ws.receive_json()  # center's join_success

            async with httpx_ws.aconnect_ws("ws://test/ws", left_client) as left_ws:
                await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
                await left_ws.receive_json()  # left's join_success
                # Drain judge_status_update that center received when left joined
                try:
                    await asyncio.wait_for(center_ws.receive_json(), timeout=0.3)
                except asyncio.TimeoutError:
                    pass
            # left_ws context exits → triggers disconnect

            await asyncio.sleep(0.1)

            msg = await asyncio.wait_for(center_ws.receive_json(), timeout=1.0)
            assert msg["type"] == "judge_status_update"
            assert msg["position"] == "left"
            assert msg["connected"] is False


async def test_judge_join_broadcasts_status_update(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as center_client, httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as left_client:
        async with httpx_ws.aconnect_ws("ws://test/ws", center_client) as center_ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", left_client) as left_ws:
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await center_ws.receive_json()  # center's join_success

            await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await left_ws.receive_json()  # left's join_success

            # Center should receive judge_status_update for left joining
            msg = await asyncio.wait_for(center_ws.receive_json(), timeout=1.0)
            assert msg["type"] == "judge_status_update"
            assert msg["position"] == "left"
            assert msg["connected"] is True


async def test_head_judge_can_next_lift_in_waiting_state(session_code):
    """next_lift must work even when session state is 'waiting'."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await ws.receive_json()
            assert session_manager.sessions[session_code]["state"] == "waiting"

            await ws.send_json({"type": "next_lift"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "reset_for_next_lift"


async def test_pong_message_updates_last_pong(session_code):
    """Sending a pong message after joining updates the server's last_pong timestamp."""
    from iron_verdict.main import connection_manager
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            ws_obj = await connection_manager.get_connection(session_code, "left_judge")
            before = await connection_manager.get_last_pong(ws_obj)
            await asyncio.sleep(0.01)
            await ws.send_json({"type": "pong"})
            await asyncio.sleep(0.05)

            after = await connection_manager.get_last_pong(ws_obj)
    assert before is not None
    assert after is not None
    assert after > before



def test_heartbeat_timing_constants():
    from iron_verdict.main import HEARTBEAT_INTERVAL_SECONDS, PONG_STALE_SECONDS
    assert HEARTBEAT_INTERVAL_SECONDS == 5
    assert PONG_STALE_SECONDS == 15


async def test_heartbeat_sweep_pings_fresh_and_closes_stale_connections():
    from unittest.mock import AsyncMock
    from iron_verdict.main import heartbeat_sweep, PONG_STALE_SECONDS
    from iron_verdict.connection import ConnectionManager

    manager = ConnectionManager()
    fresh, stale = AsyncMock(), AsyncMock()
    await manager.add_connection("ABCD1234", "left_judge", fresh)
    await manager.add_connection("ABCD1234", "display_1", stale)
    now = time.monotonic()
    manager._last_pong[fresh] = now - (PONG_STALE_SECONDS - 1)
    manager._last_pong[stale] = now - (PONG_STALE_SECONDS + 1)

    await heartbeat_sweep(manager, now)

    fresh.send_json.assert_awaited_once_with({"type": "ping"})
    fresh.close.assert_not_awaited()
    stale.close.assert_awaited_once_with(code=1001)
    stale.send_json.assert_not_awaited()


# ---- Vote delivery (vote_ack / vote_rejected / lift_id) ----

def _ws_client():
    return httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")


async def test_vote_lock_sends_vote_ack_to_voter(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success

            await ws.send_json({"type": "vote_lock", "color": "red", "reason": "reasons.squat.red.depth", "lift_id": 0})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg == {
                "type": "vote_ack",
                "color": "red",
                "reason": "reasons.squat.red.depth",
                "lift_id": 0,
            }


async def test_vote_lock_duplicate_acks_with_stored_vote(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success
            await ws.send_json({"type": "vote_lock", "color": "white"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # first vote_ack

            await ws.send_json({"type": "vote_lock", "color": "red", "reason": "reasons.squat.red.depth"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "vote_ack"
            assert msg["color"] == "white"
            assert msg["reason"] is None
    assert session_manager.sessions[session_code]["judges"]["left"]["current_vote"] == "white"


async def test_vote_lock_duplicate_does_not_notify_displays_again(session_code):
    async with _ws_client() as judge_client, _ws_client() as display_client:
        async with httpx_ws.aconnect_ws("ws://test/ws", judge_client) as ws, \
                   httpx_ws.aconnect_ws("ws://test/ws", display_client) as display_ws:
            await display_ws.send_json({"type": "join", "session_code": session_code, "role": "display"})
            await asyncio.wait_for(display_ws.receive_json(), timeout=1.0)  # join_success
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success
            await asyncio.wait_for(display_ws.receive_json(), timeout=1.0)  # judge_status_update

            await ws.send_json({"type": "vote_lock", "color": "white"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # vote_ack
            assert (await asyncio.wait_for(display_ws.receive_json(), timeout=1.0))["type"] == "judge_voted"

            await ws.send_json({"type": "vote_lock", "color": "white"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # vote_ack
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(display_ws.receive_json(), timeout=0.3)


async def test_vote_lock_with_stale_lift_id_is_rejected(session_code):
    await session_manager.reset_for_next_lift(session_code)  # lift_id -> 1
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            join = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert join["session_state"]["lift_id"] == 1

            await ws.send_json({"type": "vote_lock", "color": "white", "lift_id": 0})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "lift_changed"
    assert session_manager.sessions[session_code]["judges"]["left"]["locked"] is False


async def test_vote_lock_with_stale_lift_id_and_missing_mandatory_reason_is_lift_changed(session_code):
    await session_manager.reset_for_next_lift(session_code)  # lift_id -> 1
    session_manager.sessions[session_code]["settings"]["require_reasons"] = True
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success

            await ws.send_json({"type": "vote_lock", "color": "red", "lift_id": 0})  # no reason
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "lift_changed"
    assert session_manager.sessions[session_code]["judges"]["left"]["locked"] is False


async def test_vote_lock_resend_after_reasons_made_mandatory_is_acked_with_stored_vote(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success
            await ws.send_json({"type": "vote_lock", "color": "red", "lift_id": 0})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["type"] == "vote_ack"

            session_manager.sessions[session_code]["settings"]["require_reasons"] = True
            await ws.send_json({"type": "vote_lock", "color": "red", "lift_id": 0})  # resend, no reason
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "vote_ack"
            assert msg["color"] == "red"


async def test_vote_lock_from_display_is_rejected(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "display"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success

            await ws.send_json({"type": "vote_lock", "color": "white"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "vote_rejected"
            assert msg["code"] == "invalid"


async def test_reset_for_next_lift_broadcasts_lift_id(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success

            await ws.send_json({"type": "next_lift"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg == {"type": "reset_for_next_lift", "lift_id": 1}


# ---- Role checks: side judges cannot send head-judge messages ----

@pytest.mark.parametrize("message", [
    {"type": "timer_start"},
    {"type": "timer_reset"},
    {"type": "next_lift"},
    {"type": "end_session_confirmed"},
    {"type": "settings_update", "showExplanations": True, "liftType": "deadlift", "requireReasons": True},
])
@pytest.mark.parametrize("role", ["left_judge", "right_judge"])
async def test_side_judge_cannot_send_head_judge_message(session_code, role, message):
    session = session_manager.sessions[session_code]
    session["timer_started_at"] = 1234.0
    session["judges"]["center"]["locked"] = True
    session["judges"]["center"]["current_vote"] = "white"
    before = copy.deepcopy(session)

    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": role})
            await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success

            await ws.send_json(message)
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

            assert msg["type"] == "error"
            assert session_code in session_manager.sessions
            after = session_manager.sessions[session_code]
            for key in ("timer_started_at", "phase", "state", "settings", "lift_id", "timer_frozen_ms"):
                assert after[key] == before[key], key
            assert after["judges"]["center"]["locked"] is True


async def test_vote_rejected_logs_info(session_code, caplog):
    async with _ws_client() as ac:
        with caplog.at_level(logging.INFO, logger="iron_verdict"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # join_success
                await ws.send_json({"type": "vote_lock", "color": "white", "lift_id": 99})
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)  # vote_rejected

    records = [r for r in caplog.records if r.getMessage() == "vote_rejected"]
    assert len(records) == 1
    assert records[0].code == "lift_changed"
    assert records[0].role == "left_judge"


# ---- Concurrent joins on the same role (#57) ----

async def _join_and_hold(code, role, token=None):
    """Join on its own connection and keep it open briefly so the winner still holds the slot."""
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            msg = {"type": "join", "session_code": code, "role": role}
            if token:
                msg["reconnect_token"] = token
            await ws.send_json(msg)
            reply = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
            await asyncio.sleep(0.2)
            return reply


async def test_concurrent_fresh_joins_on_same_role_only_one_succeeds(session_code):
    replies = await asyncio.gather(
        _join_and_hold(session_code, "left_judge"),
        _join_and_hold(session_code, "left_judge"),
    )
    assert sorted(r["type"] for r in replies) == ["join_error", "join_success"]
    error = next(r for r in replies if r["type"] == "join_error")
    assert error["message"] == "Role already taken"


async def test_concurrent_reconnects_with_same_token_only_one_succeeds(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as old_ws:
            await old_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            token = (await old_ws.receive_json())["reconnect_token"]

            replies = await asyncio.gather(
                _join_and_hold(session_code, "left_judge", token),
                _join_and_hold(session_code, "left_judge", token),
            )

    assert sorted(r["type"] for r in replies) == ["join_error", "join_success"]
    error = next(r for r in replies if r["type"] == "join_error")
    assert error["message"] == "Role already taken"
    winner = next(r for r in replies if r["type"] == "join_success")
    assert session_manager.sessions[session_code]["judges"]["left"]["reconnect_token"] == winner["reconnect_token"]


# ---- Orphaned connections (#136) ----

def _entries(code):
    from iron_verdict.main import connection_manager
    return dict(connection_manager.active_connections.get(code, {}))


async def test_second_join_on_same_connection_is_rejected_and_keeps_first_role(session_code, caplog):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "display"})
            assert (await ws.receive_json())["type"] == "join_success"
            with caplog.at_level(logging.WARNING, logger="iron_verdict"):
                await ws.send_json({"type": "join", "session_code": session_code, "role": "display"})
                reply = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert reply == {"type": "error", "message": "Already joined"}
            assert len(_entries(session_code)) == 1
        await asyncio.sleep(0.1)
    assert _entries(session_code) == {}
    assert [r.getMessage() for r in caplog.records].count("second_join_rejected") == 1


async def test_second_join_as_other_judge_does_not_take_the_other_role(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()
            await ws.send_json({"type": "join", "session_code": session_code, "role": "right_judge"})
            reply = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert reply == {"type": "error", "message": "Already joined"}
            assert list(_entries(session_code)) == ["left_judge"]
            assert session_manager.sessions[session_code]["judges"]["right"]["connected"] is False
        await asyncio.sleep(0.1)
    assert _entries(session_code) == {}
    assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is False


async def test_flood_disconnect_after_join_removes_connection_and_marks_judge_disconnected(session_code):
    async with _ws_client() as center_client, _ws_client() as left_client:
        async with httpx_ws.aconnect_ws("ws://test/ws", center_client) as center_ws:
            await center_ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
            await center_ws.receive_json()
            async with httpx_ws.aconnect_ws("ws://test/ws", left_client) as left_ws:
                await left_ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
                await left_ws.receive_json()
                assert (await center_ws.receive_json())["connected"] is True
                for _ in range(25):
                    try:
                        await left_ws.send_json({"type": "pong"})
                    except Exception:
                        break
                msg = await asyncio.wait_for(center_ws.receive_json(), timeout=1.0)
            assert msg == {"type": "judge_status_update", "position": "left", "connected": False}
            assert list(_entries(session_code)) == ["center_judge"]
            assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is False


async def test_unexpected_exception_in_handler_removes_connection(session_code, monkeypatch):
    async def boom(code):
        raise RuntimeError("boom")
    monkeypatch.setattr(session_manager, "reset_for_next_lift", boom)
    with pytest.raises(Exception):
        async with _ws_client() as ac:
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
                await ws.receive_json()
                await ws.send_json({"type": "next_lift"})
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)
    assert _entries(session_code) == {}
    assert session_manager.sessions[session_code]["judges"]["center"]["connected"] is False


async def test_heartbeat_removes_connection_when_ping_fails_and_logs_once(caplog):
    from unittest.mock import AsyncMock
    from iron_verdict.main import heartbeat_sweep
    from iron_verdict.connection import ConnectionManager

    manager = ConnectionManager()
    healthy, dead = AsyncMock(), AsyncMock()
    dead.send_json.side_effect = RuntimeError("Unexpected ASGI message 'websocket.send'")
    await manager.add_connection("ABCD1234", "display_1", healthy)
    await manager.add_connection("ABCD1234", "display_2", dead)

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        await heartbeat_sweep(manager, time.monotonic())
        await heartbeat_sweep(manager, time.monotonic())

    assert manager.active_connections == {"ABCD1234": {"display_1": healthy}}
    assert await manager.get_last_pong(dead) is None
    messages = [r.getMessage() for r in caplog.records]
    assert messages.count("heartbeat_dead_connection_removed") == 1
    assert "heartbeat_send_failed" not in messages
    assert healthy.send_json.await_count == 2


async def test_heartbeat_never_removes_newer_connection_of_same_role():
    from unittest.mock import AsyncMock
    from iron_verdict.main import heartbeat_sweep
    from iron_verdict.connection import ConnectionManager

    manager = ConnectionManager()
    old, new = AsyncMock(), AsyncMock()

    async def reconnect_then_fail(message):
        # A reconnect takes the role between the sweep's snapshot and the failed ping.
        await manager.add_connection("ABCD1234", "display_1", new)
        raise RuntimeError("closed")

    old.send_json.side_effect = reconnect_then_fail
    await manager.add_connection("ABCD1234", "display_1", old)

    await heartbeat_sweep(manager, time.monotonic())

    assert manager.active_connections == {"ABCD1234": {"display_1": new}}
    assert await manager.get_last_pong(new) is not None


async def test_heartbeat_removal_of_judge_marks_disconnected_and_notifies_others(session_code):
    from unittest.mock import AsyncMock
    from iron_verdict.main import heartbeat_sweep
    from iron_verdict.connection import ConnectionManager

    manager = ConnectionManager()
    center, dead_left = AsyncMock(), AsyncMock()
    dead_left.send_json.side_effect = RuntimeError("closed")
    session_manager.join_session(session_code, "center_judge")
    session_manager.join_session(session_code, "left_judge")
    await manager.add_connection(session_code, "center_judge", center)
    await manager.add_connection(session_code, "left_judge", dead_left)

    await heartbeat_sweep(manager, time.monotonic())

    assert session_manager.sessions[session_code]["judges"]["left"]["connected"] is False
    center.send_json.assert_any_await({"type": "judge_status_update", "position": "left", "connected": False})
    assert list(manager.active_connections[session_code]) == ["center_judge"]


async def test_heartbeat_removes_connection_after_stale_close_even_if_close_fails(caplog):
    from unittest.mock import AsyncMock
    from iron_verdict.main import heartbeat_sweep, PONG_STALE_SECONDS
    from iron_verdict.connection import ConnectionManager

    manager = ConnectionManager()
    stale = AsyncMock()
    stale.close.side_effect = RuntimeError("already closed")
    await manager.add_connection("ABCD1234", "display_1", stale)
    now = time.monotonic()
    manager._last_pong[stale] = now - (PONG_STALE_SECONDS + 1)

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        await heartbeat_sweep(manager, now)
        await heartbeat_sweep(manager, now + 5)

    assert manager.active_connections == {}
    messages = [r.getMessage() for r in caplog.records]
    assert messages.count("heartbeat_stale_close") == 1
    assert messages.count("heartbeat_close_failed") == 1


# ---- Pause (#163) ----

async def _recv(ws):
    return await asyncio.wait_for(ws.receive_json(), timeout=1.0)


async def test_display_pause_start_broadcasts_pause_update(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as display, \
                   httpx_ws.aconnect_ws("ws://test/ws", ac) as judge:
            await _join(judge, session_code, "center_judge")
            await _join(display, session_code, "display")
            before_ms = int(time.time() * 1000)
            await display.send_json({"type": "pause_start", "minutes": 10, "next_lift": "bench"})
            for ws in (display, judge):
                msg = await _recv(ws)
                assert msg["type"] == "pause_update"
                assert msg["pause"]["mode"] == "minutes"
                assert msg["pause"]["next_lift"] == "bench"
                assert msg["server_now_ms"] >= before_ms
                assert abs(msg["pause"]["end_at_ms"] - (msg["server_now_ms"] + 600_000)) < 1000
                assert "id" not in msg["pause"]
    assert session_manager.sessions[session_code]["pause"] is not None


async def test_pause_start_invalid_input_is_rejected_to_sender(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, session_code, "display")
            await ws.send_json({"type": "pause_start", "minutes": "ten", "next_lift": ["bench"]})
            assert await _recv(ws) == {"type": "pause_rejected", "code": "invalid"}


async def test_judge_cannot_start_or_end_pause(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, session_code, "center_judge")
            await ws.send_json({"type": "pause_start", "minutes": 5})
            assert (await _recv(ws))["type"] == "error"
            await ws.send_json({"type": "pause_end"})
            assert (await _recv(ws))["type"] == "error"
    assert session_manager.sessions[session_code]["pause"] is None


async def test_display_pause_end_broadcasts_cleared_pause(session_code):
    session_manager.start_pause(session_code, minutes=10)
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as display, \
                   httpx_ws.aconnect_ws("ws://test/ws", ac) as other:
            await _join(display, session_code, "display")
            await _join(other, session_code, "display")
            await display.send_json({"type": "pause_end"})
            for ws in (display, other):
                msg = await _recv(ws)
                assert msg["type"] == "pause_update"
                assert msg["pause"] is None
    assert session_manager.sessions[session_code]["pause"] is None


async def test_join_success_includes_running_pause_and_server_time(session_code):
    session_manager.start_pause(session_code, minutes=30, next_lift="deadlift")
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            msg = await _join(ws, session_code, "display")
    state = msg["session_state"]
    assert state["pause"]["mode"] == "minutes"
    assert state["pause"]["next_lift"] == "deadlift"
    assert "id" not in state["pause"] and "end_at" not in state["pause"]
    assert abs(state["pause"]["end_at_ms"] - (state["server_now_ms"] + 30 * 60_000)) < 1000


async def test_join_after_pause_end_leaves_the_end_broadcast_to_the_end_task(session_code, monkeypatch):
    """A join between end_at and the end task must not swallow the end: the
    task still ends the pause and broadcasts pause_update null (review #163)."""
    from iron_verdict import main as main_module

    pause = session_manager.start_pause(session_code, minutes=1, now=time.time() - 61)["pause"]
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            msg = await _join(ws, session_code, "display")
            assert msg["session_state"]["pause"]["end_at_ms"] <= msg["session_state"]["server_now_ms"]

            async def no_sleep(_seconds):
                pass

            await main_module.end_pause_when_due(session_code, pause["id"], pause["end_at"], sleep=no_sleep)
            update = await _recv(ws)
    assert update["type"] == "pause_update" and update["pause"] is None
    assert session_manager.sessions[session_code]["pause"] is None


async def test_timer_start_ends_pause_before_timer_starts(session_code):
    session_manager.start_pause(session_code, minutes=10)
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as head, \
                   httpx_ws.aconnect_ws("ws://test/ws", ac) as display:
            await _join(head, session_code, "center_judge")
            await _join(display, session_code, "display")
            await head.send_json({"type": "timer_start"})
            first = await _recv(display)
            second = await _recv(display)
    assert first["type"] == "pause_update" and first["pause"] is None
    assert second["type"] == "timer_start"
    assert session_manager.sessions[session_code]["pause"] is None


async def test_timer_start_without_pause_sends_no_pause_update(session_code):
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as head:
            await _join(head, session_code, "center_judge")
            await head.send_json({"type": "timer_start"})
            assert (await _recv(head))["type"] == "timer_start"


async def test_end_pause_when_due_ends_and_broadcasts(session_code, monkeypatch):
    from iron_verdict import main as main_module

    pause = session_manager.start_pause(session_code, minutes=5)["pause"]
    sent = []

    async def fake_broadcast(code, message):
        sent.append((code, message))

    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(main_module.connection_manager, "broadcast_to_session", fake_broadcast)
    await main_module.end_pause_when_due(session_code, pause["id"], pause["end_at"], sleep=fake_sleep)

    assert 299 < slept[0] <= 300
    assert session_manager.sessions[session_code]["pause"] is None
    assert sent == [(session_code, {"type": "pause_update", "pause": None, "server_now_ms": sent[0][1]["server_now_ms"]})]


async def test_end_pause_when_due_leaves_a_newer_pause_alone(session_code, monkeypatch):
    from iron_verdict import main as main_module

    old = session_manager.start_pause(session_code, minutes=5)["pause"]
    session_manager.start_pause(session_code, minutes=10)
    sent = []

    async def fake_broadcast(code, message):
        sent.append(message)

    async def fake_sleep(_seconds):
        pass

    monkeypatch.setattr(main_module.connection_manager, "broadcast_to_session", fake_broadcast)
    await main_module.end_pause_when_due(session_code, old["id"], old["end_at"], sleep=fake_sleep)

    assert session_manager.sessions[session_code]["pause"] is not None
    assert sent == []


async def test_schedule_pause_end_replaces_previous_timer(session_code):
    from iron_verdict import main as main_module

    session_manager.start_pause(session_code, minutes=5)
    main_module.schedule_pause_end(session_code)
    first = main_module._pause_end_tasks[session_code]
    session_manager.start_pause(session_code, minutes=10)
    main_module.schedule_pause_end(session_code)
    second = main_module._pause_end_tasks[session_code]
    await asyncio.sleep(0)
    assert first.cancelled()
    assert not second.done()
    session_manager.end_pause(session_code)
    main_module.schedule_pause_end(session_code)
    await asyncio.sleep(0)
    assert second.cancelled()
    assert session_code not in main_module._pause_end_tasks


async def test_restore_pause_timers_schedules_restored_pauses(session_code):
    from iron_verdict import main as main_module

    session_manager.start_pause(session_code, minutes=5)
    main_module._pause_end_tasks.pop(session_code, None)
    main_module.restore_pause_timers()
    task = main_module._pause_end_tasks[session_code]
    assert not task.done()
    task.cancel()
    main_module._pause_end_tasks.pop(session_code, None)
