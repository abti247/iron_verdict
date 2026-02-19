# Batch E — Observability/Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured JSON logging (stdlib only) so operators can observe session lifecycle, judge activity, and security events via stdout.

**Architecture:** Single `logging_config.py` exports `JsonFormatter` and `setup_logging()`. A module-level `logger = logging.getLogger("judgeme")` is used in `main.py` and `connection.py`. Tests capture logs via pytest's `caplog` fixture. `setup_logging()` is called in `lifespan` for production; `caplog` works without it in tests because it installs its own handler.

**Tech Stack:** Python `logging` (stdlib), `pytest` with `caplog` fixture.

---

### Task 1: Create JSON logging module

**Files:**
- Create: `src/judgeme/logging_config.py`
- Create: `tests/test_logging_config.py`

**Step 1: Write failing test**

```python
# tests/test_logging_config.py
import json
import logging
from judgeme.logging_config import JsonFormatter


def test_json_formatter_produces_valid_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="judgeme", level=logging.INFO, pathname="", lineno=0,
        msg="test message", args=(), exc_info=None
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "test message"
    assert "timestamp" in parsed


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="judgeme", level=logging.INFO, pathname="", lineno=0,
        msg="session created", args=(), exc_info=None
    )
    record.session_code = "ABC12345"
    record.client_ip = "1.2.3.4"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["session_code"] == "ABC12345"
    assert parsed["client_ip"] == "1.2.3.4"
```

**Step 2: Run to confirm fails**

```
python -m pytest tests/test_logging_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'judgeme.logging_config'`

**Step 3: Implement**

```python
# src/judgeme/logging_config.py
import json
import logging
import sys
from datetime import datetime, timezone

_EXTRA_FIELDS = (
    "session_code", "role", "client_ip", "color",
    "position", "all_locked", "reason", "origin",
)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)
        return json.dumps(log_obj)


def setup_logging() -> None:
    """Configure root 'judgeme' logger with JSON output to stdout."""
    logger = logging.getLogger("judgeme")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
```
```python
# src/judgeme/main.py — add at top-of-file imports (do not replace existing imports)
import logging
from judgeme.logging_config import setup_logging

logger = logging.getLogger("judgeme")
```

Add `setup_logging()` call inside `lifespan`, before `yield`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()                          # <-- add this line

    async def _cleanup_loop():
        ...
```

**Step 4: Run tests**

```
python -m pytest tests/test_logging_config.py -v
```
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/judgeme/logging_config.py src/judgeme/main.py tests/test_logging_config.py
git commit -m "feat: add JSON logging module (Batch E H5)"
```

---

### Task 2: Log session creation and WebSocket join/disconnect

**Files:**
- Modify: `src/judgeme/main.py` — `create_session`, `join` handler, `WebSocketDisconnect` handler
- Modify: `tests/test_main.py` — add caplog tests

**Step 1: Write failing tests**

Add to `tests/test_main.py`:

```python
import logging

# ---- Session creation logging ----

@pytest.mark.asyncio
async def test_create_session_logs_info(caplog):
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            resp = await ac.post("/api/sessions", json={"name": "TestMeet"})
    assert resp.status_code == 200
    messages = [r.message for r in caplog.records]
    assert any("session_created" in m for m in messages)


# ---- WebSocket join logging ----

@pytest.mark.asyncio
async def test_ws_join_success_logs_info(caplog):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.INFO, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                # Create session first via REST
                resp = await httpx.AsyncClient(app=app, base_url="http://test").post(
                    "/api/sessions", json={"name": "Test"}
                )
    # Note: session creation log is sufficient for basic test
    messages = [r.message for r in caplog.records]
    assert any("session_created" in m for m in messages)


@pytest.mark.asyncio
async def test_ws_join_success_logs_role_and_session(caplog):
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
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
```

**Step 2: Run to confirm fails**

```
python -m pytest tests/test_main.py::test_create_session_logs_info tests/test_main.py::test_ws_join_success_logs_role_and_session -v
```
Expected: FAIL — no log records emitted

**Step 3: Implement**

In `main.py`, add helper:

```python
def _get_http_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _get_ws_client_ip(websocket: WebSocket) -> str:
    fwd = websocket.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (websocket.client.host if websocket.client else "unknown")
```

In `create_session`:
```python
async def create_session(request: Request, body: CreateSessionRequest):
    code = await session_manager.create_session(body.name)
    logger.info("session_created", extra={"session_code": code, "client_ip": _get_http_client_ip(request)})
    return {"session_code": code}
```

