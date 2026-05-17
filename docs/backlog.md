# Iron Verdict Backlog

> Priority order. Top = next up. When an item is done, it leaves this file —
> the durable record is the commit + CHANGELOG entry. Items with non-trivial
> rationale use the rich format (Definition / Solution / Why); trivial items
> can be a short bullet block.

---

## Snapshot save uses synchronous file I/O on the event loop

**Definition.** The 60-second snapshot task in the lifespan handler writes `/data/sessions.json` with a regular `open().write()` call inside an `async def`. The write is synchronous: while the kernel is committing bytes to disk, the calling thread is parked waiting for the I/O-completion interrupt. That thread is the event loop's thread, so during the wait no coroutines run on this worker — incoming WebSocket messages are not processed, outgoing broadcasts are not dispatched, and the heartbeat task cannot fire.

**Solution.** Replace `open().write()` with either `aiofiles.open()` + `await f.write()`, or wrap the sync call in `await asyncio.to_thread(write_sync)`. Both offload the blocking I/O to a separate OS thread from the standard thread pool, leaving the event loop's thread free to keep serving coroutines. Optionally wrap the call in `asyncio.wait_for(..., timeout=10)` so a stuck disk affects only the snapshot coroutine rather than blocking the snapshot save forever. Roughly 5 lines of `session.py` (or wherever the snapshot lives).

**Why.** Today the snapshot is small (kilobytes) and the write completes in single-digit milliseconds, so the stall is invisible. At meaningfully higher session counts the stall becomes visible to clients: heartbeat-timing artifacts, vote_lock round-trip spikes every 60 s, and risk of the heartbeat task missing its window. The fix is small and converts a documented future bottleneck into "already handled."

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
