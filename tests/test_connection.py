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


@pytest.mark.asyncio
async def test_get_connection_returns_registered_websocket():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    await manager.add_connection("ABC123", "left_judge", mock_ws)
    result = await manager.get_connection("ABC123", "left_judge")
    assert result is mock_ws


@pytest.mark.asyncio
async def test_get_connection_returns_none_when_not_found():
    manager = ConnectionManager()
    result = await manager.get_connection("ABC123", "left_judge")
    assert result is None


@pytest.mark.asyncio
async def test_broadcast_to_others_skips_excluded_websocket():
    manager = ConnectionManager()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    mock_ws3 = AsyncMock()

    await manager.add_connection("ABC123", "left_judge", mock_ws1)
    await manager.add_connection("ABC123", "center_judge", mock_ws2)
    await manager.add_connection("ABC123", "right_judge", mock_ws3)

    await manager.broadcast_to_others("ABC123", mock_ws1, {"type": "test"})

    mock_ws1.send_json.assert_not_called()
    mock_ws2.send_json.assert_called_once_with({"type": "test"})
    mock_ws3.send_json.assert_called_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_to_others_no_op_for_nonexistent_session():
    manager = ConnectionManager()
    # Should not raise
    await manager.broadcast_to_others("INVALID", AsyncMock(), {"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_to_others_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    other_ws = AsyncMock()
    await manager.add_connection("SESS", "left_judge", broken_ws)
    await manager.add_connection("SESS", "center_judge", other_ws)

    with caplog.at_level(logging.WARNING, logger="iron_verdict"):
        await manager.broadcast_to_others("SESS", other_ws, {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "broadcast_to_others_send_failed"]
    assert len(records) == 1


import asyncio


@pytest.mark.asyncio
async def test_add_connection_initializes_last_pong():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    await manager.add_connection("ABC123", "left_judge", mock_ws)
    assert mock_ws in manager._last_pong
    assert isinstance(manager._last_pong[mock_ws], float)


@pytest.mark.asyncio
async def test_remove_connection_cleans_up_last_pong():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    await manager.add_connection("ABC123", "left_judge", mock_ws)
    await manager.remove_connection("ABC123", "left_judge")
    assert mock_ws not in manager._last_pong


@pytest.mark.asyncio
async def test_mark_pong_updates_timestamp():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    await manager.add_connection("ABC123", "left_judge", mock_ws)
    first = manager._last_pong[mock_ws]
    await asyncio.sleep(0.01)
    await manager.mark_pong(mock_ws)
    assert manager._last_pong[mock_ws] > first


@pytest.mark.asyncio
async def test_mark_pong_noop_for_unknown_websocket():
    manager = ConnectionManager()
    unknown_ws = AsyncMock()
    # Should not raise
    await manager.mark_pong(unknown_ws)
    assert unknown_ws not in manager._last_pong


@pytest.mark.asyncio
async def test_get_last_pong_returns_float_for_known_ws():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    await manager.add_connection("ABC123", "left_judge", mock_ws)
    result = await manager.get_last_pong(mock_ws)
    assert isinstance(result, float)


@pytest.mark.asyncio
async def test_get_last_pong_returns_none_for_unknown_ws():
    manager = ConnectionManager()
    result = await manager.get_last_pong(AsyncMock())
    assert result is None


@pytest.mark.asyncio
async def test_get_all_connections_returns_all_entries():
    manager = ConnectionManager()
    ws1, ws2 = AsyncMock(), AsyncMock()
    await manager.add_connection("S1", "left_judge", ws1)
    await manager.add_connection("S1", "center_judge", ws2)
    result = await manager.get_all_connections()
    assert len(result) == 2
    codes = {r[0] for r in result}
    roles = {r[1] for r in result}
    sockets = {r[2] for r in result}
    assert codes == {"S1"}
    assert roles == {"left_judge", "center_judge"}
    assert sockets == {ws1, ws2}


@pytest.mark.asyncio
async def test_get_all_connections_returns_empty_when_none():
    manager = ConnectionManager()
    result = await manager.get_all_connections()
    assert result == []