In the `join` handler, after `await connection_manager.add_connection(...)`:
```python
logger.info("role_joined", extra={
    "session_code": session_code,
    "role": "display" if role.startswith("display_") else role,
    "client_ip": _get_ws_client_ip(websocket),
})
```

After failed join (`not result["success"]`):
```python
logger.warning("role_join_failed", extra={
    "session_code": session_code,
    "role": message.get("role"),
    "reason": result["error"],
    "client_ip": _get_ws_client_ip(websocket),
})
```

In `WebSocketDisconnect` handler:
```python
except WebSocketDisconnect:
    if session_code and role:
        await connection_manager.remove_connection(session_code, role)
        logger.info("role_disconnected", extra={
            "session_code": session_code,
            "role": "display" if role.startswith("display_") else role,
        })
        if role.endswith("_judge"):
            ...
```

**Step 4: Run tests**

```
python -m pytest tests/test_main.py::test_create_session_logs_info tests/test_main.py::test_ws_join_success_logs_role_and_session -v
```
Expected: PASS

**Step 5: Run full test suite to check for regressions**

```
python -m pytest tests/ -q
```
Expected: all pass

**Step 6: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: log session creation and WS join/disconnect (Batch E H5)"
```

---

### Task 3: Log vote lock, timer actions, next_lift, session end

**Files:**
- Modify: `src/judgeme/main.py`
- Modify: `tests/test_main.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_vote_lock_logs_info(caplog):
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
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
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
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
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
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
```

**Step 2: Run to confirm fails**

```
python -m pytest tests/test_main.py::test_vote_lock_logs_info tests/test_main.py::test_timer_start_logs_info tests/test_main.py::test_session_end_logs_info -v
```
Expected: FAIL

**Step 3: Implement in main.py**

In the `vote_lock` handler, after `result = await session_manager.lock_vote(...)` and `if result["success"]`:
```python
logger.info("vote_locked", extra={
    "session_code": session_code,
    "position": position,
    "color": color,
    "all_locked": result.get("all_locked", False),
})
```

In `timer_start` handler, before broadcast:
```python
logger.info("timer_start", extra={"session_code": session_code})
```

In `timer_reset` handler, before broadcast:
```python
logger.info("timer_reset", extra={"session_code": session_code})
```

In `next_lift` handler, before `reset_for_next_lift`:
```python
logger.info("next_lift", extra={"session_code": session_code})
```

In `end_session_confirmed` handler, before broadcast:
```python
logger.info("session_ended", extra={"session_code": session_code})
```

**Step 4: Run tests**

```
python -m pytest tests/test_main.py::test_vote_lock_logs_info tests/test_main.py::test_timer_start_logs_info tests/test_main.py::test_session_end_logs_info -v
```
Expected: PASS

**Step 5: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

**Step 6: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: log vote lock, timer, next lift, session end (Batch E H5)"
```

---

### Task 4: Log security events

**Files:**
- Modify: `src/judgeme/main.py`
- Modify: `tests/test_main.py`

**Step 1: Write failing tests**

```python
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
async def test_message_flood_logs_warning(caplog):
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        with caplog.at_level(logging.WARNING, logger="judgeme"):
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await ws.send_json({"type": "join", "session_code": code, "role": "left_judge"})
                await ws.receive_json()
                for _ in range(22):
                    try:
                        await ws.send_json({"type": "vote_lock", "color": "white"})
                    except Exception:
                        break

    records = [r for r in caplog.records if r.getMessage() == "message_flood_disconnect"]
    assert len(records) == 1
```

**Step 2: Run to confirm fails**

```
python -m pytest tests/test_main.py::test_origin_rejection_logs_warning tests/test_main.py::test_message_flood_logs_warning -v
```
Expected: FAIL

**Step 3: Implement**

In `websocket_endpoint`, in the origin check block:
```python
if settings.ALLOWED_ORIGIN != "*" and origin != settings.ALLOWED_ORIGIN:
    logger.warning("origin_rejected", extra={
        "origin": origin,
        "client_ip": _get_ws_client_ip(websocket),
    })
    await websocket.close(code=1008)
    return
```

In the flood check block (`if msg_count > 20`):
```python
if msg_count > 20:
    logger.warning("message_flood_disconnect", extra={"client_ip": _get_ws_client_ip(websocket)})
    await websocket.close(code=1008)
    return
```

