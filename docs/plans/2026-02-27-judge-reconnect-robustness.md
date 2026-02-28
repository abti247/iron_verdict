# Judge Reconnect Robustness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the stuck-session bug caused by judge disconnection mid-round by adding reconnect tokens, server-side connection replacement, disconnect identity guarding, judge connectivity status broadcasts, and a head judge emergency override.

**Architecture:** Reconnect tokens (16-byte hex) are generated on judge join, stored in session state and client sessionStorage, and presented on reconnection to allow server-side connection replacement rather than rejecting with "Role already taken". A disconnect identity guard prevents stale disconnect handlers from corrupting fresh connection state. Judge connectivity changes are broadcast via a new `judge_status_update` message so the head judge sees live status.

**Tech Stack:** FastAPI/asyncio (backend), Alpine.js/vanilla JS (frontend), pytest-asyncio + httpx-ws (tests)

---

### Task 1: Add `get_connection()` to ConnectionManager

**Files:**
- Modify: `src/iron_verdict/connection.py`
- Test: `tests/test_connection.py`

**Step 1: Write the failing tests**

Add to the bottom of `tests/test_connection.py`:

```python
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_connection.py::test_get_connection_returns_registered_websocket tests/test_connection.py::test_get_connection_returns_none_when_not_found -v
```
Expected: `FAILED` — `AttributeError: 'ConnectionManager' object has no attribute 'get_connection'`

**Step 3: Implement**

Add after `remove_connection` in `src/iron_verdict/connection.py` (after line 28):

```python
async def get_connection(self, session_code: str, role: str):
    """Return the registered WebSocket for a role, or None."""
    async with self._lock:
        return self.active_connections.get(session_code, {}).get(role)
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_connection.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/iron_verdict/connection.py tests/test_connection.py
git commit -m "feat: add get_connection() to ConnectionManager"
```

---

### Task 2: Add `reconnect_token` to Session State

**Files:**
- Modify: `src/iron_verdict/session.py`
- Test: `tests/test_session.py`

**Step 1: Write the failing tests**

Add to the bottom of `tests/test_session.py`:

```python
import json
import tempfile
import os


async def test_join_session_returns_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert "reconnect_token" in result
    assert isinstance(result["reconnect_token"], str)
    assert len(result["reconnect_token"]) == 32  # 16 hex bytes


async def test_reconnect_token_stored_in_judge_state():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    stored = manager.sessions[code]["judges"]["left"]["reconnect_token"]
    assert stored == result["reconnect_token"]


async def test_reconnect_token_survives_reset_for_next_lift():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    token = result["reconnect_token"]
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["judges"]["left"]["reconnect_token"] == token


async def test_snapshot_excludes_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "sessions.json")
        manager.save_snapshot(path)
        with open(path) as f:
            data = json.load(f)
    for judge in data[code]["judges"].values():
        assert "reconnect_token" not in judge


async def test_display_join_returns_no_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert result.get("reconnect_token") is None
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_session.py::test_join_session_returns_reconnect_token tests/test_session.py::test_reconnect_token_stored_in_judge_state tests/test_session.py::test_reconnect_token_survives_reset_for_next_lift tests/test_session.py::test_snapshot_excludes_reconnect_token tests/test_session.py::test_display_join_returns_no_reconnect_token -v
```
Expected: `FAILED`

**Step 3: Implement**

In `src/iron_verdict/session.py`:

**3a.** Add `"reconnect_token": None` to each judge in `create_session` (in all three judge dicts — left, center, right):

```python
"left": {
    "connected": False,
    "is_head": False,
    "current_vote": None,
    "locked": False,
    "current_reason": None,
    "reconnect_token": None,
},
```
(Repeat for `center` and `right`.)

**3b.** In `join_session`, replace the final two lines for judges (the return statement):

```python
# Before:
judge["connected"] = True
is_head = judge["is_head"]
return {"success": True, "is_head": is_head}

# After:
judge["connected"] = True
is_head = judge["is_head"]
token = secrets.token_hex(16)
judge["reconnect_token"] = token
return {"success": True, "is_head": is_head, "reconnect_token": token}
```

`secrets` is already imported at the top of `session.py`.

**3c.** In `save_snapshot`, change the judge serialisation line to strip the token:

```python
# Before:
s["judges"] = {pos: dict(j) for pos, j in session["judges"].items()}

# After:
s["judges"] = {
    pos: {k: v for k, v in j.items() if k != "reconnect_token"}
    for pos, j in session["judges"].items()
}
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_session.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/iron_verdict/session.py tests/test_session.py
git commit -m "feat: add reconnect_token to judge session state"
```

