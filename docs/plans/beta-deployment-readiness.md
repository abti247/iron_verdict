# Iron Verdict — Beta Deployment Readiness

## Answers to Your Questions

### 1. Multiple sessions in single container?

**Yes.** FastAPI + uvicorn async handles concurrent WebSocket connections fine. All state in-memory with `asyncio.Lock`. Realistic capacity: ~10-50 concurrent sessions on a small Railway instance. The real risk is data loss on restart (see section below).

### 2. Logging sufficient?

**Good foundation, gaps for production.** Has structured JSON logs with context (session_code, client_ip, role). Missing: health check endpoint, global exception handler, stack trace capture, configurable log level.

### 3. Security?

**Solid for use case.** Must-fix: set `ALLOWED_ORIGIN` env var to `https://iron-verdict.com` (defaults to `*`). Already good: security headers, rate limiting, input validation, non-root Docker, crypto-secure session codes. Web3Forms key in HTML is fine (public by design, confirmed). Low risk: no auth beyond session codes, no CSRF (acceptable).

### 4. Name risk?

**Very low.** Generic compound name, you own the domain, non-profit. Quick search on USPTO TESS + EU EUIPO to confirm. No need to register trademark unless scaling.

### 5. Other risks

| Risk | Severity | Detail |
|------|----------|--------|
| **Data loss on restart** | HIGH | Deploy/crash wipes all active sessions |
| **No graceful shutdown** | MEDIUM | WebSocket connections killed without warning on deploy |
| **Single worker** | LOW | Unlikely to matter for this workload |

---

## Data Loss on Restart — Strategy

**Goal:** Survive container restarts (deploys, crashes) during active competitions.

**Approach: Railway Volume + JSON snapshot**

Railway supports persistent volumes ($0.25/GB/month, practically free). Mount a volume, serialize session state to a JSON file on shutdown and periodically, reload on startup.

### How it works

1. Add `SNAPSHOT_PATH` env var (default: `/data/sessions.json`)
2. `SessionManager` gets `save_snapshot()` / `load_snapshot()` methods
   - `save_snapshot()`: serialize `self.sessions` dict to JSON (datetime -> ISO string)
   - `load_snapshot()`: read JSON, reconstruct sessions dict, update `last_activity`
3. **On SIGTERM** (Railway sends this before killing container): save snapshot + broadcast "server restarting" to all clients
4. **On startup**: if snapshot file exists, load it. Clients auto-reconnect via existing JS logic in app.js
5. **Periodic backup**: save snapshot every 60s alongside existing cleanup loop (protects against hard crashes where SIGTERM doesn't fire)

### Files to modify

- [session.py](src/iron_verdict/session.py) — add `save_snapshot()`, `load_snapshot()` (~30 lines)
- [config.py](src/iron_verdict/config.py) — add `SNAPSHOT_PATH` setting
- [main.py](src/iron_verdict/main.py) — hook into lifespan: load on startup, save on shutdown, periodic save task
- [Dockerfile](Dockerfile) — create `/data` dir, set permissions for appuser

### Railway config

- Add volume mount: `/data`
- Set env var: `SNAPSHOT_PATH=/data/sessions.json`

### Limitations (acceptable)

- Hard crash (OOM kill, no SIGTERM) loses up to 60s of state
- WebSocket connections themselves aren't persisted — clients must reconnect (already handled by existing reconnect logic)
- Session codes stay the same after restart, so judges rejoin same session

---

## All Changes (prioritized)

### P0 — Must have for beta

1. **Health check endpoint** — `GET /health` -> 200
   File: [main.py](src/iron_verdict/main.py) — 3 lines

2. **Global exception handler** — catch unhandled HTTP errors, log with traceback
   File: [main.py](src/iron_verdict/main.py) — ~10 lines

3. **Configurable log level** — `LOG_LEVEL` env var
   Files: [config.py](src/iron_verdict/config.py), [logging_config.py](src/iron_verdict/logging_config.py)

4. **Set `ALLOWED_ORIGIN`** in Railway env vars to `https://iron-verdict.com`
   Deployment config only, no code change

5. **Session persistence (snapshot)** — survive restarts
   Files: [session.py](src/iron_verdict/session.py), [config.py](src/iron_verdict/config.py), [main.py](src/iron_verdict/main.py), [Dockerfile](Dockerfile)

6. **Graceful shutdown** — save snapshot + broadcast "server restarting" on SIGTERM
   File: [main.py](src/iron_verdict/main.py) — in lifespan shutdown

### P1 — Should have

7. **`logger.exception()` calls** — capture stack traces where exceptions are caught
   Files: [main.py](src/iron_verdict/main.py), [connection.py](src/iron_verdict/connection.py)

8. **Remove `'unsafe-eval'` from CSP** — test if Alpine.js works without it
   File: [main.py](src/iron_verdict/main.py)

### P2 — Nice to have

9. **Request ID middleware** — UUID per request/WS connection in all log lines
   File: [main.py](src/iron_verdict/main.py)

---

## Verification

- `pytest tests/` — existing tests pass
- Start locally, create session, kill process, restart -> session still exists
- Verify `/health` returns 200
- Verify structured logs include stack traces on forced errors
- Test CSP change doesn't break Alpine.js
- Deploy to Railway with volume, verify persistence across redeploys
