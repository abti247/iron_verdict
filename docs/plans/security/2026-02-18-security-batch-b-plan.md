# Security Hardening Batch B Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement C2 (session cleanup), M3 (asyncio lock on SessionManager), and L2 (display cap with UUID-per-display).

**Architecture:** Three independent changes to server internals — a background cleanup task, a lock on shared mutable state, and a unique-key-per-display scheme that replaces the broken single-slot approach in ConnectionManager. No new dependencies.

**Tech Stack:** Python 3.11, FastAPI, asyncio, pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` required, but existing tests already have it so keep it for consistency).

---

## Task 1: C2a — Add `cleanup_expired()` to SessionManager

**Files:**
- Modify: `src/judgeme/session.py`
- Test: `tests/test_session.py`

**Background:** `get_expired_sessions(hours)` and `delete_session(code)` already exist. `cleanup_expired` is a thin wrapper that drives them. It stays synchronous — no lock needed, because it only targets sessions whose `last_activity` predates any concurrent creates.

---

**Step 1: Write the failing test**

Add to the end of `tests/test_session.py`:

```python
def test_cleanup_expired_removes_stale_keeps_fresh():
    manager = SessionManager()
    old_code = manager.create_session("Old")
    new_code = manager.create_session("New")
    manager.sessions[old_code]["last_activity"] = datetime.now() - timedelta(hours=5)

    manager.cleanup_expired(hours=4)

    assert old_code not in manager.sessions
    assert new_code in manager.sessions
```

**Step 2: Run the test and verify it fails**

```
pytest tests/test_session.py::test_cleanup_expired_removes_stale_keeps_fresh -v
```

Expected: `FAILED` — `AttributeError: 'SessionManager' object has no attribute 'cleanup_expired'`

**Step 3: Implement `cleanup_expired()` in `session.py`**

Add after `delete_session`:

```python
def cleanup_expired(self, hours: int) -> None:
    """Delete all sessions inactive for longer than `hours`."""
    expired = self.get_expired_sessions(hours)
    for code in expired:
        self.delete_session(code)
```

**Step 4: Run the test and verify it passes**

```
pytest tests/test_session.py::test_cleanup_expired_removes_stale_keeps_fresh -v
```

Expected: `PASSED`

**Step 5: Run the full suite**

```
pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add cleanup_expired to SessionManager (C2)"
```

---

## Task 2: C2b — Add lifespan startup task to main.py

**Files:**
- Modify: `src/judgeme/main.py`

**Background:** FastAPI's `lifespan` context manager replaces the old `@app.on_event("startup")` pattern. The background task sleeps 30 minutes, then cleans up, forever, until the app shuts down and cancels it.

---

**Step 1: Add imports to `main.py`**

At the top of `src/judgeme/main.py`, add two imports:

```python
import asyncio
from contextlib import asynccontextmanager
```

Full import block after change:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from judgeme.config import settings
from judgeme.session import SessionManager
from judgeme.connection import ConnectionManager
import asyncio
from contextlib import asynccontextmanager
import json
import copy
import time
import os
```

**Step 2: Add the lifespan function**

Insert this block **before** the `app = FastAPI(...)` line:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(30 * 60)
            session_manager.cleanup_expired(settings.SESSION_TIMEOUT_HOURS)

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

**Step 3: Wire lifespan into the app**

Change:

```python
app = FastAPI(title="JudgeMe")
```

To:

```python
app = FastAPI(title="JudgeMe", lifespan=lifespan)
```

**Step 4: Run the full suite**

```
pytest -v
```

Expected: all tests pass. (No new tests — background task scheduling is not unit-tested here.)

**Step 5: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: add lifespan cleanup task, runs every 30 min (C2)"
```

---

## Task 3: M3 — AsyncIO lock on SessionManager (create_session, lock_vote, reset_for_next_lift)

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `src/judgeme/main.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_main.py`

**Background:** Making a method `async` removes its implicit atomicity (Python only context-switches at `await` points). The `asyncio.Lock` restores atomicity. `ConnectionManager` already follows this exact pattern — see `src/judgeme/connection.py`. `delete_session` and `update_settings` are not locked per design (they don't have check-then-act patterns that need protection).

---

**Step 1: Add asyncio lock and convert the three methods in `session.py`**

Add `import asyncio` at the top of `src/judgeme/session.py`:

```python
import asyncio
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List
```

Update `SessionManager.__init__`:

```python
def __init__(self):
    self.sessions: Dict[str, Dict[str, Any]] = {}
    self._lock = asyncio.Lock()
