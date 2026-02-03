import pytest
from unittest.mock import AsyncMock
from judgeme.connection import ConnectionManager


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
