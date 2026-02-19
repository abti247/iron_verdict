# Security Review — JudgeMe

**Date:** 2026-02-12
**Scope:** Full codebase review for public web hosting

---

## Threat Model

This review focuses on two threat categories the hoster cares about:

1. **Hoster cost / resource abuse** — unlimited session creation, memory exhaustion, DoS
2. **Competition disruption** — hijacking a session, impersonating a judge, blocking the head judge role

---

## Critical Issues

### C1 — No Rate Limiting on Session Creation (`POST /api/sessions`)

**Risk: Hoster cost / resource abuse**

Anyone can POST to `/api/sessions` in a loop and create millions of sessions. Each session is stored in-memory. There is no rate limiting, no CAPTCHA, no token required.

**Effect:** Server RAM exhausted within minutes on a cheap VPS. Could directly cost you money (crashed competition, emergency scaling).

**Fix:** Add rate limiting per IP (e.g. 10 sessions / hour / IP) using a library like `slowapi` for FastAPI.

---

### C2 — No Session Cleanup Mechanism

**Risk: Hoster cost / resource abuse**

Sessions have a `SESSION_TIMEOUT_HOURS` setting (default 4h), but there is **no background task or cron job** that ever removes expired sessions. The `last_activity` timestamp is set but never checked against anything. `delete_session()` only runs when the head judge explicitly ends the session.

**Effect:** Memory grows unboundedly. Confirmed in `session.py` — no periodic cleanup exists.

**Fix:** Add a FastAPI startup background task that sweeps and deletes sessions older than the timeout every 30 minutes.

```python
# Example sketch
@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_expired_sessions())

async def cleanup_expired_sessions():
    while True:
        await asyncio.sleep(1800)  # every 30 min
        session_manager.cleanup_expired()
```

---

### C3 — Anyone Can Join as Any Judge Role

**Risk: Competition disruption**

Sessions are identified only by a 6-character code. Once you know the code, you can `join` as `center_judge`, `left_judge`, or `right_judge` with no further proof of identity. There is no PIN, password, or token per role.

The join logic in `session.py` does check whether a judge slot is "connected", but this means:
- A second person trying to join an occupied role gets an error — **this is correct** (slot protection exists)
- However, the **first** person to join a role wins it — no identity verification at all

**Effect:** If an attacker knows or guesses the session code before the real judge connects, they claim the slot. If the real center judge disconnects briefly (network hiccup), an attacker can steal the center judge slot and block the session.

**Partial mitigation already present:** Judges can only reconnect if the slot is free. But the reconnect is not identity-verified.

**Fix:**
- Add a **role PIN** system: when the head judge creates a session, the app generates a separate PIN for each judge role. Judges must provide both the session code and their PIN to join.
- Or: require the session creator to explicitly "pre-assign" who can join each role before the session starts.

---

### C4 — Session Codes Use Non-Cryptographic Randomness

**Risk: Session guessing / competition disruption**