```

Replace `create_session` (was sync, now async):

```python
async def create_session(self, name: str) -> str:
    """Create a new session and return its code."""
    async with self._lock:
        code = self.generate_session_code()
        self.sessions[code] = {
            "name": name,
            "judges": {
                "left": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
                "center": {
                    "connected": False,
                    "is_head": True,
                    "current_vote": None,
                    "locked": False,
                },
                "right": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
            },
            "displays": [],
            "state": "waiting",
            "timer_state": "idle",
            "settings": {
                "show_explanations": False,
                "lift_type": "squat",
            },
            "last_activity": datetime.now(),
        }
        return code
```

Replace `lock_vote` (was sync, now async):

```python
async def lock_vote(self, code: str, position: str, color: str) -> Dict[str, Any]:
    """Lock in a judge's vote."""
    async with self._lock:
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]
        judge = session["judges"][position]

        judge["current_vote"] = color
        judge["locked"] = True
        session["last_activity"] = datetime.now()

        all_locked = all(
            j["locked"] for j in session["judges"].values() if j["connected"]
        )

        if all_locked:
            session["state"] = "showing_results"

        return {"success": True, "all_locked": all_locked}
```

Replace `reset_for_next_lift` (was sync, now async):

```python
async def reset_for_next_lift(self, code: str) -> Dict[str, Any]:
    """Reset session state for next lift."""
    async with self._lock:
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]

        for judge in session["judges"].values():
            judge["current_vote"] = None
            judge["locked"] = False

        session["state"] = "waiting"
        session["last_activity"] = datetime.now()

        return {"success": True}
```

**Step 2: Update callers in `main.py`**

Three call sites need `await` added.

In `POST /api/sessions`:
```python
# Before:
code = session_manager.create_session(request.name)
# After:
code = await session_manager.create_session(request.name)
```

In the `vote_lock` handler:
```python
# Before:
result = session_manager.lock_vote(session_code, position, color)
# After:
result = await session_manager.lock_vote(session_code, position, color)
```

In the `next_lift` handler:
```python
# Before:
session_manager.reset_for_next_lift(session_code)
# After:
await session_manager.reset_for_next_lift(session_code)
```

**Step 3: Update `tests/test_session.py`**

Every test that calls `create_session`, `lock_vote`, or `reset_for_next_lift` must become `async def` and use `await`. Tests that only call `generate_session_code`, `join_session`, `update_settings`, `get_expired_sessions`, `delete_session`, or `cleanup_expired` need no changes.

The following tests need converting. For each: change `def` to `async def` and add `await` before the relevant call(s).

```python
# create_session calls — 12 tests:
async def test_create_session_returns_code():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert len(code) == 8
    assert code in manager.sessions


async def test_create_session_initializes_structure():
    manager = SessionManager()
    code = await manager.create_session("Test")
    session = manager.sessions[code]
    assert "judges" in session
    assert "left" in session["judges"]
    assert "center" in session["judges"]
    assert "right" in session["judges"]
    assert "displays" in session
    assert session["state"] == "waiting"
    assert session["timer_state"] == "idle"
    assert "last_activity" in session


async def test_join_session_as_judge_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["connected"] is True


async def test_join_session_role_already_taken_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    result = manager.join_session(code, "left_judge")
    assert result["success"] is False
    assert "already taken" in result["error"]


async def test_join_session_as_display_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert len(manager.sessions[code]["displays"]) == 1


async def test_join_session_invalid_role_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "admin")
    assert result["success"] is False
    assert "Invalid role" in result["error"]


# lock_vote calls — 4 tests:
async def test_lock_vote_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    result = await manager.lock_vote(code, "left", "white")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "white"
    assert manager.sessions[code]["judges"]["left"]["locked"] is True


async def test_lock_vote_invalid_session_fails():
    manager = SessionManager()
    result = await manager.lock_vote("INVALID", "left", "white")
    assert result["success"] is False


async def test_lock_vote_updates_last_activity():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    before = manager.sessions[code]["last_activity"]
    await manager.lock_vote(code, "left", "red")
    after = manager.sessions[code]["last_activity"]
    assert after > before


async def test_all_votes_locked_triggers_results():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")
    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "red")
    result = await manager.lock_vote(code, "right", "white")
    assert result["all_locked"] is True
    assert manager.sessions[code]["state"] == "showing_results"


# reset_for_next_lift — 1 test:
async def test_reset_for_next_lift_clears_votes():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "white")
    await manager.reset_for_next_lift(code)
    session = manager.sessions[code]
    assert session["judges"]["left"]["current_vote"] is None
    assert session["judges"]["left"]["locked"] is False
    assert session["state"] == "waiting"


# Other create_session users — 6 tests:
async def test_get_expired_sessions_returns_old_sessions():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.sessions[code]["last_activity"] = datetime.now() - timedelta(hours=5)
    expired = manager.get_expired_sessions(hours=4)
    assert code in expired


