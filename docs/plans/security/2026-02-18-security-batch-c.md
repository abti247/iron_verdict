# Batch C: Abuse Prevention Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three abuse-prevention measures: HTTP rate-limiting on session creation (C1), per-connection WebSocket message-rate limiting (H3), and Origin-header validation on WebSocket connections (M1).

**Architecture:** `slowapi` wraps `POST /api/sessions` with a 10 req/hour per-IP limit. The WS handler checks `Origin` before `accept()` using an env-var allowlist (`ALLOWED_ORIGIN`). A fixed-1-second-window counter per connection disconnects clients exceeding 20 msg/s.

**Tech Stack:** FastAPI, `slowapi>=0.1.9` (new dep), Python stdlib `time`

---

### Task 1: Add `slowapi` to deps and install

**Files:**
- Modify: `pyproject.toml`

**Step 1: Edit pyproject.toml**

Change `[project].dependencies` to:
```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "python-dotenv>=1.0.1",
    "slowapi>=0.1.9",
]
```

Change `[project.optional-dependencies].dev` to:
```toml
dev = [
    "pytest>=8.3.4",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "httpx-ws>=0.6.0",
]
```

**Step 2: Install**

```bash
pip install -e ".[dev]"
```

Expected: `Successfully installed slowapi-X.X.X` (plus any missing dev deps).

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add slowapi dep, pin httpx/httpx-ws as dev deps"
```

---

### Task 2: Add autouse fixture to reset rate-limiter between tests

**Files:**
- Modify: `tests/test_main.py`

**Step 1: Add fixture at top of test_main.py (after the existing imports)**

```python
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate-limit counters so tests don't bleed into each other."""
    from judgeme.main import limiter
    limiter._storage.reset()
    yield
```

> Note: `limiter._storage` is a `limits.storage.MemoryStorage` instance; its `reset()` method clears all counters.

**Step 2: Run existing tests to confirm they still pass**

```bash
pytest tests/test_main.py -v
```

Expected: all existing tests PASS (the fixture is a no-op until Task 3 adds the limiter).

> The fixture will raise `ImportError` until Task 3 adds `limiter` to `main.py`. That's fine — leave the fixture code commented out until then, or move it to a separate fixture file.
> **Simplest approach:** add the fixture code but wrap the import in `try/except ImportError: return` for now:

```python
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    try:
        from judgeme.main import limiter
        limiter._storage.reset()
    except (ImportError, AttributeError):
        pass
    yield
```

**Step 3: Commit**

```bash
git add tests/test_main.py
git commit -m "test: add autouse fixture to reset slowapi rate-limit storage"
```

---

### Task 3: Write failing test for C1 (rate limit on POST /api/sessions)

**Files:**
- Modify: `tests/test_main.py`

**Step 1: Add test at bottom of test_main.py**

```python
def test_create_session_rate_limited_after_10_requests():
    """11th request from the same IP within an hour returns 429."""
    for i in range(10):
        r = client.post("/api/sessions", json={"name": f"S{i}"})
        assert r.status_code == 200, f"Request {i+1} should succeed, got {r.status_code}"

    r = client.post("/api/sessions", json={"name": "overflow"})
    assert r.status_code == 429
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py::test_create_session_rate_limited_after_10_requests -v
```

Expected: FAIL — `AssertionError: assert 200 == 429` (slowapi not yet wired up).

---

### Task 4: Implement C1 (wire slowapi into main.py)

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add imports** (add after existing imports at top of file)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
```

> Note: `Request` is already in fastapi, add it to the existing `from fastapi import ...` line.

**Step 2: Create limiter** (add before `session_manager = SessionManager()`)

```python
limiter = Limiter(key_func=get_remote_address)
```

**Step 3: Wire limiter into app** (add the two lines immediately after `app = FastAPI(...)`)