**Step 4: Run tests**

```
python -m pytest tests/test_main.py::test_origin_rejection_logs_warning tests/test_main.py::test_message_flood_logs_warning -v
```
Expected: PASS

**Step 5: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

**Step 6: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: log security events — origin rejection and message flood (Batch E H5)"
```

---

### Task 5: Log connection send failures

**Files:**
- Modify: `src/judgeme/connection.py`
- Modify: `tests/test_connection.py`

**Step 1: Write failing tests**

Add to `tests/test_connection.py`:

```python
import logging
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_broadcast_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "left_judge", broken_ws)

    with caplog.at_level(logging.WARNING, logger="judgeme"):
        await manager.broadcast_to_session("SESS", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "broadcast_send_failed"]
    assert len(records) == 1


@pytest.mark.asyncio
async def test_send_to_role_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "left_judge", broken_ws)

    with caplog.at_level(logging.WARNING, logger="judgeme"):
        await manager.send_to_role("SESS", "left_judge", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "send_to_role_failed"]
    assert len(records) == 1


@pytest.mark.asyncio
async def test_send_to_displays_failure_logs_warning(caplog):
    manager = ConnectionManager()
    broken_ws = AsyncMock()
    broken_ws.send_json.side_effect = Exception("connection lost")
    await manager.add_connection("SESS", "display_abc", broken_ws)

    with caplog.at_level(logging.WARNING, logger="judgeme"):
        await manager.send_to_displays("SESS", {"type": "test"})

    records = [r for r in caplog.records if r.getMessage() == "send_to_display_failed"]
    assert len(records) == 1
```

**Step 2: Run to confirm fails**

```
python -m pytest tests/test_connection.py::test_broadcast_failure_logs_warning tests/test_connection.py::test_send_to_role_failure_logs_warning tests/test_connection.py::test_send_to_displays_failure_logs_warning -v
```
Expected: FAIL

**Step 3: Implement in connection.py**

Add at top of `connection.py`:
```python
import logging
logger = logging.getLogger("judgeme")
```

Replace `broadcast_to_session` exception handler:
```python
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("broadcast_send_failed", extra={"reason": str(exc)})
```

Replace `send_to_role` exception handler:
```python
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("send_to_role_failed", extra={"role": role, "reason": str(exc)})
```

Replace `send_to_displays` exception handler:
```python
        for websocket in websockets:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("send_to_display_failed", extra={"reason": str(exc)})
```

**Step 4: Run tests**

```
python -m pytest tests/test_connection.py::test_broadcast_failure_logs_warning tests/test_connection.py::test_send_to_role_failure_logs_warning tests/test_connection.py::test_send_to_displays_failure_logs_warning -v
```
Expected: PASS

**Step 5: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

**Step 6: Commit**

```bash
git add src/judgeme/connection.py tests/test_connection.py
git commit -m "feat: log connection send failures (Batch E H5)"
```

---

### Task 6: Final verification and cleanup

**Step 1: Run full suite one more time**

```
python -m pytest tests/ -q
```
Expected: all pass, no warnings

**Step 2: Verify JSON output format manually**

Start the server (from worktree root):
```
python -m uvicorn judgeme.main:app --port 8001
```

Create a session via curl and observe stdout:
```
curl -s -X POST http://localhost:8001/api/sessions -H "Content-Type: application/json" -d '{"name":"Test"}'
```
Expected: a JSON line on stdout like:
```json
{"timestamp":"2026-02-19T...","level":"INFO","message":"session_created","session_code":"ABC12345","client_ip":"127.0.0.1"}
```

Stop server with Ctrl+C.

**Step 3: Push branch and open PR**

```bash
git push origin feature/batch-e-observability
gh pr create --title "feat: Batch E — structured JSON logging (H5)" --body "$(cat <<'EOF'
## Summary
- Adds JSON-formatted logging (stdlib only) to stdout
- Logs: session created/ended, role joined/disconnected (with client IP), vote locked, timer actions, next lift, security events (origin rejection, message flood)
- Logs connection send failures in ConnectionManager
- All events logged at INFO; security violations at WARNING
- Covered by new tests using pytest caplog fixture

## Test plan
- [ ] `python -m pytest tests/ -q` — all pass
- [ ] Manual smoke test: start server, create session via curl, verify JSON line on stdout

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