async def test_delete_session_removes_from_memory():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.delete_session(code)
    assert code not in manager.sessions


async def test_create_session_initializes_settings():
    manager = SessionManager()
    code = await manager.create_session("Test")
    session = manager.sessions[code]
    assert "settings" in session
    assert session["settings"]["show_explanations"] is False
    assert session["settings"]["lift_type"] == "squat"


async def test_update_settings_stores_values():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, True, "bench")
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["show_explanations"] is True
    assert manager.sessions[code]["settings"]["lift_type"] == "bench"


async def test_update_settings_invalid_lift_type_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, False, "snatch")
    assert result["success"] is False
    assert "Invalid lift type" in result["error"]


async def test_create_session_stores_name():
    manager = SessionManager()
    code = await manager.create_session("Platform A")
    assert manager.sessions[code]["name"] == "Platform A"


# Also update test_cleanup_expired (added in Task 1):
async def test_cleanup_expired_removes_stale_keeps_fresh():
    manager = SessionManager()
    old_code = await manager.create_session("Old")
    new_code = await manager.create_session("New")
    manager.sessions[old_code]["last_activity"] = datetime.now() - timedelta(hours=5)
    manager.cleanup_expired(hours=4)
    assert old_code not in manager.sessions
    assert new_code in manager.sessions
```

Tests that do **not** need changes (stay sync):
- `test_generate_session_code_creates_8_char_code`
- `test_generate_session_code_creates_unique_codes`
- `test_join_session_invalid_code_fails`
- `test_lock_vote_invalid_session_fails` (already converted above to async)
- `test_update_settings_invalid_session_fails`

**Step 4: Update `tests/test_main.py` session_code fixture**

The `session_code` fixture calls `session_manager.create_session()`. Make it async:

```python
@pytest.fixture
async def session_code():
    """Create a fresh session and return its code."""
    code = await session_manager.create_session("Test Session")
    yield code
    if code in session_manager.sessions:
        session_manager.delete_session(code)
```

**Step 5: Run the full test suite**

```
pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add src/judgeme/session.py src/judgeme/main.py tests/test_session.py tests/test_main.py
git commit -m "feat: add asyncio.Lock to SessionManager for thread-safe mutations (M3)"
```

---

## Task 4: L2a — Add `count_displays` and `send_to_displays` to ConnectionManager

**Files:**
- Modify: `src/judgeme/connection.py`
- Test: `tests/test_connection.py`

**Background:** With UUID-per-display (role keys like `display_abc123`), we need two new methods: one to count active displays for the cap check, one to fan out messages to all displays. Pattern mirrors the existing `send_to_role` — acquire lock for snapshot, send outside lock.

---

**Step 1: Write the failing tests**

Add to `tests/test_connection.py`:

```python
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
```

**Step 2: Run the tests and verify they fail**

```
pytest tests/test_connection.py::test_count_displays_returns_zero_for_empty_session tests/test_connection.py::test_count_displays_counts_only_display_connections tests/test_connection.py::test_send_to_displays_sends_to_all_displays tests/test_connection.py::test_send_to_displays_no_op_for_empty_session -v
```

Expected: `FAILED` — `AttributeError: 'ConnectionManager' object has no attribute 'count_displays'`

**Step 3: Implement the two methods in `connection.py`**

Add after `send_to_role`:

```python
async def count_displays(self, session_code: str) -> int:
    """Count active display connections in a session."""
    async with self._lock:
        if session_code not in self.active_connections:
            return 0
        return sum(
            1 for role in self.active_connections[session_code]
            if role.startswith("display_")
        )

async def send_to_displays(self, session_code: str, message: Dict[str, Any]):
    """Send a message to all display connections in a session."""
    async with self._lock:
        if session_code not in self.active_connections:
            return
        websockets = [
            ws for role, ws in self.active_connections[session_code].items()
            if role.startswith("display_")
        ]

    for websocket in websockets:
        try:
            await websocket.send_json(message)
        except Exception:
            pass
