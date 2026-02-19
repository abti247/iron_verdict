# Timer Sync Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two timer bugs — clock skew causing wrong initial value on start, and late-joining clients seeing stale "60" instead of current countdown.

**Architecture:** Replace absolute `server_timestamp` (broken across different-clock devices) with server-computed `time_remaining_ms`. Server tracks `timer_started_at` in session state. On join, server computes and injects current `time_remaining_ms` into `join_success`. Client counts down from received ms using its own local clock.

**Tech Stack:** Python/FastAPI backend (`session.py`, `main.py`), Alpine.js frontend (`static/index.html`), pytest + httpx + httpx_ws for tests.

---

### Task 1: Add `timer_started_at` to session state

**Files:**
- Modify: `src/judgeme/session.py:48-49`
- Modify: `src/judgeme/session.py:129-144` (`reset_for_next_lift`)
- Test: `tests/test_session.py`

**Step 1: Write failing tests**

Add to `tests/test_session.py`:

```python
async def test_create_session_includes_timer_started_at():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["timer_started_at"] is None


async def test_reset_for_next_lift_clears_timer_started_at():
    manager = SessionManager()
    code = await manager.create_session("Test")
    import time
    manager.sessions[code]["timer_started_at"] = time.time()
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["timer_started_at"] is None
```

**Step 2: Run tests to verify they fail**

```
.venv/Scripts/python.exe -m pytest tests/test_session.py::test_create_session_includes_timer_started_at tests/test_session.py::test_reset_for_next_lift_clears_timer_started_at -v
```

Expected: FAIL — `KeyError: 'timer_started_at'`

**Step 3: Implement**

In `session.py`, add `"timer_started_at": None` after `"timer_state": "idle"` (line 49):

```python
"timer_state": "idle",
"timer_started_at": None,
```

In `reset_for_next_lift` (around line 141), add before `return`:

```python
session["timer_started_at"] = None
```

**Step 4: Run tests to verify they pass**

```
.venv/Scripts/python.exe -m pytest tests/test_session.py::test_create_session_includes_timer_started_at tests/test_session.py::test_reset_for_next_lift_clears_timer_started_at -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add timer_started_at to session state"
```

---

### Task 2: Update `timer_start` handler — store timestamp, broadcast `time_remaining_ms`

**Files:**
- Modify: `src/judgeme/main.py:269-288`
- Test: `tests/test_main.py`

**Step 1: Write failing test**

Add to `tests/test_main.py` (after the existing `test_timer_start_logs_info` test):

```python
@pytest.mark.asyncio
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
    assert 59000 <= msg["time_remaining_ms"] <= 60000


@pytest.mark.asyncio
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

    import time
    assert session_manager.sessions[code]["timer_started_at"] is not None
    assert abs(session_manager.sessions[code]["timer_started_at"] - time.time()) < 2
```

**Step 2: Run tests to verify they fail**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_timer_start_broadcasts_time_remaining_ms tests/test_main.py::test_timer_start_stores_timer_started_at -v
```

Expected: FAIL

**Step 3: Implement**

In `main.py`, replace the `timer_start` broadcast block (lines 281-288):

```python
logger.info("timer_start", extra={"session_code": session_code})
session_manager.sessions[session_code]["timer_started_at"] = time.time()
await connection_manager.broadcast_to_session(
    session_code,
    {
        "type": "timer_start",
        "time_remaining_ms": 60000
    }
)
```

**Step 4: Run tests**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_timer_start_broadcasts_time_remaining_ms tests/test_main.py::test_timer_start_stores_timer_started_at -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: broadcast time_remaining_ms on timer_start"
```

---

### Task 3: Update `timer_reset` handler — clear `timer_started_at`

**Files:**
- Modify: `src/judgeme/main.py:290-306`
- Test: `tests/test_main.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
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
```

**Step 2: Run to verify it fails**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_timer_reset_clears_timer_started_at -v
```

Expected: FAIL

**Step 3: Implement**

In `main.py`, add one line before the `timer_reset` broadcast (around line 302):

```python
logger.info("timer_reset", extra={"session_code": session_code})
session_manager.sessions[session_code]["timer_started_at"] = None
await connection_manager.broadcast_to_session(
    session_code,
    {"type": "timer_reset"}
)
```

**Step 4: Run test**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_timer_reset_clears_timer_started_at -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: clear timer_started_at on timer_reset"
```

---