`session.py` uses `random.choices()` (Python's Mersenne Twister) instead of `secrets.choice()`.

```python
# Current (insecure)
code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Should be
import secrets
code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
```

**Effect:** The PRNG state can theoretically be recovered if an attacker observes enough generated codes. In practice this is a low-probability attack, but it costs nothing to fix.

---

### C5 — `reload=True` in Production (`run.py`)

**Risk: Server compromise**

`uvicorn.run(..., reload=True)` is a development flag that watches for file changes and restarts the server. It should **never** run in production. It adds unnecessary attack surface and instability.

**Fix:** Remove `reload=True` from `run.py`, or gate it on an env variable:

```python
reload = os.getenv("ENV", "production") == "development"
uvicorn.run("judgeme.main:app", host=..., port=..., reload=reload)
```

---

## High Issues

### H1 — No HTTPS/WSS Enforcement

**Risk: Session code interception, competition disruption**

Without HTTPS, session codes, votes, and role assignments are sent in plaintext over the network. Anyone on the same Wi-Fi as a judge (common at competitions in a sports hall) can read and replay WebSocket messages.

**Fix:** Run behind a reverse proxy (Nginx or Caddy) that terminates TLS. Caddy auto-provisions Let's Encrypt certificates with near-zero config.

---

### H2 — Session Code Sent as URL Query Parameter (Demo Mode)

**Risk: Code leakage**

When the head judge opens demo windows for other judges, the session code is appended as a URL parameter (`?code=ABC123&demo=left_judge`). This exposes codes in:
- Browser history
- Server access logs
- HTTP Referer headers if any third-party resource is loaded

**Fix:** After reading the code from the URL, immediately replace the URL in browser history using `history.replaceState()`:

```javascript
// After reading params
history.replaceState({}, '', window.location.pathname);
```

---

### H3 — No Limit on WebSocket Message Rate

**Risk: Competition disruption / DoS**

A client can spam WebSocket messages (e.g. thousands of `vote_lock` or `timer_start` messages per second) with no throttling. FastAPI/uvicorn will process them all, consuming CPU.

**Fix:** Track message counts per connection and disconnect clients that exceed a threshold (e.g. 20 messages/second).

---

### H4 — Vote Color Not Validated Server-Side

**Risk: Data corruption**

In `main.py`, the `color` field from a `vote_lock` message is stored without validation:

```python
color = message.get("color")  # no check
result = session_manager.lock_vote(session_code, position, color)
```

A malicious client could submit `color: "HACKED"` or a very long string.

**Fix:** Validate against an allowlist before storing:

```python
VALID_COLORS = {"white", "red", "blue", "yellow"}
color = message.get("color")
if color not in VALID_COLORS:
    await websocket.send_json({"type": "error", "message": "Invalid vote color"})
    continue
```

---

### H5 — No Logging or Audit Trail

**Risk: Unable to investigate incidents**

There is no server-side logging of who joined sessions, what votes were cast, or when sessions were created/ended. If a competition is disrupted, there is no forensic trail.

**Fix:** Add structured logging to key events:
- Session created / ended
- Role joined / disconnected
- Vote locked
- Timer actions

Use Python's `logging` module with a JSON formatter. Keep logs outside the app directory.

---

## Medium Issues

### M1 — No CORS / Origin Check on WebSocket

WebSocket connections do not enforce an origin check. A malicious webpage on a different domain could open a WebSocket connection to your server if the URL is known.

**Fix:** In the WebSocket handler, validate the `Origin` header against your expected domain:

```python
origin = websocket.headers.get("origin", "")
if not origin.startswith("https://yourdomain.com"):
    await websocket.close(code=1008)
    return
```

---

### M2 — Session State Broadcast Includes Full Vote Data Before Reveal

On `join_success`, the full `session_state` including all votes is sent to every connecting client. If a judge or display connects while votes are locked but not yet shown, they receive all votes before the reveal.

Check whether `session_state` in the join response should redact `current_vote` values until results are officially shown.

---

### M3 — Race Condition in Session Manager (No Locking)

`ConnectionManager` uses `asyncio.Lock()`, but `SessionManager` does not. Concurrent WebSocket messages (e.g. two judges voting at the exact same millisecond) could cause inconsistent state.

**Fix:** Add an `asyncio.Lock()` to `SessionManager` and acquire it in write operations (`lock_vote`, `reset_for_next_lift`, `create_session`).

---

### M4 — Alpine.js Loaded from CDN

```html
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

A CDN compromise would allow arbitrary JavaScript injection into your app. The `@3.x.x` tag is mutable and could point to a different version.

**Fix:** Pin to a specific version (`@3.14.1`) and add a `integrity` / `crossorigin` attribute (Subresource Integrity):

```html
<script
  src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"
  integrity="sha384-<hash>"
  crossorigin="anonymous"
  defer>
</script>
```

Or self-host Alpine.js.

---

## Low Issues

### L1 — No HTTP Security Headers

The FastAPI app does not set security headers. Add via middleware or reverse proxy:

| Header | Recommended Value |
|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' cdn.jsdelivr.net; connect-src 'self' wss://yourdomain.com` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |

---

### L2 — No Connection Limit per Session

There is no cap on how many `display` clients can connect to a session. An attacker could open thousands of WebSocket connections to one session, exhausting file descriptors.

**Fix:** Cap display connections per session (e.g. max 20 displays).

---

## Summary Table

| ID | Severity | Title | Affects |
|----|----------|-------|---------|
| C1 | **Critical** | No rate limiting on session creation | Hoster cost |
| C2 | **Critical** | Sessions never cleaned up from memory | Hoster cost |
| C3 | **Critical** | Anyone can steal a judge role | Competition safety |
| C4 | **Critical** | Weak PRNG for session codes | Session guessing |
| C5 | **Critical** | `reload=True` in production | Server stability |
| H1 | High | No HTTPS/WSS | Data interception |
| H2 | High | Session code in URL | Code leakage |
| H3 | High | No WebSocket message rate limit | DoS |
| H4 | High | Vote color not validated | Data corruption |
| H5 | High | No audit logging | Incident response |
| M1 | Medium | No WebSocket origin check | Unauthorized access |
| M2 | Medium | Full vote data in join response | Premature reveal |
| M3 | Medium | Race condition in SessionManager | Data integrity |
| M4 | Medium | Alpine.js CDN without SRI | Supply chain |
| L1 | Low | No HTTP security headers | Defense in depth |
| L2 | Low | No display connection cap | DoS |

---

## Recommended Fix Order for a Competition Launch

1. **C4** — Switch to `secrets` module (5-min fix, zero risk)
2. **C5** — Remove `reload=True` (2-min fix)
3. **H4** — Validate vote colors server-side (10-min fix)
4. **C2** — Add session cleanup background task (30-min fix)
5. **H1** — Set up HTTPS with Caddy or Nginx (1-2h, one-time infra work)
6. **C1** — Add rate limiting with `slowapi` (1h)
7. **H2** — Clear session code from URL after reading (15-min fix)
8. **C3** — Design and implement role PINs (biggest effort, most important for competition integrity)
9. **H5** — Add structured logging (1h)
10. **M1** — Add WebSocket origin validation (30-min fix)
