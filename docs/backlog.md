# Iron Verdict Backlog

> Priority order. Top = next up. When an item is done, it leaves this file —
> the durable record is the commit + CHANGELOG entry. Items with non-trivial
> rationale use the rich format (Definition / Solution / Why); trivial items
> can be a short bullet block.

---

## Snapshot save uses synchronous file I/O on the event loop

**Definition.** The 60-second snapshot task in the lifespan handler writes `/data/sessions.json` with a regular `open().write()` call inside an `async def`. The write is synchronous: while the kernel is committing bytes to disk, the calling thread is parked waiting for the I/O-completion interrupt. That thread is the event loop's thread, so during the wait no coroutines run on this worker — incoming WebSocket messages are not processed, outgoing broadcasts are not dispatched, and the heartbeat task cannot fire.

**Solution.** Two changes: (1) skip the write entirely if there are no active sessions — the task fires unconditionally every 60 s regardless of load, so on an idle server this eliminates the I/O call altogether; (2) replace `open().write()` with either `aiofiles.open()` + `await f.write()`, or wrap the sync call in `await asyncio.to_thread(write_sync)`, to offload the blocking I/O to a separate OS thread when a write does occur. Optionally wrap in `asyncio.wait_for(..., timeout=10)` so a stuck disk affects only the snapshot coroutine. Roughly 5–8 lines of `session.py` (or wherever the snapshot lives).

**Why.** The task fires every 60 s unconditionally — confirmed in production logs, where `snapshot_saved` appears every minute even with no active competition session, meaning the event loop is blocked on a write of `{}` indefinitely. Today the write completes in single-digit milliseconds so the stall is invisible, but the idle write is pointless and the async fix is small. At meaningfully higher session counts the stall would become visible to clients: heartbeat-timing artifacts, vote_lock round-trip spikes every 60 s, and risk of the heartbeat task missing its window.

---

## `ALLOWED_ORIGIN` — fail loud on missing env var in non-dev

**Definition.** `ALLOWED_ORIGIN` controls which `Origin` headers the WebSocket handshake accepts. Production is correctly configured via Railway env var (`ALLOWED_ORIGIN=https://iron-verdict.com`), but the in-code default is `"*"` for local dev convenience. A new deployment surface (staging, fork, redeploy with a mistyped variable) that forgets to set the env var would silently accept WebSocket handshakes from any origin, enabling Cross-Site WebSocket Hijacking.

**Solution.** On startup, validate the resolved value: if `ENV != "development"` and `ALLOWED_ORIGIN` is unset or `"*"`, refuse to start (raise + exit) or at minimum log a loud `ERROR`-level warning. Belt-and-braces: also log the resolved `ALLOWED_ORIGIN` value at startup so deployments are easy to verify in Railway logs.

**Why.** Secure-by-default beats secure-by-discipline. The current setup relies on remembering to set the env var on every new deployment surface; failing loud makes the misconfiguration impossible to ship by accident. Cheap (~10 lines) and removes a class of silent-failure deployment bug.

---

## Global concurrent-WebSocket cap in `ConnectionManager`

**Definition.** `ConnectionManager` has no upper bound on total WebSocket connections per worker. The per-session display cap (`DISPLAY_CAP=20`) bounds connections per session, and Cloudflare's per-IP cap bounds connections per client IP, but a malicious actor opening many sessions from many IPs (or a benign traffic spike) could in principle open thousands of connections to a single worker. Each WebSocket carries memory (Python objects, OS socket buffers) and increases the heartbeat task's per-iteration cost.

**Solution.** Add a configurable global cap (e.g. `MAX_WEBSOCKETS=2000`) checked in `ConnectionManager.connect()` before registering a new socket. Reject new connections with WS close code 1013 ("try again later") once the cap is reached. Log a metric or counter for observability when the cap is hit.

**Why.** Belt-and-braces. Cloudflare is the primary defense at the edge, but a process-level cap protects against scenarios where Cloudflare misses something, a future deployment skips Cloudflare, or the attack pattern spreads across enough IPs to slip under per-IP limits. Cheap to implement, free at runtime when under cap.

---

## `join_session` check-then-write race