---

### Task 3: Backend — Connection Replacement, Identity Guard, Status Broadcasts

**Files:**
- Modify: `src/iron_verdict/main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing tests**

Add to the bottom of `tests/test_main.py`:

```python
@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
                    "reconnect_token": "000000000000000000000000000000000000",
                })
                msg = await asyncio.wait_for(new_ws.receive_json(), timeout=1.0)
                assert msg["type"] == "join_error"
                assert "already taken" in msg["message"].lower()


@pytest.mark.asyncio
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
                # Drain the judge_status_update that center received when left joined
                try:
                    await asyncio.wait_for(center_ws.receive_json(), timeout=0.3)
                except asyncio.TimeoutError:
                    pass
            # left_ws context exits → triggers disconnect

            await asyncio.sleep(0.1)

            # Center should receive judge_status_update for left disconnecting
            msg = await asyncio.wait_for(center_ws.receive_json(), timeout=1.0)
            assert msg["type"] == "judge_status_update"
            assert msg["position"] == "left"
            assert msg["connected"] is False


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_head_judge_can_next_lift_in_waiting_state(session_code):
    """next_lift must work even when session state is 'waiting' (no resultsShown gate server-side)."""
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_main.py::test_join_success_includes_reconnect_token tests/test_main.py::test_join_success_session_state_excludes_reconnect_tokens tests/test_main.py::test_reconnect_with_valid_token_replaces_stale_connection tests/test_main.py::test_reconnect_with_wrong_token_rejected tests/test_main.py::test_judge_disconnect_broadcasts_status_update tests/test_main.py::test_judge_join_broadcasts_status_update tests/test_main.py::test_head_judge_can_next_lift_in_waiting_state -v
```
Expected: most FAIL

**Step 3: Implement in `src/iron_verdict/main.py`**

**3a. In the `join` handler, after `result = session_manager.join_session(session_code, role)`, replace the existing error block:**

```python
# Before:
if not result["success"]:
    logger.warning("role_join_failed", ...)
    await websocket.send_json({"type": "join_error", "message": result["error"]})
    await websocket.close()
    return

# After:
if not result["success"]:
    if result["error"] == "Role already taken" and role.endswith("_judge"):
        position = role.replace("_judge", "")
        stored_token = message.get("reconnect_token")
        judge = session_manager.sessions.get(session_code, {}).get("judges", {}).get(position, {})
        judge_token = judge.get("reconnect_token")
        if stored_token and judge_token and stored_token == judge_token:
            # Valid reconnect token — close old connection and take the slot
            old_ws = await connection_manager.get_connection(session_code, role)
            if old_ws:
                await connection_manager.remove_connection(session_code, role)
                try:
                    await old_ws.close()
                except Exception:
                    pass
            session_manager.sessions[session_code]["judges"][position]["connected"] = False
            result = session_manager.join_session(session_code, role)
    if not result["success"]:
        logger.warning("role_join_failed", extra={
            "conn_id": conn_id,
            "session_code": session_code,
            "role": message.get("role"),
            "reason": result["error"],
            "client_ip": _get_ws_client_ip(websocket),
        })
        await websocket.send_json({"type": "join_error", "message": result["error"]})
        await websocket.close()
        return
```

**3b. Strip reconnect tokens from session_state before sending to client.** After the existing lines that create `session_state` (around line 268), add:

```python
session_state = copy.deepcopy(session_manager.sessions[session_code])
session_state["last_activity"] = session_state["last_activity"].isoformat()
# Do not expose other judges' reconnect tokens to clients
for judge in session_state["judges"].values():
    judge.pop("reconnect_token", None)
```

**3c. Include reconnect_token in join_success.** Change the `send_json` call:

```python
await websocket.send_json({
    "type": "join_success",
    "role": "display" if role.startswith("display_") else role,
    "is_head": result["is_head"],
    "session_state": session_state,
    "reconnect_token": result.get("reconnect_token"),  # None for display
})
```

**3d. Broadcast `judge_status_update` on successful judge join.** Add after the `send_json` call above (and only for judge roles, not display):

```python
if role.endswith("_judge"):
    position = role.replace("_judge", "")
    await connection_manager.broadcast_to_session(
        session_code,
        {"type": "judge_status_update", "position": position, "connected": True},
    )
