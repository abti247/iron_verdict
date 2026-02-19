# Security Batch A Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply 5 low-risk security fixes: secure PRNG, production reload flag, vote color validation, URL cleanup, and Alpine.js SRI pinning.

**Architecture:** All changes are isolated and self-contained. No new dependencies. Three Python files, one HTML file.

**Tech Stack:** Python `secrets` module (stdlib), FastAPI, Alpine.js 3.14.1

**Worktree:** `.worktrees/security-batch-a` (branch `feature/security-batch-a`)

**Run tests with:** `pytest tests/ -q` from the worktree root

---

### Task 1: C4 — Secure PRNG + 8-char session codes

**Files:**
- Modify: `src/judgeme/session.py:1,16`
- Modify: `tests/test_session.py:8,23`
- Modify: `tests/test_main.py:27`

**Step 1: Update the 3 existing length tests to expect 8 chars (they will fail)**

In `tests/test_session.py`, change line 8:
```python
assert len(code) == 8
```

In `tests/test_session.py`, change line 23:
```python
assert len(code) == 8
```

In `tests/test_main.py`, change line 27:
```python
assert len(data["session_code"]) == 8
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_session.py::test_generate_session_code_creates_6_char_code tests/test_session.py::test_create_session_returns_code tests/test_main.py::test_create_session_returns_code -v
```

Expected: 3 FAILED (AssertionError: assert 6 == 8)

**Step 3: Implement in `src/judgeme/session.py`**

Replace line 1:
```python
import secrets
```
(Remove `import random`)

Replace the `generate_session_code` body (lines 15-16):
```python
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
```

Also update the docstring on line 14 from "6-character" to "8-character".

**Step 4: Run tests to verify they pass**

```
pytest tests/test_session.py tests/test_main.py -q
```

Expected: all pass

**Step 5: Commit**

```
git add src/judgeme/session.py tests/test_session.py tests/test_main.py
git commit -m "fix: use secrets module and 8-char session codes (C4)"
```

---

### Task 2: C5 — Gate reload flag on env var

**Files:**
- Modify: `run.py:14`

No unit test — this is a one-line config guard that's impractical to unit test.

**Step 1: Replace `reload=True` in `run.py`**

Change lines 9-15 to:
```python
if __name__ == "__main__":
    reload = os.getenv("ENV") == "development"
    uvicorn.run(
        "judgeme.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=reload
    )
```

Add `import os` at the top of the file (after the existing imports).

**Step 2: Verify app still starts (manual)**

```
python run.py
```

Expected: starts without reload (no "Watching for file changes" message)

```
ENV=development python run.py
```

Expected: starts with reload

**Step 3: Commit**

```
git add run.py
git commit -m "fix: gate reload=True on ENV=development (C5)"
```

---

### Task 3: H4 — Validate vote color server-side

**Files:**
- Modify: `src/judgeme/main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

Add to the end of `tests/test_main.py`:

```python
@pytest.mark.asyncio
async def test_vote_lock_invalid_color_returns_error(session_code):
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    ) as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await ws.send_json({"type": "join", "session_code": session_code, "role": "left_judge"})
            await ws.receive_json()  # join_success

            await ws.send_json({"type": "vote_lock", "color": "HACKED"})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
            assert msg["type"] == "error"
            assert "color" in msg["message"].lower()
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_main.py::test_vote_lock_invalid_color_returns_error -v
```

Expected: FAILED (timeout — no error message is currently sent back)

**Step 3: Implement in `src/judgeme/main.py`**

Add a constant near the top (after imports):
```python
VALID_COLORS = {"white", "red", "blue", "yellow"}
```

In the `vote_lock` handler (around line 111), add validation before `lock_vote`:
```python
            elif message_type == "vote_lock":
                if not session_code or not role:
                    continue

                position = role.replace("_judge", "")
                color = message.get("color")

                if color not in VALID_COLORS:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid vote color"
                    })
                    continue

                result = session_manager.lock_vote(session_code, position, color)
                # ... rest unchanged
```

**Step 4: Run all tests**

```
pytest tests/ -q
```

Expected: all pass

**Step 5: Commit**

```
git add src/judgeme/main.py tests/test_main.py
git commit -m "fix: validate vote color against allowlist server-side (H4)"
```

---

### Task 4: H2 — Clear session code from URL after reading

> **Status: DROPPED** — see post-implementation note below.

**Original plan:** call `history.replaceState` after reading `?code=&demo=` params to remove them from the popup address bar.

#### Post-implementation investigation

Three approaches were attempted and all failed in Chrome and Edge popup windows:

1. **`history.replaceState` in Alpine's deferred `init()`** — Chrome silently ignores History API calls from deferred scripts in popup windows.
2. **Synchronous inline `<script>` before Alpine** — Chrome also ignores `history.replaceState` in popup windows even from synchronous scripts. The URL remains unchanged in the address bar.
3. **`window.name` (JSON) + clean URL** — `window.open(url, jsonName, features)` appeared to sanitise names containing JSON metacharacters (`{`, `"`, `:`); `window.name` was not set in the popup, so the params were never passed.
4. **`localStorage` + `window.name` (role string) + clean URL** — Despite correct implementation, the URL still appeared in popups in both Chrome and Edge.

#### Why it was dropped

The root concern for H2 was leaking real competition session codes. On closer examination:

- `?code=&demo=` params **only appear in demo mode** — real sessions are joined by manually typing a code, never via URL.
- Demo sessions are ephemeral, carry no real competition data, and are typically opened on the same machine.
- The session code in a demo popup URL gives an attacker access to a demo session only — no meaningful security impact.

The complexity and fragility of working around Chrome/Edge popup address-bar restrictions outweighs the negligible risk. The fix was reverted and the simpler `?code=&demo=` URL approach was kept for demo popups.

#### What was shipped instead (bonus fixes found during investigation)

- **Double `init()` call removed:** `x-init="init()"` was redundant (Alpine auto-calls `init()` from `x-data`), causing a second WebSocket open and a "Still in CONNECTING state" console error.
- **`Cache-Control: no-cache` on HTML endpoint:** FastAPI was serving `index.html` without cache headers, causing Chrome to heuristically cache it and serve stale JavaScript.

---

### Task 5: M4 — Pin Alpine.js version with SRI hash

**Files:**
- Modify: `src/judgeme/static/index.html:7`

**Step 1: Compute the SRI hash for Alpine.js 3.14.1**

Run in Git Bash or WSL:
```bash
curl -s https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```

Copy the resulting base64 string — you'll use it as `sha384-<hash>`.

**Step 2: Update the script tag in `index.html` line 7**

Replace:
```html
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

With:
```html
<script
    defer
    src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"
    integrity="sha384-<hash-from-step-1>"
    crossorigin="anonymous">
</script>
```

**Step 3: Manual verification**

Open the app in a browser. Open DevTools → Network tab. Confirm Alpine.js loads without SRI errors. Confirm the app works normally (buttons respond, screens transition).

**Step 4: Commit**

```
git add src/judgeme/static/index.html
git commit -m "fix: pin Alpine.js to 3.14.1 with SRI hash (M4)"
```
