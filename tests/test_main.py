import asyncio
import pytest
import httpx
import httpx_ws
from httpx_ws.transport import ASGIWebSocketTransport
from fastapi.testclient import TestClient
from judgeme.main import app, session_manager


client = TestClient(app)


@pytest.fixture
def session_code():
    """Create a fresh session and return its code."""
    code = session_manager.create_session("Test Session")
    yield code
    if code in session_manager.sessions:
        session_manager.delete_session(code)


def test_create_session_returns_code():
    response = client.post("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_code" in data
    assert len(data["session_code"]) == 6


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