```

**3e. Replace the `except WebSocketDisconnect` handler** with the identity-guarded version:

```python
except WebSocketDisconnect:
    if session_code and role:
        current_ws = await connection_manager.get_connection(session_code, role)
        if current_ws is websocket:
            # This is still the active connection — clean up normally
            await connection_manager.remove_connection(session_code, role)
            logger.info("role_disconnected", extra={
                "conn_id": conn_id,
                "session_code": session_code,
                "role": "display" if role.startswith("display_") else role,
            })
            if role.endswith("_judge"):
                position = role.replace("_judge", "")
                if session_code in session_manager.sessions:
                    session_manager.sessions[session_code]["judges"][position]["connected"] = False
                    await connection_manager.broadcast_to_session(
                        session_code,
                        {"type": "judge_status_update", "position": position, "connected": False},
                    )
        else:
            # Connection was replaced by a reconnect — ignore stale disconnect
            logger.info("stale_disconnect_ignored", extra={
                "conn_id": conn_id,
                "session_code": session_code,
                "role": "display" if role.startswith("display_") else role,
            })
```

**Step 4: Run to verify pass**

```bash
pytest tests/test_main.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/iron_verdict/main.py tests/test_main.py
git commit -m "feat: connection replacement, identity guard, judge status broadcasts"
```

---

### Task 4: Frontend JS — Reconnect Token, handleJoinError Fix, judgeConnected State, pageshow

**Files:**
- Modify: `src/iron_verdict/static/js/handlers.js`
- Modify: `src/iron_verdict/static/js/app.js`

No automated tests for these changes — verify manually by opening the browser dev tools and checking that messages flow correctly.

**Step 1: Fix `handleJoinError` in `handlers.js`**

Replace the existing function:

```javascript
// Before:
export function handleJoinError(app, message) {
    app.ws.close();
    sessionStorage.removeItem('iv_session');
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Failed to join session: ${sanitizedMessage}`);
}

// After:
export function handleJoinError(app, message) {
    if (message.message === 'Role already taken') {
        // Transient race condition — server closes socket, auto-reconnect retries
        return;
    }
    app.ws.close();
    sessionStorage.removeItem('iv_session');
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Failed to join session: ${sanitizedMessage}`);
}
```

**Step 2: Update `handleJoinSuccess` in `handlers.js`** to store the reconnect token and initialize judgeConnected state:

```javascript
export function handleJoinSuccess(app, message) {
    app.isHead = message.is_head;
    app.sessionName = message.session_state?.name || '';
    app.screen = app.role === 'display' ? 'display' : 'judge';

    // Initialize live connectivity state from session snapshot
    const judges = message.session_state?.judges;
    if (judges) {
        app.judgeConnected = {
            left: judges.left?.connected ?? false,
            center: judges.center?.connected ?? false,
            right: judges.right?.connected ?? false,
        };
    }

    // Persist reconnect token for future reconnections
    if (message.reconnect_token) {
        const stored = sessionStorage.getItem('iv_session');
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                parsed.reconnect_token = message.reconnect_token;
                sessionStorage.setItem('iv_session', JSON.stringify(parsed));
            } catch (_e) {}
        }
    }

    if (app.isHead) {
        app.requireReasons = message.session_state?.settings?.require_reasons ?? false;
        app.saveSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        app.startTimerCountdown(trms);
    }
}
```

**Step 3: Add `handleJudgeStatusUpdate` to `handlers.js`**

Add after `handleSettingsUpdate`:

```javascript
export function handleJudgeStatusUpdate(app, message) {
    app.judgeConnected[message.position] = message.connected;
}
```

**Step 4: Update `app.js`**

**4a.** Add `judgeConnected` to the app state object (near the other state properties, around line 38):

```javascript
judgeConnected: { left: false, center: false, right: false },
```

**4b.** Add `handleJudgeStatusUpdate` to the import list at the top of `app.js`:

```javascript
import {
    handleJoinSuccess,
    handleJoinError,
    handleError,
    handleShowResults,
    handleResetForNextLift,
    handleTimerStart,
    handleTimerReset,
    handleSessionEnded,
    handleSettingsUpdate,
    handleServerRestarting,
    handleJudgeStatusUpdate,   // ← add this
} from './handlers.js';
```

**4c.** Add `judge_status_update` to the `handleMessage` dispatch map:

```javascript
handleMessage(message) {
    const dispatch = {
        join_success:        handleJoinSuccess,
        join_error:          handleJoinError,
        error:               handleError,
        show_results:        handleShowResults,
        reset_for_next_lift: handleResetForNextLift,
        timer_start:         handleTimerStart,
        timer_reset:         handleTimerReset,
        session_ended:       handleSessionEnded,
        settings_update:     handleSettingsUpdate,
        server_restarting:   handleServerRestarting,
        judge_status_update: handleJudgeStatusUpdate,  // ← add this
    };
    dispatch[message.type]?.(this, message);
},
```

**4d.** In `joinSession`, update the `onReopen` callback to include the reconnect token from sessionStorage:

```javascript
// Before:
() => {
    this.connectionStatus = 'connected';
    this.serverRestarting = false;
    this.wsSend({ type: 'join', session_code: code, role: role });
},

