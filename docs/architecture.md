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
- `GET /vportal` — alternate landing page for VPortal-integrated sessions; serves the identical HTML as `/`. The client infers session kind from `location.pathname` at create time. No server-side marker.
- `GET /health` — single endpoint used by Railway. Currently conflates liveness + readiness.  
*Why one endpoint:* Railway consumes a single health URL; splitting earned nothing on this platform. Cost: on ECS/K8s, a slow snapshot save could trip a "not ready" signal and cause an unnecessary restart loop — those platforms want `/livez` (is the process up?) separated from `/readyz` (can it serve traffic?).
- `POST /api/sessions` — create a session. Accepts optional `kind: "generic" | "vportal"` (default `generic`); rejects other values with 422. Rate-limited to 10/hour/IP via slowapi.
- `GET /api/sessions/{code}` — look up an active session. Returns `{"exists": true, "kind": ..., "staging_available": ...}` on 200 or 404 with `{"detail": "Session not found"}`. Path pattern `^[A-Z0-9]{8}$` rejects malformed codes with 422 before touching the session map. Rate-limited to 30/minute/IP via slowapi.  
*Why a separate endpoint instead of validating at WebSocket join:* fail-fast UX. Without it, a typo gets the user as far as the role-selection screen before failing — at a live competition that's a real cost.  
*Why the lookup also returns `kind`:* it is the single source of truth for "should the VPortal connect button appear on Select Role?" Reading from the server avoids relying on `location.pathname` (which the back-nav code scrubs to `/` via `replaceState` on every load) and lets a device that joined via QR (plain `/`) still see the connect button when the underlying session was created via `/vportal`. *Why no session name in the response:* minimizes information disclosure; the kind + existence is all callers need.
- `POST /api/vportal/login` — proxy endpoint; forwards browser credentials to a federation's VPortal instance via a host-allowlisted outbound request and returns the JWT plus the server-clamped polling interval. See *VPortal integration* below.
- `POST /api/vportal/graphql` — proxy endpoint; forwards GraphQL reads to VPortal with `Authorization: Bearer <jwt>`. Read-only by construction: mutations and any operation outside a hard-coded allowlist of four read queries are rejected with 400 before the outbound call.
- `GET /static/*` — static assets (CSS, JS, fonts) served by FastAPI. In an AWS deployment these would move to CloudFront → S3.

Security:

