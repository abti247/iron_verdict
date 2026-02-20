import logging
import pytest
from unittest.mock import AsyncMock
from iron_verdict.connection import ConnectionManager


@pytest.mark.asyncio
async def test_add_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    await manager.add_connection("ABC123", "left_judge", mock_ws)

    assert "ABC123" in manager.active_connections
    assert "left_judge" in manager.active_connections["ABC123"]


@pytest.mark.asyncio
async def test_remove_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    await manager.add_connection("ABC123", "left_judge", mock_ws)
    await manager.remove_connection("ABC123", "left_judge")

    assert "left_judge" not in manager.active_connections.get("ABC123", {})


@pytest.mark.asyncio
async def test_broadcast_to_session():
    manager = ConnectionManager()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()

    await manager.add_connection("ABC123", "left_judge", mock_ws1)
    await manager.add_connection("ABC123", "center_judge", mock_ws2)

    await manager.broadcast_to_session("ABC123", {"type": "test"})

    mock_ws1.send_json.assert_called_once_with({"type": "test"})
    mock_ws2.send_json.assert_called_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_send_to_role():
    manager = ConnectionManager()
    mock_ws = AsyncMock()

    await manager.add_connection("ABC123", "left_judge", mock_ws)

    await manager.send_to_role("ABC123", "left_judge", {"type": "test"})

    mock_ws.send_json.assert_called_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_to_nonexistent_session():
    manager = ConnectionManager()
    # Should not raise exception
    await manager.broadcast_to_session("INVALID", {"type": "test"})


@pytest.mark.asyncio
async def test_send_to_nonexistent_role():
    manager = ConnectionManager()
    # Should not raise exception
    await manager.send_to_role("ABC123", "nonexistent", {"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_handles_failed_websocket():
    manager = ConnectionManager()
    mock_ws_good = AsyncMock()
    mock_ws_bad = AsyncMock()
    mock_ws_bad.send_json.side_effect = Exception("Connection closed")

    await manager.add_connection("ABC123", "left_judge", mock_ws_good)
    await manager.add_connection("ABC123", "center_judge", mock_ws_bad)

    # Should not raise exception
    await manager.broadcast_to_session("ABC123", {"type": "test"})

    # Good connection should still receive message
    mock_ws_good.send_json.assert_called_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_send_to_role_handles_failed_websocket():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.send_json.side_effect = Exception("Connection closed")

    await manager.add_connection("ABC123", "left_judge", mock_ws)

    # Should not raise exception
    await manager.send_to_role("ABC123", "left_judge", {"type": "test"})


@pytest.mark.asyncio
async def test_count_displays_returns_zero_for_empty_session():
    manager = ConnectionManager()
    assert await manager.count_displays("ABC123") == 0


@pytest.mark.asyncio
async def test_count_displays_counts_only_display_connections():
    manager = ConnectionManager()
    await manager.add_connection("ABC123", "display_aabb1122", AsyncMock())
    await manager.add_connection("ABC123", "display_ccdd3344", AsyncMock())
    await manager.add_connection("ABC123", "left_judge", AsyncMock())

    assert await manager.count_displays("ABC123") == 2


@pytest.mark.asyncio
async def test_send_to_displays_sends_to_all_displays():
    manager = ConnectionManager()
    mock_display1 = AsyncMock()
    mock_display2 = AsyncMock()
    mock_judge = AsyncMock()

    await manager.add_connection("ABC123", "display_aabb1122", mock_display1)
    await manager.add_connection("ABC123", "display_ccdd3344", mock_display2)
    await manager.add_connection("ABC123", "left_judge", mock_judge)

    message = {"type": "judge_voted", "position": "left"}
    await manager.send_to_displays("ABC123", message)

    mock_display1.send_json.assert_called_once_with(message)
    mock_display2.send_json.assert_called_once_with(message)
    mock_judge.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_displays_no_op_for_empty_session():
    manager = ConnectionManager()
    # Should not raise
    await manager.send_to_displays("INVALID", {"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "left_judge", broken_ws)

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        await manager.broadcast_to_session("SESS", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "broadcast_send_failed"]
    assert len(records) == 1


@pytest.mark.asyncio
async def test_send_to_role_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "left_judge", broken_ws)

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        await manager.send_to_role("SESS", "left_judge", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "send_to_role_failed"]
    assert len(records) == 1


@pytest.mark.asyncio
async def test_send_to_displays_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "display_abc", broken_ws)

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        await manager.send_to_displays("SESS", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "send_to_display_failed"]
    assert len(records) == 1