### Task 4: Inject `time_remaining_ms` into `join_success`

**Files:**
- Modify: `src/judgeme/main.py:213-222`
- Test: `tests/test_main.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_join_success_includes_time_remaining_ms_when_timer_not_running():
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


@pytest.mark.asyncio
async def test_join_success_includes_time_remaining_ms_when_timer_running():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/sessions", json={"name": "Test"})
    code = resp.json()["session_code"]

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            # Head judge starts timer
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
```

**Step 2: Run to verify they fail**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_join_success_includes_time_remaining_ms_when_timer_not_running tests/test_main.py::test_join_success_includes_time_remaining_ms_when_timer_running -v
```

Expected: FAIL

**Step 3: Implement**

In `main.py`, replace the `join_success` block (lines 213-222):

```python
# Issue 3: Use deep copy for nested dicts
session_state = copy.deepcopy(session_manager.sessions[session_code])
session_state["last_activity"] = session_state["last_activity"].isoformat()

# Compute time_remaining_ms for late-joining clients
if session_state.get("timer_started_at"):
    elapsed_ms = (time.time() - session_state["timer_started_at"]) * 1000
    session_state["time_remaining_ms"] = max(0, 60000 - elapsed_ms)
else:
    session_state["time_remaining_ms"] = None

await websocket.send_json({
    "type": "join_success",
    "role": "display" if role.startswith("display_") else role,
    "is_head": result["is_head"],
    "session_state": session_state
})
```

**Step 4: Run tests**

```
.venv/Scripts/python.exe -m pytest tests/test_main.py::test_join_success_includes_time_remaining_ms_when_timer_not_running tests/test_main.py::test_join_success_includes_time_remaining_ms_when_timer_running -v
```

Expected: PASS

**Step 5: Run full test suite to check for regressions**

```
.venv/Scripts/python.exe -m pytest tests/ -q --tb=short
```

Expected: all pass

**Step 6: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: inject time_remaining_ms into join_success session_state"
```

---

### Task 5: Update frontend — `startTimerCountdown` and message handlers

**Files:**
- Modify: `src/judgeme/static/index.html:1049-1050` (timer_start handler)
- Modify: `src/judgeme/static/index.html:1004-1010` (join_success handler)
- Modify: `src/judgeme/static/index.html:1104-1120` (`startTimerCountdown`)

No automated test for frontend — verify manually at end.

**Step 1: Update `startTimerCountdown`**

Replace lines 1104-1120:

```javascript
startTimerCountdown(timeRemainingMs) {
    this.stopTimer();
    const startedAt = Date.now();
    const initial = timeRemainingMs;

    this.timerInterval = setInterval(() => {
        const remaining = Math.max(0, initial - (Date.now() - startedAt));
        const seconds = Math.ceil(remaining / 1000);
        this.timerDisplay = seconds;
        this.timerExpired = seconds === 0;

        if (seconds === 0) {
            clearInterval(this.timerInterval);
        }
    }, 100);
},
```

**Step 2: Update `timer_start` handler**

Replace line 1050:

```javascript
} else if (message.type === 'timer_start') {
    this.startTimerCountdown(message.time_remaining_ms);
```

**Step 3: Update `join_success` handler**

In the `join_success` block (lines 1004-1010), add timer resume after the existing lines:

```javascript
if (message.type === 'join_success') {
    this.isHead = message.is_head;
    this.sessionName = message.session_state?.name || '';
    this.screen = this.role === 'display' ? 'display' : 'judge';
    if (this.isHead) {
        this.saveSettings();  // sync localStorage settings to server
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        this.startTimerCountdown(trms);
    }
```

**Step 4: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: use time_remaining_ms for clock-skew-free timer countdown"
```

---

### Task 6: Manual verification

**Step 1: Start the server**

```
.venv/Scripts/python.exe -m uvicorn judgeme.main:app --reload
```

**Step 2: Test bug 1 fix — timer starts at 60**

- Open head judge screen on one device
- Click "Start Timer"
- Verify timer starts counting down from 60 (not 107 or any other value)

**Step 3: Test bug 2 fix — late joiner sees current time**

- Start timer on head judge
- Wait 5 seconds
- Open a judge screen on a second device (or second tab)
- Verify the new client's timer shows ~55 (not 60)

**Step 4: Run full test suite one final time**

```
.venv/Scripts/python.exe -m pytest tests/ -q --tb=short
```

Expected: all pass