// After:
() => {
    this.connectionStatus = 'connected';
    this.serverRestarting = false;
    let reconnectToken = null;
    const stored = sessionStorage.getItem('iv_session');
    if (stored) {
        try { reconnectToken = JSON.parse(stored).reconnect_token || null; } catch (_e) {}
    }
    const joinMsg = { type: 'join', session_code: code, role: role };
    if (reconnectToken) joinMsg.reconnect_token = reconnectToken;
    this.wsSend(joinMsg);
},
```

**4e.** Add the `pageshow` listener in `init()`, just before the closing `}` of the method:

```javascript
window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    const stored = sessionStorage.getItem('iv_session');
    if (!stored) return;
    try {
        const { code, role } = JSON.parse(stored);
        if (code && role && this.ws && this.ws.readyState === 3) {
            this.joinSession(role);
        }
    } catch (_e) {}
});
```

`readyState === 3` is `WebSocket.CLOSED`. Only call `joinSession` if the socket is definitively dead (not CONNECTING=0, OPEN=1, or CLOSING=2).

**Step 5: Commit**

```bash
git add src/iron_verdict/static/js/handlers.js src/iron_verdict/static/js/app.js
git commit -m "feat: reconnect token in client, handleJoinError fix, judgeConnected state, pageshow recovery"
```

---

### Task 5: UI — Connectivity Status Bar and Unconditional Next Lift

**Files:**
- Modify: `src/iron_verdict/static/index.html`
- Modify: `src/iron_verdict/static/css/components.css`

**Step 1: Add CSS for connectivity indicators to `components.css`**

Add at the end of the `/* ===== HEAD JUDGE CONTROLS =====*/` section (after the `.settings-bar select` block, around line 310):

```css
.judge-connectivity-bar {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.connectivity-dot {
    font-size: 12px;
    letter-spacing: 1px;
    padding: 3px 8px;
    border-radius: 3px;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
}

.connectivity-dot.status-connected {
    color: #4ade80;
    border: 1px solid #4ade80;
}

.connectivity-dot.status-disconnected {
    color: var(--text-dim);
    border: 1px solid var(--chrome-dark);
}
```

**Step 2: Add connectivity bar to `index.html` and fix Next Lift button**

In `index.html`, inside `<div class="head-section" x-show="isHead">`, add the connectivity bar **above** the `<div class="head-grid">` (after `<div class="head-title">Head Judge Controls</div>`):

```html
<!-- Judge connectivity status -->
<div class="judge-connectivity-bar">
    <span class="connectivity-dot" :class="judgeConnected.left ? 'status-connected' : 'status-disconnected'">
        L
    </span>
    <span class="connectivity-dot" :class="judgeConnected.center ? 'status-connected' : 'status-disconnected'">
        C
    </span>
    <span class="connectivity-dot" :class="judgeConnected.right ? 'status-connected' : 'status-disconnected'">
        R
    </span>
</div>
```

Then fix the Next Lift button (around line 287):

```html
<!-- Before: -->
<button class="btn-blood btn-blood-primary cut-corner-sm"
        @click="nextLift()" :disabled="!resultsShown">Next Lift</button>

<!-- After: -->
<button class="btn-blood btn-blood-primary cut-corner-sm"
        @click="resultsShown ? nextLift() : confirm('Results haven\'t been shown yet — advance anyway?') && nextLift()">Next Lift</button>
```

**Step 3: Run the full test suite to confirm nothing regressed**

```bash
pytest -v
```
Expected: all PASS

**Step 4: Commit**

```bash
git add src/iron_verdict/static/index.html src/iron_verdict/static/css/components.css
git commit -m "feat: judge connectivity status bar, unconditional Next Lift for head judge"
```

---

### Task 6: Update CHANGELOG

**File:** `CHANGELOG.md`

Add under `[Unreleased]` → `Added`:
```
- Reconnect token: judges can reclaim their role after disconnect without "Role already taken" error
- Judge connectivity status bar on head judge screen (live L/C/R indicators)
- Head judge Next Lift button is always active with confirmation if results not yet shown
```

Add under `[Unreleased]` → `Fixed`:
```
- Stale disconnect after connection replacement no longer sets judge connected=false
- handleJoinError no longer permanently kills auto-reconnect on transient "Role already taken" errors
- bfcache page restoration now re-establishes WebSocket connection if socket is closed
```

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for judge reconnect robustness"
```
