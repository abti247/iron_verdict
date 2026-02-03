import pytest
from judgeme.connection import ConnectionManager


@pytest.mark.asyncio
async def test_add_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    manager.add_connection("ABC123", "left_judge", mock_ws)

    assert "ABC123" in manager.active_connections
    assert "left_judge" in manager.active_connections["ABC123"]


@pytest.mark.asyncio
async def test_remove_connection():
    manager = ConnectionManager()
    mock_ws = "mock_websocket"

    manager.add_connection("ABC123", "left_judge", mock_ws)
    manager.remove_connection("ABC123", "left_judge")

    assert "left_judge" not in manager.active_connections.get("ABC123", {})
