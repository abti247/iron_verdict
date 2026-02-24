# P2: WebSocket Connection ID Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `conn_id` field to all WebSocket log lines so a single client's full connection lifecycle can be traced in isolation.

**Architecture:** Generate `secrets.token_hex(8)` at WS connect time; pass as `extra` in every log call inside `websocket_endpoint`; register `conn_id` in `_EXTRA_FIELDS` so `JsonFormatter` includes it automatically.

**Tech Stack:** Python, FastAPI, standard `logging`, `secrets` (already imported)

---

### Task 1: Register `conn_id` in the JSON formatter

**Files:**
- Modify: `src/iron_verdict/logging_config.py:6-9`
- Test: `tests/test_logging_config.py`

**Step 1: Write the failing test**

Add to `tests/test_logging_config.py`:

```python
def test_json_formatter_includes_conn_id():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.INFO, pathname="", lineno=0,
        msg="role_joined", args=(), exc_info=None
    )
    record.conn_id = "abc12345def67890"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["conn_id"] == "abc12345def67890"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_logging_config.py::test_json_formatter_includes_conn_id -v
```

Expected: FAIL — `conn_id` absent from JSON output.

**Step 3: Implement**

In `src/iron_verdict/logging_config.py`, add `"conn_id"` to `_EXTRA_FIELDS`:

```python
_EXTRA_FIELDS = (
    "session_code", "role", "client_ip", "color",
    "position", "all_locked", "reason", "origin", "conn_id",
)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_logging_config.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add tests/test_logging_config.py src/iron_verdict/logging_config.py
git commit -m "feat: register conn_id in JSON log formatter"
```

---

### Task 2: Generate and propagate `conn_id` in the WebSocket handler

**Files:**
- Modify: `src/iron_verdict/main.py:148-467`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Add to `tests/test_main.py`. This test verifies that all log records emitted during a WS connection share the same `conn_id`.

```python
@pytest.mark.asyncio
async def test_ws_logs_include_conn_id(session_code, caplog):
    """All log records from one WS connection share a conn_id."""
    import logging
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py::test_ws_logs_include_conn_id -v
```

Expected: FAIL — `ws_records` is empty (no `conn_id` on any records).

**Step 3: Implement**

In `src/iron_verdict/main.py`, inside `websocket_endpoint`, generate `conn_id` immediately after the function signature and add it to every `extra={}` dict.

At line 149 (right after `async def websocket_endpoint(websocket: WebSocket):`), add:

```python
conn_id = secrets.token_hex(8)
```

Then update every `logger.*` call in the function to include `conn_id=conn_id`. Here are all the call sites with their updated `extra` dicts:

```python
# origin_rejected (~line 152)
logger.warning("origin_rejected", extra={
    "conn_id": conn_id,
    "origin": origin,
    "client_ip": _get_ws_client_ip(websocket),
})

# message_flood_disconnect (~line 177)
logger.warning("message_flood_disconnect", extra={
    "conn_id": conn_id,
    "client_ip": _get_ws_client_ip(websocket),
})

# role_join_failed (~line 208)
logger.warning("role_join_failed", extra={
    "conn_id": conn_id,
    "session_code": session_code,
    "role": message.get("role"),
    "reason": result["error"],
    "client_ip": _get_ws_client_ip(websocket),
})

# role_joined (~line 233)
logger.info("role_joined", extra={
    "conn_id": conn_id,
    "session_code": session_code,
    "role": "display" if role.startswith("display_") else role,
    "client_ip": _get_ws_client_ip(websocket),
})

# vote_locked (~line 290)
logger.info("vote_locked", extra={
    "conn_id": conn_id,
    "session_code": session_code,
    "position": position,
    "color": color,
    "all_locked": result.get("all_locked", False),
})

# timer_start (~line 338)
logger.info("timer_start", extra={"conn_id": conn_id, "session_code": session_code})

# timer_reset (~line 360)
logger.info("timer_reset", extra={"conn_id": conn_id, "session_code": session_code})

# next_lift (~line 379)
logger.info("next_lift", extra={"conn_id": conn_id, "session_code": session_code})

# session_ended (~line 398)
logger.info("session_ended", extra={"conn_id": conn_id, "session_code": session_code})

# ws_close_failed (~line 412)
logger.warning("ws_close_failed", exc_info=True, extra={"conn_id": conn_id})

# role_disconnected (~line 458)
logger.info("role_disconnected", extra={
    "conn_id": conn_id,
    "session_code": session_code,
    "role": "display" if role.startswith("display_") else role,
})
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_main.py::test_ws_logs_include_conn_id -v
```

Expected: PASS.

**Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS.

**Step 6: Commit**

```bash
git add src/iron_verdict/main.py tests/test_main.py
git commit -m "feat: add conn_id to WebSocket log lines for connection tracing"
```