**Definition.** In `SessionManager.join_session` at [src/iron_verdict/session.py:104–110](../src/iron_verdict/session.py#L104-L110), the existence check for a role slot and the write that claims that slot are not under the same lock acquisition. Two judges hitting the same role within a few microseconds can both pass the "is this role free?" check before either one writes — the second writer would then overwrite the first.

**Solution.** Move the check and write into a single `async with self.lock:` block (no release in between). Standard check-then-act-under-lock pattern, no design change.

**Why.** The window is microseconds wide and the failure mode is recoverable (server returns "Role already taken" to whichever client gets the second response), so this hasn't caused observable problems. But it's a real bug listed in the architecture scale-flags table and trivial to fix. Removing it eliminates an interview talking point and is the right thing to do regardless.

---

## VPortal proxy leaks transport errors as 500s

**Definition.** `/api/vportal/graphql` at [src/iron_verdict/vportal_proxy.py:205](../src/iron_verdict/vportal_proxy.py#L205) wraps the outbound httpx call with no exception handler. The status-code checks below it only fire if a response was actually received. Transport-layer failures — `httpx.RemoteProtocolError`, `httpx.ConnectError`, `httpx.ReadTimeout` — bubble up to FastAPI and surface to the client as `500 Internal Server Error`, implying an Iron Verdict bug when the real cause is upstream. Observed once during the 2026-05-23 live competition: a single poll hit `RemoteProtocolError: Server disconnected without sending a response`; neighbouring polls from the same client succeeded.

**Solution.** Wrap the `_http_client.post(...)` call in `try/except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout)`. On exception, retry once — httpx will discard the dead socket and dial a fresh connection — and if the retry also fails, log a structured warning and raise `HTTPException(502, "VPortal upstream unreachable")` so the status code matches the existing 5xx-from-upstream branch on line 217. Roughly 10 lines.

**Why.** The most likely root cause is a stale-keepalive race: the shared module-level `httpx.AsyncClient` pools connections to `bvdk.vportal-online.de`, and an idle connection silently closed by VPortal or an intermediate NAT/LB gets reused on the next poll before the client notices it's dead. Unavoidable in any pooled HTTP client; the fix is to catch and retry, not to disable pooling. Severity is low (the next poll cycle succeeded and no vote state was affected), but the misleading 500 will recur, and a transparent retry makes it invisible. Worth doing before the next competition so the logs stay readable and a real upstream outage would show as a 502 rather than being lost in the noise.

---

## Self-host Alpine.js (mitigates third-party-CDN dependency)

**Definition.** Alpine.js is loaded from `cdn.jsdelivr.net` at runtime — via a `<link rel="preload">` and a dynamically-injected `<script>` in `init.js`. If jsdelivr is unreachable (CDN outage, regional ISP issue, competition-venue Wi-Fi that blocks third-party domains), Alpine never loads and the app stays black forever — every screen has `x-cloak` that only Alpine knows how to strip.

**Solution.** Download `alpinejs@3.14.1/dist/cdn.min.js`, commit to `src/iron_verdict/static/js/alpine.min.js`, point the dynamic injection in `init.js` at the local path. Drop the SRI integrity hash and `crossOrigin` flag (pointless on same-origin). Keep `<link rel="preload">` pointed at the new local path so the parallel-fetch optimization is preserved. Roughly 5 lines in `init.js` and 1 in `index.html`, plus the committed JS file.

**Why.** Removes a single point of failure outside Iron Verdict's control. Low probability (jsdelivr is reliable) but total impact during a competition — no Alpine = no UI. Worth doing in the pre-competition window specifically; outside that window it's a normal hygiene item. Same logic does *not* apply to qrcodejs (only the QR-join flow degrades; everyone else fine) or Google Fonts (graceful fallback to system fonts; UI fully functional).

---

## Graceful WebSocket drain on shutdown (deferred)

**Definition.** `_handle_shutdown` does not notify connected WebSocket clients before the process exits. On Railway deploys, every connected client sees an abrupt TCP close and reconnects via exponential backoff. The existing `connectionStatus` dot on the client masks the user-facing impact, but all clients reconnect at roughly the same instant — a thundering-herd pattern that hits the new instance simultaneously.

**Solution.** On `SIGTERM`, send each connected WebSocket a `{"type": "server_shutting_down"}` message and close with WS close code 1001 ("going away") rather than abrupt RST. Client-side, treat that message as "expect to reconnect shortly with some random jitter" rather than immediate exponential-backoff retry. Roughly 30 lines server-side and 10 lines client-side.

**Why (and why deferred).** With a single Railway instance and weekly-ish deploys, user impact today is small — judges see a yellow dot for a couple of seconds during deploys. Becomes load-bearing when: (a) CI/CD lands and ships multiple deploys per day, (b) the app scales horizontally and rolling deploys terminate one instance at a time, or (c) ephemeral compute (spot/preemptible instances) is used and must drain on a termination signal. Keep on the backlog as a senior-grade pattern and a clean interview talking point; revisit when (a), (b), or (c) becomes real.

---

## Split `/health` into `/livez` + `/readyz` (deferred)

**Definition.** `GET /health` conflates two distinct concepts: *liveness* (is the process up and not deadlocked?) and *readiness* (can the process accept traffic right now?). Railway consumes a single health endpoint, so this is benign on the current platform.

**Solution.** Add `GET /livez` (always 200 if the event loop is responsive) and `GET /readyz` (returns 503 during startup, during shutdown drain, when the snapshot lock is held longer than a threshold, etc.). Configure the deployment platform to use them separately for its restart vs. routing decisions.

**Why (and why deferred).** Earns nothing on Railway, which uses a single endpoint. Becomes relevant on ECS/Kubernetes/ALB-based deployments where a slow readiness check can trip an over-eager probe and cause an unnecessary restart loop. Defer to the AWS migration phase; consider implementing the split *before* the migration if the code change is cheap, to make the migration smoother.

---

## Turnstile widget on `POST /api/sessions` (optional)

**Definition.** `POST /api/sessions` is rate-limited to 10/hour/IP via slowapi, with Cloudflare Bot Fight Mode also active at the edge. A determined bot operating a botnet of distinct IPs could still create many sessions, consuming server memory and snapshot disk space.

**Solution.** Add Cloudflare Turnstile (cookieless, no-personal-data CAPTCHA) on the session-creation form. Server verifies the Turnstile token in `POST /api/sessions` before creating the session.

**Why.** Belt-and-braces against bot-driven session creation. Lower priority than the items above — Cloudflare's existing protections cover most realistic threat models — but cheap and a nice talking point. Treat as opt-in based on observed abuse, not as a default hardening step.