```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Step 4: Decorate and update `create_session`**

Replace:
```python
@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new judging session."""
    code = await session_manager.create_session(request.name)
    return {"session_code": code}
```

With:
```python
@app.post("/api/sessions")
@limiter.limit("10/hour")
async def create_session(request: Request, body: CreateSessionRequest):
    """Create a new judging session."""
    code = await session_manager.create_session(body.name)
    return {"session_code": code}
```

> Renaming `request` → `body` is required because slowapi needs a parameter named `request: Request`.

**Step 5: Run all tests**

```bash
pytest tests/test_main.py -v
```

Expected: all PASS, including `test_create_session_rate_limited_after_10_requests`.

**Step 6: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: rate-limit POST /api/sessions to 10/hour per IP (C1)"
```

---

### Task 5: Add `ALLOWED_ORIGIN` to config

**Files:**
- Modify: `src/judgeme/config.py`

**Step 1: Add setting**

Add one line to the `Settings` class:
```python
ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "*")
```

Final `Settings` class:
```python
class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "*")
```

**Step 2: Commit**

```bash
git add src/judgeme/config.py
git commit -m "feat: add ALLOWED_ORIGIN setting for WebSocket origin validation (M1)"
```

---

### Task 6: Write failing test for M1 (Origin validation)

**Files:**
- Modify: `tests/test_main.py`

**Step 1: Add imports at top if not already present**

```python
import httpx_ws
```

**Step 2: Add two tests at bottom of test_main.py**

```python
@pytest.mark.asyncio
async def test_websocket_rejects_wrong_origin(monkeypatch):
    """WS connection with wrong Origin is closed with code 1008."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://app.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws(
            "ws://test/ws", ac, headers={"origin": "https://evil.com"}
        ) as ws:
            with pytest.raises(Exception):
                await ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_accepts_matching_origin(monkeypatch, session_code):
    """WS connection with correct Origin is accepted normally."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGIN", "https://app.example.com")

    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws(
            "ws://test/ws", ac, headers={"origin": "https://app.example.com"}
        ) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            msg = await ws.receive_json()
            assert msg["type"] == "join_success"
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/test_main.py::test_websocket_rejects_wrong_origin tests/test_main.py::test_websocket_accepts_matching_origin -v
```

Expected: `test_websocket_rejects_wrong_origin` FAILS (no origin check yet, connection succeeds). `test_websocket_accepts_matching_origin` PASSES (coincidentally, as the check doesn't exist).

---

### Task 7: Implement M1 (Origin check in WS handler)

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add origin check at top of `websocket_endpoint`, BEFORE `await websocket.accept()`**

Replace:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
```

With:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    origin = websocket.headers.get("origin", "")
    if settings.ALLOWED_ORIGIN != "*" and origin != settings.ALLOWED_ORIGIN:
        await websocket.close(code=1008)
        return
    await websocket.accept()
```

> Starlette's `websocket.close()` before `accept()` internally calls `accept()` then sends a close frame with the given code. The client receives the close frame and `receive_json()` raises an exception.

**Step 2: Run all tests**

```bash
pytest tests/test_main.py -v
```

Expected: all PASS.

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: validate WebSocket Origin header against ALLOWED_ORIGIN env var (M1)"
```

---

### Task 8: Write failing test for H3 (per-connection message rate limit)

**Files:**
- Modify: `tests/test_main.py`

**Step 1: Add test at bottom of test_main.py**

```python
@pytest.mark.asyncio
async def test_websocket_disconnects_on_message_flood(session_code):
    """Sending >20 messages/second closes connection with code 1008."""
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            # Join (message #1)
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success — server has processed msg #1

            # Send 20 more messages in rapid succession (msgs #2–#21)
            # All within the same 1-second window → triggers the >20 limit
            for _ in range(20):
                await ws.send_json({"type": "ping"})

            # Give server a moment to process and close
            await asyncio.sleep(0.1)

            # Next receive should raise because server closed with 1008
            with pytest.raises(Exception):
                await ws.receive_json()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py::test_websocket_disconnects_on_message_flood -v
```

Expected: FAIL — `receive_json()` succeeds or times out instead of raising.

---

### Task 9: Implement H3 (message rate tracking in WS loop)

**Files:**
- Modify: `src/judgeme/main.py`

**Step 1: Add rate-tracking variables before the `while True:` loop**

Find the block that starts with:
```python
    session_code = None
    role = None

    try:
        while True:
            data = await websocket.receive_text()
```

Replace with:
```python
    session_code = None
    role = None

    msg_count = 0
    window_start = time.monotonic()

    try:
        while True:
            data = await websocket.receive_text()

            now = time.monotonic()
            if now - window_start >= 1.0:
                window_start = now
                msg_count = 1
            else:
                msg_count += 1
            if msg_count > 20:
                await websocket.close(code=1008)
                return
```

> `time` is already imported at line 12 of main.py.

**Step 2: Run all tests**

```bash
pytest tests/test_main.py -v
```

Expected: all PASS.

**Step 3: Commit**

```bash
git add src/judgeme/main.py
git commit -m "feat: disconnect WebSocket clients exceeding 20 messages/second (H3)"
```

---

## Final verification

```bash
pytest tests/ -v
```

Expected: all tests PASS with no warnings about unhandled rate limit state.

---

## Unresolved questions

1. **slowapi `_storage` attribute:** The fixture uses `limiter._storage.reset()`. If `slowapi` changes internal attribute names in a future version, the fixture breaks. Should we pin `slowapi==0.1.9` exactly?

2. **Origin header in tests:** `httpx_ws.aconnect_ws` passes `headers` to the underlying HTTP upgrade request. Confirm `origin` (lowercase) is the correct header name for httpx's transport layer — browsers send `Origin` (capitalized), but HTTP headers are case-insensitive and httpx normalizes them.

3. **H3 window type:** The implementation uses a fixed 1-second window (counter resets when `now - window_start >= 1.0`), not a sliding window. This means a burst of 20 at the end of one window + 20 at the start of the next = 40 messages in ~1 second with no disconnect. Per the spec ("20 messages/second") this is acceptable for a first implementation — confirm or specify sliding window.
