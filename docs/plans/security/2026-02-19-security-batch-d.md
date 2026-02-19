# Batch D Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Batch D: security headers middleware (L1), verify session code is absent from display screen (C3), and write Caddy TLS deployment guide (H1).

**Architecture:** Add `SecurityHeadersMiddleware` (Starlette `BaseHTTPMiddleware`) to `main.py`; audit `index.html` display screen and add protective comment; create `docs/deployment.md`. All three tasks touch different files and are independent.

**Tech Stack:** FastAPI/Starlette middleware, Alpine.js (CDN), pytest/httpx.

---

## Task 1: Security Headers Middleware (L1)

**Files:**
- Modify: `src/judgeme/main.py`
- Test: `tests/test_main.py`

### Step 1: Write the failing tests

Append to `tests/test_main.py`:

```python
def test_security_headers_on_root():
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "cdn.jsdelivr.net" in csp


def test_security_headers_on_api():
    response = client.post("/api/sessions", json={"name": "Test"})
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers
```

### Step 2: Run test — expect FAIL

```
pytest tests/test_main.py::test_security_headers_on_root tests/test_main.py::test_security_headers_on_api -v
```

Expected: `FAILED` — `KeyError` on missing headers.

### Step 3: Add middleware to `main.py`

Add import after existing imports (line ~18):

```python
from starlette.middleware.base import BaseHTTPMiddleware
```

Add class definition and CSP constant before `limiter = ...` (around line 32):

```python
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "connect-src 'self' ws: wss:; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

Register the middleware immediately after `app = FastAPI(...)` (around line 51):

```python
app.add_middleware(SecurityHeadersMiddleware)
```

### Step 4: Run tests — expect PASS

```
pytest tests/test_main.py::test_security_headers_on_root tests/test_main.py::test_security_headers_on_api -v
```

Expected: `PASSED`.

### Step 5: Run full test suite

```
pytest tests/ -v
```

Expected: all tests pass. If `test_websocket_*` tests fail due to middleware wrapping, check that `BaseHTTPMiddleware` is not interfering with the WebSocket upgrade path (it shouldn't — WebSocket connections bypass `call_next`).

### Step 6: Commit

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: add security headers middleware (L1)"
```

---

## Task 2: Audit Display Screen for Session Code (C3)

**Files:**
- Modify: `src/judgeme/static/index.html` (comment only)

This is a verification task. The display screen (`x-show="screen === 'display'"`) already uses `x-text="sessionName"` (the human-readable name like "Platform A"), not `x-text="sessionCode"` (the join code like "ABCD1234").

### Step 1: Verify audit

Search `index.html` for `sessionCode`. Confirm it appears **only** in:
- Role-select screen: `<span class="session-code" @click="returnToLanding()" x-text="sessionCode">`
- Judge screen header: `<span class="session-code" @click="returnToRoleSelection()" x-text="sessionCode">`
- **Not** inside `<div class="screen" x-show="screen === 'display'">` block.

### Step 2: Add protective comment

In `index.html`, find the display screen opening div (looks like):

```html
        <!-- Display Screen -->
        <div class="screen" x-show="screen === 'display'">
```

Replace it with:

```html
        <!-- Display Screen: shows sessionName only — sessionCode intentionally omitted (C3) -->
        <div class="screen" x-show="screen === 'display'">
```

### Step 3: Commit

```bash
git add src/judgeme/static/index.html
git commit -m "chore: audit display screen - confirm session code not exposed (C3)"
```

---

## Task 3: Caddy TLS Deployment Guide (H1)

**Files:**
- Create: `docs/deployment.md`

### Step 1: Create `docs/deployment.md`

```markdown
# Deployment Guide

## Production Deployment with TLS

Use [Caddy](https://caddyserver.com/) as a reverse proxy. It provisions and renews Let's Encrypt certificates automatically.

### 1. Install Caddy

Follow the [official installation guide](https://caddyserver.com/docs/install) for your OS.

### 2. Create a Caddyfile

```
yourdomain.com {
    reverse_proxy localhost:8000
}
```

Caddy handles HTTPS automatically. Port 80 and 443 must be open.

### 3. Run JudgeMe

```bash
uvicorn judgeme.main:app --host 127.0.0.1 --port 8000
```

Bind to `127.0.0.1` so the app is only reachable through Caddy, not directly from the internet.

### 4. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_ORIGIN` | `*` | Restrict WebSocket origin. Set to `https://yourdomain.com` in production. |
| `SESSION_TIMEOUT_HOURS` | `24` | Hours before idle sessions are cleaned up. |
| `DISPLAY_CAP` | `20` | Max simultaneous display connections per session. |
| `ENV` | _(unset)_ | Set to `development` to enable Uvicorn auto-reload. |

### Security Notes

- Set `ALLOWED_ORIGIN=https://yourdomain.com` — prevents WebSocket connections from foreign origins.
- Bind Uvicorn to `127.0.0.1`, not `0.0.0.0` — keeps the app behind Caddy.
- The app sends `Strict-Transport-Security` headers; browsers enforce HTTPS after first visit.
- CSP currently allowlists `cdn.jsdelivr.net` for Alpine.js. To tighten: self-host Alpine.js and change `script-src` to `'self'` only.
```

### Step 2: Commit

```bash
git add docs/deployment.md
git commit -m "docs: add Caddy deployment guide with TLS (H1)"
```

---

## Final: Run full suite and verify

```
pytest tests/ -v
```

All tests must pass before opening the PR.
