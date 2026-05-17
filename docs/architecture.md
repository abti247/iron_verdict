# Architecture

Iron Verdict is a single-process FastAPI + Uvicorn application serving real-time powerlifting competition judging. The runtime is one Python process, one event loop. There is no horizontal scaling today — all state lives in memory.

## Runtime shape

- One Uvicorn worker. `run.py` does not pass `workers=`.
- Async I/O concurrency on a single CPU. Suitable for hundreds to low thousands of concurrent sessions, bounded by memory and message rate, not CPU.
- All state managers and broadcast lists are local to the process.

*Why single-worker:* all session state and the WebSocket registry live in process memory. A second worker would have a disjoint view of sessions and connections, so broadcasts and reconnects would silently fail across workers. Horizontal scaling requires moving state to Redis first (see [Known scale flags](#known-scale-flags)).

## HTTP surface

Served by FastAPI directly:

- `GET /` — landing page (static HTML + Alpine.js).
- `GET /health` — single endpoint used by Railway. Currently conflates liveness + readiness.  
*Why one endpoint:* Railway consumes a single health URL; splitting earned nothing on this platform. Cost: on ECS/K8s, a slow snapshot save could trip a "not ready" signal and cause an unnecessary restart loop — those platforms want `/livez` (is the process up?) separated from `/readyz` (can it serve traffic?).
- `POST /api/sessions` — create a session. Rate-limited to 10/hour/IP via slowapi.
- `GET /api/sessions/{code}` — check whether a session is active. Returns `{"exists": true}` on 200 or 404 with `{"detail": "Session not found"}`. Path pattern `^[A-Z0-9]{8}$` rejects malformed codes with 422 before touching the session map. Rate-limited to 30/minute/IP via slowapi.  
*Why a separate endpoint instead of validating at WebSocket join:* fail-fast UX. Without it, a typo gets the user as far as the role-selection screen before failing — at a live competition that's a real cost. *Why no session name in the response:* minimizes information disclosure; the existence boolean is all the landing screen needs.
- `GET /static/*` — static assets (CSS, JS, fonts) served by FastAPI. In an AWS deployment these would move to CloudFront → S3.

Security:

- Standard hardening headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, HSTS.
- CSP allows `cdn.jsdelivr.net` (Alpine.js), `'unsafe-inline'` and `'unsafe-eval'` — Alpine compiles `x-show`/`x-bind` expressions at runtime via `eval`; the framework will not function without it. XSS posture is recovered structurally: the app never renders user input as HTML. The only user-controllable string written to the DOM is the session name, which is set via `x-text` (text node, not HTML).
- WebSocket origin check via `ALLOWED_ORIGIN`. In-code default is `"*"` for local dev; **production overrides this via the Railway env var `ALLOWED_ORIGIN=https://iron-verdict.com`**, so the live deployment rejects cross-origin WebSocket handshakes.  
*Why the origin check matters:* Same-Origin Policy does not apply to WebSockets — without a server-side `Origin` check, any site could open a WS to `/ws` from a victim's browser and hijack the session (Cross-Site WebSocket Hijacking).  
*Why the permissive default:* local dev convenience.  
*Caveat (tracked in the operational backlog):* secure-by-discipline rather than secure-by-default — a new deployment surface that forgets to set the env var would silently accept any origin. Failing loud at startup in non-dev environments without an explicit value would close that gap.

## WebSocket surface

`GET /ws` is the single WebSocket endpoint. Message types after `join`:

- `vote_lock` — judge locks a colour (and optional reason).
- `settings_update` — head judge changes lift type, show-explanations, require-reasons.
- `timer_start`, `timer_reset` — head judge controls the 60-second attempt timer.
- `next_lift` — head judge resets state for the next attempt.
- `end_session_confirmed` — head judge ends the session.
- `pong` — client reply to server-initiated heartbeat ping.

Per-connection rate limit: 20 messages/second via a sliding window. Exceeding it closes the connection with code 1008. Per-IP concurrent-connection cap is delegated to the edge (Cloudflare).

*Why split the limits this way:* per-connection caps are cheap and local — they protect the message-handling path from a single buggy or malicious client. Per-IP concurrency caps need cross-connection awareness that the edge already has, plus Cloudflare can tie them to broader signals (bot scoring, ASN reputation) that the app process cannot.

## State management

Two in-process managers, each guarded by its own `asyncio.Lock`. The two locks are never held together.

*Why two locks instead of one:* the managers have orthogonal concerns — domain state vs. transport — and conflating them would either serialize all WebSocket I/O behind every domain mutation, or vice versa. *Why never held together:* taking two locks in any order opens a deadlock window if some future path ever inverts the order. The rule "never both" makes deadlock structurally impossible. Accepted cost: any operation that conceptually needs both must split into two phases (compute under one lock, then act under the other) — no such operation has been needed so far.

### `SessionManager`

- Holds `self.sessions: dict[str, dict]` — domain state per session code.
- Each session records: `judges` (left/center/right with vote, reason, locked, connected, reconnect token), `phase`, `state`, `settings`, `timer_started_at`, `timer_frozen_ms`, `last_activity`, `name`.
- Generates 8-character alphanumeric session codes.
- Owns business rules: vote-lock state machine, all-judges-locked → results computation (including the IPF rule that a disconnected non-voter blocks results), timer freeze on results, reset for next lift.

### `ConnectionManager`

- Holds `self.active_connections: dict[session_code, dict[role, WebSocket]]` — transport registry only.
- Tracks `_last_pong: dict[WebSocket, float]` for the heartbeat task.
- Provides `broadcast_to_session`, `broadcast_to_others`, `send_to_role`, `send_to_displays`. Per-socket errors are swallowed and emit warning logs by name.

*Why swallow per-socket errors:* one dead or slow client must not abort the broadcast to the others. The alternative — propagating the first send failure — would let a single misbehaving client (or a TCP RST on one judge's connection) stall state propagation to the remaining judges and the display.

## Persistence

`/data/sessions.json` is a periodic JSON snapshot used **only** for crash recovery, not for state sharing between processes. Saved every 60 seconds by the lifespan task. On Railway it is volume-backed; on ECS/Fargate it would need EFS.

*Why a JSON file and not a database:* the only requirement is "survive a Railway restart with active sessions intact." A flat file gives that with zero operational overhead — no migrations, no connection pool, no schema. Accepted cost: up to 60 s of mutations lost on crash, no point-in-time recovery, no querying. *Why not skip persistence entirely:* a deploy or OOM mid-event would wipe judges' in-flight votes; the 60 s snapshot bounds the blast radius.

Snapshots exclude reconnect tokens — those exist only in memory and die with the process. Reconnects after a restart are not supported.

*Why exclude tokens from the snapshot:* tokens are session-scoped secrets. Persisting them widens the blast radius if `/data/sessions.json` ever leaks (volume mount misconfiguration, debug dump, leaked backup). The trade-off is intentional — after a restart, judges rejoin via the session URL and pick a free role; the friction is acceptable for a 60-second-recovery-window failure mode.

## Reconnection model

- **Judges** receive a 32-character `reconnect_token` on first join. A new WebSocket presenting the matching `(session_code, role, token)` triple replaces the existing connection. An identity guard prevents the disconnect handler of the old socket from clobbering the new one. Tokens survive `reset_for_next_lift`.
- **Displays** have no reconnect token. Each display join takes the next free display slot (`display_aabb1122` random suffix). Displays are interchangeable viewers, capped per session by `DISPLAY_CAP` (default 20).
- Judge slots cap at 3 (left, center, right) and are exclusive.

*Why tokens for judges but not displays:* judges have identity that must persist across reconnects — their vote, lock state, and reason are tied to a specific role. Displays are read-only viewers whose only state is "what's currently on screen", recoverable from the next broadcast. Adding tokens for displays would buy nothing and complicate slot bookkeeping for an unbounded viewer count.

*Why the identity guard:* when a judge reconnects, the new socket replaces the old one in the registry. Without the guard, the *old* socket's disconnect handler (which fires as the underlying TCP tears down) would clear the slot — disconnecting the live new socket and dropping the judge.

*Why a display cap:* every state change fans out to all displays in a session. Without a cap, a single session could become a broadcast amplifier — a malicious actor opens hundreds of display tabs, every `vote_lock` multiplies into hundreds of WebSocket sends, and CPU/bandwidth on the single worker spikes.

## Background work

Single `lifespan` task runs two periodic operations:

- **Snapshot save** — every 60 seconds. Synchronous file I/O inside the async loop; event-loop stall risk at scale.  
*Why sync is acceptable today:* the snapshot is small (kilobytes — a handful of active sessions) and the write completes in single-digit milliseconds. At higher session counts the blocking write would start visibly stalling the event loop; fix is `aiofiles` or a thread-pool executor.
- **Cleanup expired sessions** — every 30 minutes; deletes sessions with `last_activity` older than 4 hours.

A server-initiated heartbeat pings WebSocket clients at a fixed interval and disconnects clients that don't reply within the timeout.

## Edge

- Cloudflare proxy (orange cloud) sits in front of Railway. SSL/TLS Full (strict), Bot Fight Mode on.
- Domain: `iron-verdict.com` → CNAME → Railway.

## Known scale flags

These block multi-instance deployment. Listed for the Phase 6 AWS migration, not as immediate fixes.

| Flag | Impact |
|---|---|
| In-memory `SessionManager.sessions` | No horizontal scaling. Fix path: Redis (state + pub/sub). |
| In-memory `ConnectionManager` | Broadcasts don't cross instances. Fix path: Redis pub/sub. |
| `/data/sessions.json` | Needs EFS or persistent volume on ECS. |
| Sync file I/O in async loop | Event-loop stall at high session counts. |
| `ALLOWED_ORIGIN="*"` in-code default | No CSRF risk on the *current* production deploy (Railway env var overrides to `https://iron-verdict.com`), but secure-by-discipline rather than secure-by-default — a new deployment surface that forgets to set the env var would silently accept any origin. Fix: fail loud at startup in non-dev mode if the value is unset or `"*"`. |
| `/health` conflates liveness + readiness | ECS/Kubernetes prefer separate `/livez` + `/readyz`. |
| `_handle_shutdown` does not drain WebSockets | Clients flap on rolling deploys. |
| No Prometheus metrics surface | Phase 3 work on the roadmap. |
| `join_session` race at `session.py:104–110` | Check-then-write outside the lock. Low priority. |

## Frontend

No-build single-page application. One HTML file served by FastAPI's `StaticFiles`; JS loaded as native ES modules via `<script type="module">`. No bundler, no transpilation, no node_modules.

*Why no build step:* the app is small enough that a bundler earns nothing — no tree-shaking pay-off, no code-splitting need, no TypeScript surface to compile. The dev loop is "edit file → refresh"; CI does not need a frontend build stage; the Docker image carries no `node_modules`. Accepted cost: no minification (file sizes are already small, Cloudflare brotli-compresses on the wire), no TS, and any future move to a framework with required tooling (React, Svelte) would need to introduce the toolchain. The Vitest test runner *does* pull in `node_modules`, but only as a devDependency — it never ships to production.

**CDN dependencies (integrity-checked):**

- Alpine.js 3.14.1 — reactive bindings and component model.
- QRCode.js — QR code on the role-select screen.
- Umami Analytics — cookieless, no personal data.

**JS modules:**

| File | Purpose |
|---|---|
| `init.js` | Entry point: reads demo URL params before Alpine boots, loads i18n, bootstraps Alpine, handles popstate. |
| `app.js` | The single Alpine component (`ironVerdictApp`) — all reactive state and methods. |
| `websocket.js` | WebSocket wrapper with exponential-backoff auto-reconnect. |
| `handlers.js` | One named handler per incoming WS message type; imported by `app.js`. |
| `timer.js` | Module-level countdown interval (`startTimerCountdown`, `stopTimer`). |
| `constants.js` | `CARD_REASONS[liftType][color]` — arrays of i18n reason keys. |
| `i18n.js` | Locale loading, `t()` lookup, `setLanguage()`, Alpine store integration. |
| `demo.js` | Demo methods spread into the Alpine component. |

**CSS files:** `variables.css` (16 custom properties) → `base.css` (resets, typography) → `components.css` (buttons, inputs, orbs) → `layout.css` (per-screen wrappers) → `animations.css` (keyframes).

### Screen machine

The `screen` string drives visibility via Alpine `x-show`. No URL changes on transition:

```
landing → role-select → judge
                     → display
demo-intro → (opens 4 pop-up windows)
contact / privacy  (info-only screens)
```

QR entry point: `?session=XXXX` lands on the landing screen with the code pre-filled, immediately triggers the lookup validator, and navigates to role-select only if the code resolves to an active session. Invalid or unknown codes surface an inline error on landing. `history.replaceState` cleans the URL on entry regardless of outcome.

### WebSocket client

`websocket.js` wraps the native `WebSocket` with:

- Exponential-backoff reconnect: 1 s → 2 s → … → 16 s max; resets to 1 s on successful open.
- `stopped` flag prevents reconnect after intentional close (e.g. "Back to Landing").
- On reconnect, sends `join` with `reconnect_token` from `sessionStorage` if one is stored.
- Server returns a new `reconnect_token` in `join_success`; stored in `sessionStorage.iv_session`.
- `join_error: "Role already taken"` is suppressed when a token is stored — transient race during reconnect; the server will accept the retry with the token.
- `pageshow` listener with `event.persisted` handles bfcache restore: if `readyState === 3` (CLOSED), rejoins automatically.

### Client-side state

| Storage | Key | Content | Lifetime |
|---|---|---|---|
| `sessionStorage` | `iv_session` | `{code, role, reconnect_token?}` | Tab close |
| `localStorage` | `iron-verdict-lang` | `'en'` or `'de'` | Persistent |
| Alpine reactive state | — | `screen`, `selectedVote`, `voteLocked`, timer, etc. | Page lifetime |

*Why `sessionStorage` (not `localStorage`) for the reconnect token:* tab-scoped lifetime matches the lifetime of a judging session. If the token survived in `localStorage`, an old token could leak into a *new* session opened in the same browser later, leading to confusing "Role already taken" failures (server rejects because the role belongs to a stale judge identity). `localStorage` is reserved for genuinely persistent preferences like language.

### i18n

Both locale files (`en.json`, `de.json`) are fetched in parallel at startup. `t(key)` resolves dotted key paths (e.g. `"reasons.squat.red.depth"`), falling back to English if a key is missing. Reactivity is driven by a dummy `_v` counter in an Alpine store: `setLanguage()` increments it, forcing every `t()` call in the template to re-evaluate. Language resolution order: `localStorage` → `navigator.language` prefix → `'en'`.

*Why the dummy `_v` counter:* Alpine's reactivity is property-access-based — a template re-evaluates only when the reactive properties it reads inside the expression change. `t()` resolves the key against a module-level `locales` object, so by default no Alpine-tracked property is read and changing the language wouldn't trigger any re-render. The workaround: `t()` itself touches `Alpine.store('i18n')._v` on every call (`void store._v` in `i18n.js`), so each invocation registers `_v` as a dependency of whatever effect ran it. `setLanguage()` bumps `_v`, which invalidates every effect that has called `t()`. Cost: a single counter bump re-evaluates every translated binding on the page — cheap because Alpine's binding count is small.

Reason keys in `constants.js` are i18n keys. They double as the identifier sent over WebSocket and the translation lookup key — adding a reason means one entry in `constants.js` and one entry in each locale file; no backend change required.

### Demo mode

`launchDemo()` creates a real session via `POST /api/sessions`, then opens 4 browser windows with `?code=XXXX&demo=<role>` params. `init.js` reads those params before Alpine boots and stores them in `window._demoParams`; `app.js init()` picks them up and auto-joins the specified role. Requires the browser to allow pop-ups.

### Security note

The display screen shows `sessionName` but not `sessionCode` — deliberate, to prevent the code from being visible on a projected screen that anyone in the room could copy.