```

**Step 4: Run tests and verify they pass**

```
pytest tests/test_connection.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add src/judgeme/connection.py tests/test_connection.py
git commit -m "feat: add count_displays and send_to_displays to ConnectionManager (L2)"
```

---

## Task 5: L2b — Display cap: config + main.py join handler + test

**Files:**
- Modify: `src/judgeme/config.py`
- Modify: `src/judgeme/main.py`
- Test: `tests/test_main.py`

**Background:** Each display connection gets a unique role key (`display_<8-hex-chars>`) so multiple displays are tracked correctly in ConnectionManager and all receive broadcasts. The logical role `"display"` is still sent back to the client in `join_success`. Cap defaults to 20, overridable via env var.

---

**Step 1: Add `DISPLAY_CAP` to `config.py`**

```python
class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
```

**Step 2: Write the failing test**

Add to `tests/test_main.py` (add `from judgeme.config import settings` to imports if not already present):

```python
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
```

**Step 3: Run the test and verify it fails**

```
pytest tests/test_main.py::test_display_cap_rejects_when_full -v
```

Expected: `FAILED` — the display joins successfully instead of being rejected.

**Step 4: Update the `join` handler in `main.py`**

Add `import secrets` to the import block:

```python
import asyncio
from contextlib import asynccontextmanager
import json
import copy
import time
import os
import secrets
```

In the `join` handler, after the `result = session_manager.join_session(...)` block, insert the display-specific logic. The updated `join` block (full replacement):

```python
if message_type == "join":
    session_code = message.get("session_code")
    role = message.get("role")

    if not session_code or not role:
        await websocket.send_json({
            "type": "error",
            "message": "Missing required fields"
        })
        continue

    result = session_manager.join_session(session_code, role)

    if not result["success"]:
        await websocket.send_json({
            "type": "join_error",
            "message": result["error"]
        })
        await websocket.close()
        return

    if role == "display":
        if await connection_manager.count_displays(session_code) >= settings.DISPLAY_CAP:
            await websocket.send_json({
                "type": "join_error",
                "message": "Display cap reached"
            })
            await websocket.close()
            return
        role = f"display_{secrets.token_hex(4)}"

    await connection_manager.add_connection(session_code, role, websocket)

    session_state = copy.deepcopy(session_manager.sessions[session_code])
    session_state["last_activity"] = session_state["last_activity"].isoformat()

    await websocket.send_json({
        "type": "join_success",
        "role": "display" if role.startswith("display_") else role,
        "is_head": result["is_head"],
        "session_state": session_state
    })
```

Note: the `role` variable is now the UUID key (`display_abc123`) for the lifetime of this connection. `connection_manager.remove_connection(session_code, role)` in the `WebSocketDisconnect` handler already uses this variable, so display disconnect cleanup is correct automatically.

**Step 5: Replace `send_to_role("display", ...)` with `send_to_displays`**

Find this block in the `vote_lock` handler:

```python
await connection_manager.send_to_role(
    session_code,
    "display",
    {"type": "judge_voted", "position": position}
)
```

Replace with:

```python
await connection_manager.send_to_displays(
    session_code,
    {"type": "judge_voted", "position": position}
)
```

**Step 6: Run the full test suite**

```
pytest -v
```

Expected: all tests pass, including `test_display_cap_rejects_when_full`.

**Step 7: Commit**

```bash
git add src/judgeme/config.py src/judgeme/main.py tests/test_main.py
git commit -m "feat: display cap with UUID-per-display connection keys (L2)"
```

---

## Task 6: L2c — Remove `session["displays"]` from SessionManager

**Files:**
- Modify: `src/judgeme/session.py`
- Modify: `tests/test_session.py`

**Background:** Display tracking is now owned entirely by ConnectionManager. The `displays` list in the session dict is unused dead state. Removing it simplifies the session structure and eliminates the stale-entry accumulation bug (displays were appended but never removed on disconnect).

---

**Step 1: Remove `"displays": []` from `create_session` in `session.py`**

In the `async def create_session` body, remove this line from the session dict:

```python
"displays": [],
```

**Step 2: Simplify `join_session` for the display path**

Current display path:
```python
if role == "display":
    session["displays"].append({"connected": True})
    return {"success": True, "is_head": False}
```

Replace with:
```python
if role == "display":
    return {"success": True, "is_head": False}
```

**Step 3: Update the test that checks `displays`**

In `tests/test_session.py`, replace `test_join_session_as_display_succeeds`:

```python
async def test_join_session_as_display_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert result["is_head"] is False
```

Also update `test_create_session_initializes_structure` to remove the `displays` assertion:

```python
async def test_create_session_initializes_structure():
    manager = SessionManager()
    code = await manager.create_session("Test")
    session = manager.sessions[code]

    assert "judges" in session
    assert "left" in session["judges"]
    assert "center" in session["judges"]
    assert "right" in session["judges"]
    assert session["state"] == "waiting"
    assert session["timer_state"] == "idle"
    assert "last_activity" in session
```

**Step 4: Run the full test suite**

```
pytest -v
```

Expected: all tests pass.

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "refactor: remove session[displays] list, ConnectionManager owns display tracking (L2)"
```

---

## Final verification

```
pytest -v
```

All tests green. Six commits total — one per task. Batch B complete.