- Standard hardening headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, HSTS.
- CSP: scripts, styles and fonts only from `'self'` (plus the Umami analytics host for its script and beacon, and `api.web3forms.com` for the contact form). It allows `'unsafe-inline'` and `'unsafe-eval'` — Alpine compiles `x-show`/`x-bind` expressions at runtime via `eval`; the framework will not function without it. XSS posture is recovered structurally: the app never renders user input as HTML. The only user-controllable string written to the DOM is the session name, which is set via `x-text` (text node, not HTML).
- WebSocket origin check via `ALLOWED_ORIGIN`. In-code default is `"*"` for local dev; **production overrides this via the Railway env var `ALLOWED_ORIGIN=https://iron-verdict.com`**, so the live deployment rejects cross-origin WebSocket handshakes.  
*Why the origin check matters:* Same-Origin Policy does not apply to WebSockets — without a server-side `Origin` check, any site could open a WS to `/ws` from a victim's browser and hijack the session (Cross-Site WebSocket Hijacking).  
*Why the permissive default:* local dev convenience.  
*Caveat (tracked in [#60](https://github.com/abti247/iron_verdict/issues/60)):* secure-by-discipline rather than secure-by-default — a new deployment surface that forgets to set the env var would silently accept any origin. Failing loud at startup in non-dev environments without an explicit value would close that gap.

## WebSocket surface

`GET /ws` is the single WebSocket endpoint. Message types after `join`:

- `vote_lock` — judge locks a colour (and optional reason), tagged with the `lift_id` it was cast for. Always answered to the voter with exactly one of:
  - `vote_ack` `{color, reason, lift_id}` — the vote is stored. A duplicate `vote_lock` (judge already locked) is also acked, carrying the **stored** vote: resends are idempotent and the server's vote is what the judge sees.
  - `vote_rejected` `{code, message}` (logged as `vote_rejected`) — `code` is `lift_changed` (the `lift_id` is stale), `reason_required` (reasons are mandatory and none was given) or `invalid` (bad colour/reason/lift id, or not a judge). Nothing is stored. `SessionManager.lock_vote` checks the lift before the mandatory reason, and the already-locked case before both. Why: a stale vote must always surface as `lift_changed` — answering `reason_required` would let the judge add a reason and turn the previous lift's colour into a vote for the new lift.
- `settings_update` — head judge changes lift type, show-explanations, require-reasons.
- `timer_start`, `timer_reset` — head judge controls the 60-second attempt timer.
- `next_lift` — head judge resets state for the next attempt; broadcasts `reset_for_next_lift` with the new `lift_id`.
- `end_session_confirmed` — head judge ends the session.
- `pong` — client reply to server-initiated heartbeat ping.

Head-judge-only messages (`timer_start`, `timer_reset`, `next_lift`, `end_session_confirmed`, `settings_update`) from any other role get an `error` and leave the session unchanged — the UI only hides these buttons, the server is the actual guard.

*Why `vote_ack` / `vote_rejected` instead of fire-and-forget:* the client's socket can look open while the network is gone, and `websocket.js` drops sends on a closed socket. Without an explicit answer the judge screen cannot know whether a vote counted; showing "Vote Locked" optimistically let a lost vote hang the competition with nobody seeing why. *Why `lift_id`:* a vote queued offline is resent after reconnect; if the head judge advanced meanwhile, the server would otherwise count it for the wrong lift. `lift_id` is optional in `vote_lock` so a tab still running the previous frontend during a deploy keeps working (without the stale-lift check).

Per-connection rate limit: 20 messages/second via a sliding window. Exceeding it closes the connection with code 1008. Per-IP concurrent-connection cap is delegated to the edge (Cloudflare).

*Why split the limits this way:* per-connection caps are cheap and local — they protect the message-handling path from a single buggy or malicious client. Per-IP concurrency caps need cross-connection awareness that the edge already has, plus Cloudflare can tie them to broader signals (bot scoring, ASN reputation) that the app process cannot.

## State management

Two in-process managers, each guarded by its own `asyncio.Lock`. The two locks are never held together.

*Why two locks instead of one:* the managers have orthogonal concerns — domain state vs. transport — and conflating them would either serialize all WebSocket I/O behind every domain mutation, or vice versa. *Why never held together:* taking two locks in any order opens a deadlock window if some future path ever inverts the order. The rule "never both" makes deadlock structurally impossible. Accepted cost: any operation that conceptually needs both must split into two phases (compute under one lock, then act under the other) — no such operation has been needed so far.

### `SessionManager`

- Holds `self.sessions: dict[str, dict]` — domain state per session code.
- Each session records: `name`, `kind` (`"generic" | "vportal"`, immutable after create), `judges` (left/center/right with vote, reason, locked, connected, reconnect token), `phase`, `state`, `settings` (`show_explanations` default on, `lift_type` default squat, `require_reasons` default off; snapshots keep their stored values), `timer_started_at`, `timer_frozen_ms`, `lift_id` (counter, +1 on every reset for next lift; `0` for snapshots that predate it), `last_activity`.  
*Why `kind` lives in session state:* drives whether the VPortal connect button appears on Select Role and whether the display screen starts polling. Set at create, read by every consumer via `GET /api/sessions/{code}`.
- Generates 8-character alphanumeric session codes.
- Owns business rules: vote-lock state machine, all-judges-locked → results computation (including the IPF rule that a disconnected non-voter blocks results), timer freeze on results, reset for next lift.

### `ConnectionManager`

- Holds `self.active_connections: dict[session_code, dict[role, WebSocket]]` — transport registry only.
- Tracks `_last_pong: dict[WebSocket, float]` for the heartbeat task.
- Provides `broadcast_to_session`, `broadcast_to_others`, `send_to_role`, `send_to_displays`. Per-socket errors are swallowed and emit warning logs by name.

*Why swallow per-socket errors:* one dead or slow client must not abort the broadcast to the others. The alternative — propagating the first send failure — would let a single misbehaving client (or a TCP RST on one judge's connection) stall state propagation to the remaining judges and the display.

## Persistence

`/data/sessions.json` is a periodic JSON snapshot used **only** for crash recovery, not for state sharing between processes. Checked every 60 seconds by the lifespan task and written only if its content changed since the last write (or since the load at startup); on shutdown it is written once more, unconditionally. On Railway it is volume-backed; on ECS/Fargate it would need EFS.

*Why a JSON file and not a database:* the only requirement is "survive a Railway restart with active sessions intact." A flat file gives that with zero operational overhead — no migrations, no connection pool, no schema. Accepted cost: up to 60 s of mutations lost on crash, no point-in-time recovery, no querying. *Why not skip persistence entirely:* a deploy or OOM mid-event would wipe judges' in-flight votes; the 60 s snapshot bounds the blast radius.

Snapshots exclude reconnect tokens — those exist only in memory and die with the process. Reconnects after a restart are not supported.

*Why exclude tokens from the snapshot:* tokens are session-scoped secrets. Persisting them widens the blast radius if `/data/sessions.json` ever leaks (volume mount misconfiguration, debug dump, leaked backup). The trade-off is intentional — after a restart, judges rejoin via the session URL and pick a free role; the friction is acceptable for a 60-second-recovery-window failure mode.

## Reconnection model

- **Judges** receive a 32-character `reconnect_token` on first join. A new WebSocket presenting the matching `(session_code, role, token)` triple replaces the existing connection. An identity guard prevents the disconnect handler of the old socket from clobbering the new one. Tokens survive `reset_for_next_lift`.
- **Concurrent joins on one role** yield exactly one success. Single-worker asyncio is the guarantee, not a lock: `join_session` is synchronous, so its "role free?" check and the write cannot interleave. The reconnect takeover awaits (closing the old socket) between token check and slot takeover, so it re-checks the token afterwards — a second client with the same token (e.g. a duplicated browser tab copies `sessionStorage`) gets "Role already taken" once the winner has rotated the token. *Why:* otherwise both clients got `join_success` and one acted as judge without receiving broadcasts ([#57](https://github.com/abti247/iron_verdict/issues/57)). Breaks with multiple workers like all in-memory state.
- **Displays** have no reconnect token. Each display join takes the next free display slot (`display_aabb1122` random suffix). Displays are interchangeable viewers, capped per session by `DISPLAY_CAP` (default 20).
- Judge slots cap at 3 (left, center, right) and are exclusive.
- **Votes across reconnects:** the judge screen keeps an unconfirmed vote in memory and in `sessionStorage.iv_pending_vote` (memory covers a failing storage write, storage covers a reload). After every `join_success` it reconciles with the server's snapshot of that judge: server has a vote → shown as confirmed; server has none but one is pending → resent automatically (a stale `lift_id` is rejected with `lift_changed`); neither → open. A vote shown as locked locally but unknown to the server (the lift was reset while offline) reverts to open.

*Why tokens for judges but not displays:* judges have identity that must persist across reconnects — their vote, lock state, and reason are tied to a specific role. Displays are read-only viewers whose only state is "what's currently on screen", recoverable from the next broadcast. Adding tokens for displays would buy nothing and complicate slot bookkeeping for an unbounded viewer count.

*Why the identity guard:* when a judge reconnects, the new socket replaces the old one in the registry. Without the guard, the *old* socket's disconnect handler (which fires as the underlying TCP tears down) would clear the slot — disconnecting the live new socket and dropping the judge.

*Why a display cap:* every state change fans out to all displays in a session. Without a cap, a single session could become a broadcast amplifier — a malicious actor opens hundreds of display tabs, every `vote_lock` multiplies into hundreds of WebSocket sends, and CPU/bandwidth on the single worker spikes.

## Background work

Single `lifespan` task runs two periodic operations:

- **Snapshot save** — every 60 seconds, only if the serialized sessions differ from the last snapshot written (or loaded). Serialization runs in the event loop; the file write runs in a worker thread (`asyncio.to_thread`). Deleting the last session changes the content to `{}`, which is written once. The shutdown save stays synchronous and unconditional.  
*Why compare content, not a dirty flag:* sessions are mutated in many places (votes, timer, settings, connected flags); a flag would have to be set at every one of them, and a forgotten one means lost state after a restart. Serializing a few kilobytes once a minute is cheap. *Why serialize before the thread:* the thread must not read session dicts the loop mutates at the same time. *Why no timeout on the write:* a thread cannot be cancelled; during normal running a hung disk only stalls the cleanup loop, not voting or the heartbeat. A lock around the file write keeps the shutdown save from interleaving with an in-flight periodic write — on a hung disk the synchronous shutdown save then waits on that lock, as a hung synchronous write did before.
- **Cleanup expired sessions** — every 30 minutes; deletes sessions with `last_activity` older than 4 hours.

A server-initiated heartbeat (`heartbeat_sweep`, every `HEARTBEAT_INTERVAL_SECONDS` = 5 s) pings every WebSocket client and closes (code 1001) any client without a `pong` for more than `PONG_STALE_SECONDS` = 15 s — effectively 15–20 s, since the check runs once per interval. The client runs the mirror-image watchdog (see [WebSocket client](#websocket-client)).
*Why 5 s / 15 s:* a half-open connection — typical on venue Wi-Fi when a device switches access points — fires no close event on either side; with the former 30 s / 70 s a judge looked connected for over a minute while votes went nowhere. One ping per client every 5 s is negligible next to the 20 messages/s rate limit.

## VPortal integration

Optional, pull-only overlay of the current lifter on the display screen for sessions created via `/vportal`. The integration is opt-in at session creation; generic sessions are unaffected.

**Architecture.** Stateless Python proxy ([src/iron_verdict/vportal_proxy.py](../src/iron_verdict/vportal_proxy.py)) + client module ([src/iron_verdict/static/js/vportalClient.js](../src/iron_verdict/static/js/vportalClient.js)). The JWT lives in browser `localStorage` keyed by session code (`vportal:<sessionCode>`); the proxy holds no tokens, no credentials, and no per-session state — only a shared `httpx.AsyncClient` plus the host and operation allowlists.

*Why client-side storage instead of server-side sessions:* a server-side token store concentrates risk — one server-side leak compromises every active session. localStorage scopes the blast radius to a single device; the existing XSS surface is small (no user-generated content rendered to HTML, Alpine `x-text` only). Accepted cost: standard browser threat model — XSS would steal the token.

**Data flow per polling cycle.** Browser reads `{host, token, competition_id, stage_id}` from localStorage; the proxy forwards two GraphQL reads per tick (`competitionGroupList`, then `competitionAthleteAttemptList`) with `Authorization: Bearer <token>`. `profile.competition.id` is fetched once at login and cached. Polling cadence is server-controlled via `VPORTAL_FETCH_INTERVAL_MS` (default 3000ms, clamped to 2000ms minimum); the client receives the clamped value at login and uses it — no client-side default.  
*Why server-controlled with a hard minimum:* prevents a malicious or buggy client from polling sub-2000ms, and keeps tuning a between-event operation (Railway env var → redeploy) rather than a code change.

**Security boundaries.**

- **Host allowlist** in the proxy: `bvdk.vportal-online.de`, `oevk.vportal-online.de`, `staging-bvdk.vportal-online.de`, `staging-oevk.vportal-online.de`. When `TEST_MODE=1`, `localhost`/`127.0.0.1` (and `host:port` variants) are additionally allowed for the E2E fake-server fixture. Any other host returns 400 before the outbound call — the proxy is not an open relay.
- **GraphQL operation allowlist**: hard-coded set of four read operations (`profile`, `competitionStageList`, `competitionGroupList`, `competitionAthleteAttemptList`). Mutations and any other top-level field are rejected with 400. Iron Verdict therefore cannot write to VPortal even if a modified client tries — the official scorekeeper continues to record verdicts on the VPortal side manually.  
*Why an allowlist instead of trusting "we only send reads":* defence in depth. A leaked or stolen JWT grants whatever permissions the operator account has; without the gate, a malicious client could send mutations through the same proxy that's already authenticated. The four-operation allowlist makes write attempts a 400 at our edge.
- **No credential storage server-side**. Login credentials cross the proxy in-memory for the duration of one request and are not logged. The JWT flows back to the browser.

**Failure isolation.** Every VPortal failure path — wrong credentials, expired token, upstream 5xx, unreachable network, empty active group, missing stage — leaves the core judging functionality (lights, timer, votes, verdict, WebSocket layer) fully operational. The overlay is strictly additive: corners hide, an unobtrusive banner may appear, and the rest of the display continues to render.

**Display overlay lifecycle.** On a display join `startDisplayOverlay()` reads the session kind from `GET /api/sessions/{code}` and starts the poller only for `kind=vportal` on a device that has its own VPortal login with a stage. If that lookup fails (network error or non-2xx) on such a device, the disconnected banner shows and the lookup is retried at the polling interval until it succeeds; a device without its own login looks up once and never polls. Leaving the display (role-select, landing, session end) calls `stopDisplayOverlay()`, which stops the poller and any pending retry and clears the overlay; every start begins with the same stop, so a display never runs two pollers. A run counter keeps a lookup or poll that was still in flight when the display was left from starting a poller or writing the overlay. A final `join_error` stops the overlay as well.  
*Why retry the lookup:* a display is typically reloaded exactly when the venue network is bad; the WebSocket reconnects on its own, and before #112 the lifter data then stayed missing without any hint until another reload. *Why the existing banner and not a new message:* to the person at the display the effect is the same as a lost VPortal connection — lifter data missing — and it clears itself once polling works.

**Upstream errors on `/login`.** Every upstream failure of the login flow returns **424** with `detail: {"reason": <code>}` — `no_session_cookie` (`/account/login` set no `__Host-VPORTAL`/`VPORTAL` cookie), `token_exchange_failed` (`/auth/token` answered neither 200 nor 302/401/403; `upstream_status` added to `detail`), `missing_access_token` (200 without an `access_token` in a JSON object), `unreachable` (transport error on either request, no retry). Wrong credentials (302/401/403 from `/auth/token`) stay 401 and write a `vportal_login_rejected` **info** log with the same status/header/cookie-name fields — a missing role may look like a wrong password to us, and the redirect target tells them apart. Each 424 writes one `vportal_login_failed` warning with `reason`, `host`, the status and `Location` of `/account/login` and `/auth/token`, the token response's `content_type`, the **names** of the cookies `/account/login` set, and for `unreachable` the `upstream_path` and `error` class — never cookie values, credentials or bodies. The connect dialog maps the reason to a translated message (`static/js/vportalErrors.js`); unknown reasons and other statuses get a generic message with the HTTP status.  
*Why 424 instead of 502:* Cloudflare replaces the body of an origin 502 with its own "Bad gateway" page, so the reason never reached the dialog or the browser's network tab (staging login, 2026-10-13, issue #100). A non-5xx status passes through unchanged. `/graphql` keeps 502 — the polling client only counts failures there.

**Upstream errors on `/graphql`.** The proxy maps VPortal failures to explicit statuses so an upstream problem never looks like an Iron Verdict bug (500): 401 → 401 (`token-expired` in the client); 5xx → 502 "VPortal upstream error"; a transport error (connection closed without response, connect error, timeout, reset) is retried **once**, immediately (logged as `vportal_transport_retry` at info level with `host` and `error` class), and only a second failure returns 502 "VPortal upstream unreachable" plus a `vportal_upstream_unreachable` warning log (`host`, `error` class). HTTP error responses are never retried. The login path has no retry.  
*Why retry transport errors:* the shared `httpx.AsyncClient` pools keep-alive connections; VPortal or a NAT/load balancer can close an idle one just before the next poll reuses it (seen live 2026-05-23 as a single `RemoteProtocolError` between successful polls). httpx discards the dead connection, so the retry runs on a fresh one and the display never notices. Safe because the operation allowlist makes every forwarded call a read. *Why no delay before the retry:* the cause is a stale connection, not an overloaded upstream. *Why log the retry although it usually succeeds:* the stale-connection explanation rests on one observed incident; the retry log shows in the field how often and when it happens, and whether the error class fits. Accepted cost: if VPortal hangs, a request takes up to two client timeouts (2 × 5 s) before the 502.

**Configuration env vars** (in addition to the existing surface — `HOST`, `PORT`, `SESSION_TIMEOUT_HOURS`, etc.):

| Var | Default | Effect |
|---|---|---|
| `VPORTAL_FETCH_INTERVAL_MS` | `3000` | Polling cadence for the display overlay, in ms. Server-side clamped to 2000ms minimum; the clamped value is returned to the client at login. |
| `TEST_MODE` | unset | When `1`, the proxy accepts `localhost`/`127.0.0.1` (with optional port) as VPortal hosts. E2E tests only — never set in production. |
| `EXPOSE_VPORTAL_STAGING` | unset | When `1`, the connect modal exposes a third federation option (BVDK Staging) pointing at `staging-bvdk.vportal-online.de`. Unset on production once staging access expires. |

**Reference:** [docs/vportal-fake-server-fidelity.md](vportal-fake-server-fidelity.md) — pre-staging risks and what was resolved against the referee codebase.

## Edge

- Cloudflare proxy (orange cloud) sits in front of Railway. SSL/TLS Full (strict), Bot Fight Mode on.
- Domain: `iron-verdict.com` → CNAME → Railway.

## Build and deployment

- One Docker image (`Dockerfile`, Python 3.13 slim). The entrypoint chowns `/data` (Railway mounts volumes as root) and drops to `appuser` via `gosu`. `APP_VERSION` is baked in at build time as `sha-<commit>` and shown in the landing-page footer.
- CI builds the image on every PR and smoke-tests the running container ([.github/workflows/image.yml](../.github/workflows/image.yml)). Commits on `main` that pass CI and the image check are pushed to `ghcr.io/abti247/iron_verdict` as `sha-<commit>` and `main`; a `vX.Y.Z` Git tag re-tags that same image without rebuilding and creates the GitHub release.
- Railway runs a release tag of the GHCR image. Deploy and rollback are a manual change of the tag in the Railway service settings. Runbook: [docs/release.md](release.md).

*Why build once, promote:* what runs at a competition is bit-identical to what was tested, and a rollback is a tag change (about a minute) instead of a local rebuild.

## Known scale flags

These block multi-instance deployment. Listed for the Phase 6 AWS migration, not as immediate fixes.

| Flag | Impact |
|---|---|
| In-memory `SessionManager.sessions` | No horizontal scaling. Fix path: Redis (state + pub/sub). |
| In-memory `ConnectionManager` | Broadcasts don't cross instances. Fix path: Redis pub/sub. |
| `/data/sessions.json` | Needs EFS or persistent volume on ECS. |
| `ALLOWED_ORIGIN="*"` in-code default | No CSRF risk on the *current* production deploy (Railway env var overrides to `https://iron-verdict.com`), but secure-by-discipline rather than secure-by-default — a new deployment surface that forgets to set the env var would silently accept any origin. Fix: fail loud at startup in non-dev mode if the value is unset or `"*"`. Tracked in [#60](https://github.com/abti247/iron_verdict/issues/60). |
| `/health` conflates liveness + readiness | ECS/Kubernetes prefer separate `/livez` + `/readyz`. Tracked in [#64](https://github.com/abti247/iron_verdict/issues/64). |
| `_handle_shutdown` does not drain WebSockets | Clients flap on rolling deploys. Tracked in [#63](https://github.com/abti247/iron_verdict/issues/63). |
| No Prometheus metrics surface | Phase 3 work on the roadmap. |

## Frontend

No-build single-page application. One HTML file served by FastAPI's `StaticFiles`; JS loaded as native ES modules via `<script type="module">`. No bundler, no transpilation, no node_modules.

*Why no build step:* the app is small enough that a bundler earns nothing — no tree-shaking pay-off, no code-splitting need, no TypeScript surface to compile. The dev loop is "edit file → refresh"; CI does not need a frontend build stage; the Docker image carries no `node_modules`. Accepted cost: no minification (file sizes are already small, Cloudflare brotli-compresses on the wire), no TS, and any future move to a framework with required tooling (React, Svelte) would need to introduce the toolchain. The Vitest test runner *does* pull in `node_modules`, but only as a devDependency — it never ships to production.

**Vendored dependencies (served same-origin, no CDN):**

- `static/vendor/alpinejs-3.14.1.min.js` — Alpine.js (CDN build, auto-starts on load; `init.js` injects it).
- `static/vendor/qrcodejs-1.0.0.min.js` — QRCode.js, QR code on the role-select screen.
- `static/fonts/` + `static/css/fonts.css` — Bebas Neue and Rajdhani (400/600/700) as woff2, the same `unicode-range` subsets Google Fonts serves (latin, latin-ext, devanagari); the browser only downloads a subset a page actually uses. `font-display: swap`.
- License files sit next to the files (`vendor/LICENSE-*`, MIT; `fonts/OFL-*.txt`, SIL OFL 1.1). Upgrading a library means replacing the file and its versioned name in `index.html` / `init.js`.

*Why vendored:* everything after a judge or display opens the page is critical path, and venue Wi-Fi may have no or very slow internet. With Alpine on a CDN the page stayed invisible (`x-cloak`) when the CDN was unreachable; with Google Fonts a slow connection held up the start until the request timed out. `init.js` still waits for the four font faces before injecting Alpine, so the first render is in the right font — served locally, that wait is milliseconds. `test_offline_assets.py` runs a full competition with every foreign host blocked.

**Boot sequence:** `<html class="booting">` is in the markup. `boot.css` hides every top-level element of `<body>` except `.boot-screen` (spinner, "Laden … / Loading …") while that class is set. `init.js` loads the locales and fonts, injects Alpine, and removes `booting` on `alpine:initialized`, so the first screen Alpine renders replaces the indicator in one step. On a reload with a stored session that first screen is the *reconnecting* screen (see *Screen machine*), never the landing screen. If Alpine has not started after 10 s, a CSS animation delay swaps the indicator for a bilingual "could not be loaded" message with a reload link (`<a href="">`, keeps the query string); if the Alpine download fails, `init.js` sets `boot-failed` and the message shows at once. The boot screen is plain markup without Alpine or i18n.

*Why a global boot state instead of `x-cloak` alone:* every new top-level element had to remember `x-cloak`; the VPortal modal did not and flashed up as a full-screen login dialog until Alpine started. The boot state hides everything regardless (`x-cloak` stays as well). *Why the fallback is pure CSS:* it also appears when no JS runs at all (e.g. `init.js` fails), where a JS timer would never fire — a silent black screen becomes an understandable message.

**External, not on the critical path:**

- Umami Analytics — cookieless, no personal data; loaded with `defer`, nothing waits for it.
- web3forms — contact form submission only.

**JS modules:** one store per kind of shared state, one module that owns the connection, one Alpine component per screen. `index.html` puts each screen's component on that screen's root element; `<body x-data>` only carries the `display-mode` class.

| File | Purpose |
|---|---|
| `init.js` | Entry point: reads demo URL params before Alpine boots, loads i18n and fonts, injects Alpine, ends the boot state (see *Boot sequence*), hands `popstate` events to the connection (`followHistory`). |
| `app.js` | Bootstrap: on `alpine:init` registers the stores and screen components, creates the connection and picks the first screen (`start()`). |
| `connection.js` | The one owner of the WebSocket: `joinSession`, session lookup, reload recovery start, `returnToRoleSelection` / `returnToLanding`, back-button handling, sending, and dispatch of every incoming message to `handlers.js`. All VPortal display-overlay start/stop calls. Plain object, dependencies (stores, storage, socket factory, `fetch`, `t`, `alert`) injectable for Vitest. |
| `handlers.js` | One named handler per incoming WS message type; each writes the stores (and calls connection flows such as leaving the session). An unknown type is logged, not dropped silently. |
| `sessionStore.js` | `Alpine.store('session')`: session code, name and kind, own role, `isHead`, `isDemo`, connection status, `serverRestarting`, judge connectivity, role-taken notice, the landing form (name, code, lookup error). Data only. |
| `navigation.js` | `Alpine.store('nav')`: current `screen`, `navigateTo()` with its history entries, the entry pathname, the popstate / navigate-in-place flags (see *Screen machine*). |
| `judgeStore.js` | `Alpine.store('judge')`: the judge's selection and vote state, `liftId`, the lift's result for the judge screen; vote methods from `voteDelivery.js`. |
| `displayStore.js` | `Alpine.store('display')`: phase, lights, reasons and verdict of the display. |
| `voteLight.js` | Vote → light colour (`white` / `red`) and card colour (`red` / `blue` / `yellow`, none for white); used by the display and judge stores. |
| `settingsStore.js` | `Alpine.store('settings')`: lift type, show reasons, require reasons. |
| `timer.js` | Module-level countdown interval (`startTimerCountdown`, `stopTimer`) and `Alpine.store('timer')` (shown time, expired; start / freeze / reset). |
| `voteDelivery.js` | Judge vote state machine (open → sending → confirmed), pending vote in `sessionStorage`, reconciliation after join, `vote_ack` / `vote_rejected` handling; methods of the judge store. |
| `roleTakeover.js` | Gives up rejoining after 25 s of "Role already taken" with a stale token: role-select with a "position signed in on another device" notice. |
| `reloadRecovery.js` | Reload recovery: restores the session stored in `sessionStorage.iv_session` behind the reconnecting screen, and the "session ended or expired" fallback to landing. Called by the connection. |
| `vportalStore.js` | VPortal state and methods as `Alpine.store('vportal')`: connect button and dialog on role-select, lifter overlay and disconnected banner on the display. The connection starts the display overlay on a display join and stops it on every way out of the display; the landing screen hands it the staging flag. Client, translator and `fetch` are injectable for Vitest. |
| `websocket.js` | WebSocket wrapper with short capped-backoff auto-reconnect, immediate reconnect on `online` / `visibilitychange` / bfcache restore, and heartbeat watchdog. |
| `screens/landingScreen.js` | Landing: create a session, look one up by code, links to demo, contact, privacy & legal notice. |
| `screens/contactScreen.js` | Contact form (web3forms). |
| `screens/demoIntroScreen.js` | Demo intro: opens a demo session in four windows. |
| `screens/reconnectingScreen.js` | "Connecting…" after a reload; Cancel. |
| `screens/roleSelectScreen.js` | Role-select: role buttons, QR code, role-taken notice (VPortal button reads `$store.vportal`). |
| `screens/judgeScreen.js` | Judge screen: reason-list scroll hint, role label, reasons for the chosen colour, head-judge controls (send via the connection). |
| `screens/displayScreen.js` | Display screen: zoom and settings panel (gear, `S`, `Esc`). |
| `constants.js` | `CARD_REASONS[liftType][color]` — arrays of i18n reason keys. |
| `i18n.js` | Locale loading, `t()` lookup, `setLanguage()`, Alpine store integration. |
| `vportalClient.js` / `vportalQueries.js` | VPortal proxy calls, JWT in `localStorage`, polling; the GraphQL read operations. |
| `vportalErrors.js` | Maps a failed VPortal login (status + proxy `reason` code) to the dialog message. Pure function, translator injected. |

*Why a connection module instead of a component:* the socket belongs to no screen and no element. With one owner no screen component can open a second socket (see the bfcache bug under *WebSocket client*), and every way out of the display (role-select, landing, session ended, final join error, back button) runs through the same module, so the VPortal overlay stop cannot be forgotten and no second poller starts. Join, reconnect, reload and role takeover — the most critical code — run under Vitest.

*Why server-driven state lives in stores:* a message must reach its state even when the screen that shows it is not in the DOM (`x-if`) or not visible. Handlers write the stores directly; components only read them and hold pure UI state (zoom, settings panel, scroll hint). No browser events as transport — with no listener a message would be lost silently.

*Why `x-if` for landing, contact, privacy, demo intro and reconnecting, `x-show` for role-select, judge and display:* screens that hold nothing are not in the DOM when not shown, so they cannot flash up. Judge and display must not be rebuilt on a reconnect; role-select keeps its QR code and VPortal button for the frequent judge ↔ role-select round trip. State an `x-if` screen needs after it is gone (the landing form, written by reload recovery and the leave flows) lives in the session store.

*Why a store for VPortal instead of its own component:* the connect button, the dialog and the display overlay sit in three separate places of the markup and share one connection, so a component scoped to one element cannot hold them. The session kind is not VPortal state: it is a session property (sent at create, read on role-select, corrected from the server on display start) and lives in `Alpine.store('session')`.

**CSS files:** `variables.css` (16 custom properties) → `base.css` (resets, typography) → `components.css` (buttons, inputs, orbs) → `layout.css` (per-screen wrappers) → `animations.css` (keyframes) → `boot.css` (boot screen and fallback, see *Boot sequence*).

### Screen machine

`Alpine.store('nav').screen` drives which screen is shown (`x-if` or `x-show`, see *JS modules*). The URL stays at `/`; only `history.state` changes:

```
(reload) reconnecting → judge / display / role-select   (failure or Cancel → landing)
judge / reconnecting → role-select with notice           (position taken by another device, see roleTakeover.js)
landing → role-select → judge
                     → display
demo-intro → (opens 4 pop-up windows)
contact / privacy  (info-only screens)
```

Real screen transitions go through `$store.nav.navigateTo(screen)`, which sets `screen` and pushes `{screen}` onto the browser history. `navigateTo` is idempotent — repeated transitions to the same screen (notably from `handleJoinSuccess` on every WebSocket reconnect) don't pollute the back-stack with duplicates. `app.js` seeds the stack with `replaceState({screen: 'landing'})`. The `popstate` listener in `init.js` passes `event.state.screen` to the connection's `followHistory()`, which dispatches to `returnToRoleSelection()` / `returnToLanding()` (which clear vote state and close the WebSocket) or sets `screen` directly for info-only targets; a `handlingPopstate` guard prevents the helper from re-pushing state during back-navigation. **Why:** before this, the browser back button exited the app — now it steps through screens (judge → role-select → landing) and properly tears down the live WebSocket on the way.

Reload behaviour follows the same model. `iv_session` is upgraded as the user moves forward — `{code}` once a code is created or validated, `{code, role, reconnect_token}` once a role is picked. On reload the connection's `start()` reads `iv_session` and, if it holds a code, sets `screen = 'reconnecting'` before Alpine's first render ("Connecting to session <code>", spinner, Cancel): full state rejoins the judge/display right away (the WebSocket retries as usual while the server is unreachable — the page stays on *reconnecting*); code-only state re-validates against `/api/sessions/{code}` and returns to role-select. `join_success` (or the successful lookup) replaces *reconnecting* with the real screen. A stale code (session ended or expired between reloads — `join_error` "Session not found" or a 404 lookup) clears `iv_session` and shows landing with an inline "Session <code> has ended or expired" message; other join errors keep their popup and then go to landing; a failed lookup (network) shows landing with the "Couldn't verify session" error and the code pre-filled. Cancel behaves like leaving the session (`returnToLanding()`: closes the socket, clears `iv_session`); a session lookup that answers after Cancel is ignored. **Why** a dedicated screen: a judge who reloads mid-attempt must not see the landing screen and think they were thrown out. **Why** no delay before the rejoin: `start()` runs on `alpine:init` against the already registered stores and the screen only changes on the server's answer, so the former 100 ms `setTimeout` protected nothing. Demo windows (`?code=…&demo=…`) still join after their own 100 ms delay and are not affected.

*Why rehydration uses `replaceState`, not `pushState`:* a one-shot `navigateInPlaceNext` flag tells the next `navigateTo` to replace the current entry instead of pushing. The post-reload back-stack therefore matches the pre-reload one exactly — same depth, same prior entries — so the existing role-select entry (or whatever was below judge before the reload) is what swipe-back returns to. Without this, mobile in-app browsers (e.g. iOS Safari opened from a QR scanner) skip JS-pushed history made after the reload and the swipe-back gesture exits the launching app instead of stepping back within iron-verdict.

QR entry point: `?session=XXXX` lands on the landing screen with the code pre-filled, immediately triggers the lookup validator, and navigates to role-select only if the code resolves to an active session. Invalid or unknown codes surface an inline error on landing. The init-time `replaceState` cleans the URL on entry regardless of outcome. **Why** URL params are captured before the replaceState: scrubbing the query string clears `window.location.search`, so the QR code must be read first.

### WebSocket client

`websocket.js` wraps the native `WebSocket` with:

- Reconnect waits 0.5 s → 1 s → 2 s → 3 s max, each ±20 % jitter; resets to 0.5 s on successful open.
  *Why so short instead of classic exponential backoff:* backoff protects servers with thousands of clients from a reconnect storm; a session has ~5 clients, so the trade-off favours recovery — with the old 16 s cap a judge could stay offline up to 16 s after the server was back (e.g. after a deploy). The jitter still keeps clients from hitting a restarted server in the same instant.
- Immediate reconnect while waiting for a retry: `online` (device back on the network), `visibilitychange` to visible (tab back in front) and `pageshow` with `event.persisted` (bfcache restore) cancel the pending retry timer and connect at once. An open socket or an attempt in progress is left alone, so these never create a second socket (an open-but-dead socket is the watchdog's job). If the socket is `CLOSED` without its close event having reached the wrapper (page frozen in the bfcache), it is abandoned like a watchdog drop and replaced. The listeners are removed on `close()`.
  *Why in the wrapper, not in the app:* the earlier bfcache handler in `app.js` called `joinSession()` again, creating a second wrapper while the first one's retry timer could still fire — two sockets for one judge. One wrapper owning every reconnect trigger keeps exactly one active socket.
- `stopped` flag prevents reconnect after intentional close (e.g. "Back to Landing").
- Heartbeat watchdog (judges and displays alike): if no server message of any kind arrives for 15 s (3 missed pings), the wrapper abandons the socket — handlers detached, `close()` called — reports it as dropped (indicator turns "reconnecting") and connects a new socket immediately. Checked every 2.5 s, so detection takes 15–17.5 s. A gap of more than 5 s between two checks means the browser paused or throttled timers (background tab, frozen page); the watchdog then restarts its count instead of reconnecting, since incoming messages may still be queued behind the pause.
  *Why detach handlers instead of waiting for `onclose`:* on a half-open connection the close handshake can hang for a long time; the old socket's late `onclose` or messages must not trigger a second reconnect or reach the app. *Why only on the open socket:* a socket that never opens fails via `onclose` and the normal backoff, so the watchdog cannot pile up connection attempts. The display's VPortal polling is started in `joinSession` (`connection.js`), not on reconnect, so a watchdog reconnect does not start it again; a new display join stops the previous poller first.
- On reconnect, sends `join` with `reconnect_token` from `sessionStorage` if one is stored.
- Server returns a new `reconnect_token` in `join_success`; stored in `sessionStorage.iv_session`.
- `join_error: "Role already taken"` with a stored token means the token no longer matches (a matching token always takes the slot). It is retried silently for up to 25 s from the first rejection in a row (`roleTakeover.js`); after that the position counts as taken by another device: `returnToRoleSelection()` (socket closed, token dropped, `iv_session` back to `{code}`) with an inline notice naming the position. A `join_success` resets the streak. Applies to the reconnecting screen after a reload and to a judge screen that lost its connection.
  *Why retry at all:* if `join_success` with the new token is lost on a connection that dies, the server still counts that dead connection as connected until the heartbeat closes it (≤ ~20 s: 15 s without pong, swept every 5 s) and rejects the retry with the old token. *Why the client decides, not the server:* both cases are a token mismatch, so the server cannot tell them apart either. *Why 25 s:* the ~20 s worst case plus margin; the limit is checked on each rejection, it adds no wait.

### Client-side state

| Storage | Key | Content | Lifetime |
|---|---|---|---|
| `sessionStorage` | `iv_session` | `{code}` on role-select, `{code, role, reconnect_token?}` on judge/display | Tab close |
| `sessionStorage` | `iv_pending_vote` | `{code, role, lift_id, color, reason}` from LOCK IN until `vote_ack` / `vote_rejected` / next lift / leaving the judge screen | Tab close |
| `localStorage` | `iron-verdict-lang` | `'en'` or `'de'` | Persistent |
| `localStorage` | `iron-verdict:display-zoom` | Display screen zoom multiplier (0.7–1.5) | Persistent |
| `Alpine.store('session')` | — | Session code, name, kind, own role, `isHead`, `isDemo`, connection status, `serverRestarting`, judge connectivity, role-taken notice, landing form | Page lifetime |
| `Alpine.store('nav')` | — | Current screen, history flags | Page lifetime |
| `Alpine.store('judge')` / `display` / `timer` / `settings` | — | Vote and result state (`voteLocked` is derived), display lights and phase, shown time, session settings | Page lifetime |
| Screen components | — | UI-only state: display zoom and settings panel, reason-list scroll hint, contact form, demo running | Page lifetime (`x-if` screens: while shown) |
| `Alpine.store('vportal')` | — | VPortal connection, dialog step, stage list, current lifter on the display | Page lifetime |

*Why `sessionStorage` (not `localStorage`) for the reconnect token:* tab-scoped lifetime matches the lifetime of a judging session. If the token survived in `localStorage`, an old token could leak into a *new* session opened in the same browser later, leading to confusing "Role already taken" failures (server rejects because the role belongs to a stale judge identity). `localStorage` is reserved for genuinely persistent preferences like language.

### i18n

Both locale files (`en.json`, `de.json`) are fetched in parallel at startup. `t(key)` resolves dotted key paths (e.g. `"reasons.squat.red.depth"`), falling back to English if a key is missing. Reactivity is driven by a dummy `_v` counter in an Alpine store: `setLanguage()` increments it, forcing every `t()` call in the template to re-evaluate. Language resolution order: `localStorage` → `navigator.language` prefix → `'en'`.

*Why the dummy `_v` counter:* Alpine's reactivity is property-access-based — a template re-evaluates only when the reactive properties it reads inside the expression change. `t()` resolves the key against a module-level `locales` object, so by default no Alpine-tracked property is read and changing the language wouldn't trigger any re-render. The workaround: `t()` itself touches `Alpine.store('i18n')._v` on every call (`void store._v` in `i18n.js`), so each invocation registers `_v` as a dependency of whatever effect ran it. `setLanguage()` bumps `_v`, which invalidates every effect that has called `t()`. Cost: a single counter bump re-evaluates every translated binding on the page — cheap because Alpine's binding count is small.

Reason keys in `constants.js` are i18n keys. They double as the identifier sent over WebSocket and the translation lookup key — adding a reason means one entry in `constants.js` and one entry in each locale file; no backend change required.

### Demo mode

`launchDemo()` creates a real session via `POST /api/sessions`, then opens 4 browser windows with `?code=XXXX&demo=<role>` params. `init.js` reads those params before Alpine boots and hands them to `app.js` on `alpine:init`; the connection's `start()` auto-joins the specified role. Requires the browser to allow pop-ups.

### Display settings overlay

The display screen has a single interactive control: a low-contrast gear icon (top-left) and `S` keyboard shortcut, both of which open a small overlay with a 0.7×–1.5× zoom slider. The slider writes to `--display-zoom` on the display root; every responsive size on the display multiplies through that variable. Selection persists to `localStorage` as `iron-verdict:display-zoom`.

*Why a low-contrast gear plus a keyboard shortcut:* the display is mixed-deployment — sometimes the operator knows the app, sometimes a volunteer is at the keyboard. A faint gear is invisible at projector distance but discoverable on the operator laptop; `S` exists as the power-user path. There is no other interactive control on the display screen, so a single conventional dismiss model (`Escape`, click-outside) suffices.

*Why per-browser localStorage:* the same laptop typically goes to the same venue, so the setting should outlive a session. A new laptop re-tunes once. Server-side per-session storage would add a new API surface for a per-device UI preference — out of proportion with the value.

### Lights and cards

A light shows only the verdict of one judge: white (valid) or red (invalid). The colour the judge picked for an invalid vote (red, blue, yellow) is shown as a card under the red light — display 40 % × 20 % of the light (scales with it and `--display-zoom`), judge results panel 50 % × 25 %. Vote, protocol and server keep the four colours; only the rendering maps them (`voteLight.js`). The card is shown regardless of "Show reasons on display", which hides only the text.
*Why white/red plus card:* the classic referee-light convention; four light colours confused spectators (#115).

**Lights never move on the display.** The display content is vertically centred, so any height change would shift the lights. Therefore the card is always in the layout (`visibility: hidden` without a card), each light's column reserves light + card + two reason lines (`min-height` on `.display-orb-wrap`, which also sets `--orb-size` for the light), and "Waiting for judges…" shares one grid cell with the verdict stamp (they never show together; the stamp is always in the layout, hidden while idle). A reason longer than two lines still grows the column.
*Why so tight:* the reserved space has to fit the screen height at the largest zoom (1.5) on 1280×720, 1366×768 and 1920×1080 — hence the small padding/gaps of `.display-full` and the timer's negative bottom margin, which trims the empty descender space under its digits. `test_red_light_card.py` checks this.

### Reasons under the lights

The reason text sits centred under its light (display and judge results panel), centred by the column flexbox: at least light-wide (judge panel: up to 144 px), as wide as its longest whole word, and at most half the column gap into the neighbour's side. A word wider than that breaks at its soft hyphens (U+00AD), which `locales/de.json` sets by hand at the compound joints of long German reason words (`Hantel\u00adständern`); the browser shows a hyphen only where it actually breaks. Soft hyphens are break points for the box's `min-content` too, so an invisible, unhyphenated copy of the reason (`::after` with `content: attr(data-reason)`, `hyphens: none`) sizes the box to the longest *whole* word — otherwise words that fit would be split. Within multi-line reasons the browser still fills lines greedily and may use a soft hyphen there ("mit Hantel-" / "ständern"), as in normal German typesetting. Only a word without a fitting soft hyphen breaks anywhere, without a hyphen — the last-resort safety net. On the display each light's column is exactly as wide as the light, so the lights stay put when reasons appear, and the reason font scales with `vmin` and `--display-zoom` like the lights. In the judge panel the columns split the panel width and the reason font shrinks a little on phones (16 px at 320 px width, 1.29rem from tablet width up).

*Why soft hyphens instead of `hyphens: auto` or a bundled hyphenation library:* Chrome on Windows/Linux downloads hyphenation dictionaries on demand — an external runtime dependency that venue Wi-Fi may block, so automatic hyphenation would silently differ between devices. A bundled library (patterns + WASM, ~100 KB, async) would add load time and an async first render for a fixed catalog of a few dozen reasons. Soft hyphens are deterministic on every browser and cost nothing at runtime; a new long reason without one is caught by `test_reason_centering.py`.

### Security note

The display screen shows `sessionName` but not `sessionCode` — deliberate, to prevent the code from being visible on a projected screen that anyone in the room could copy.
