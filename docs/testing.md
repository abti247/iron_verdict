# Testing

Three tiers, kept honest by tooling boundaries:

- **Backend unit** — modules tested in isolation. No FastAPI involved.
- **Backend integration** — drives the FastAPI app through ASGI (`TestClient` for HTTP, `httpx_ws.aconnect_ws` for WebSocket).
- **End-to-end** — real Uvicorn on a random port (or an external server via `E2E_BASE_URL`); Playwright drives the browser against the real DOM.

## How to run

```
pytest tests/ --ignore=tests/e2e   # backend unit + integration
pytest tests/e2e/                  # E2E
pytest                             # everything
pytest --tb=short -v               # readable pass/fail
```

## Continuous integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every pull request and is reusable via `workflow_call`, so a main-branch pipeline can call the same checks instead of duplicating them. Three parallel jobs, each a required status check for merging into `main`:

| Job | What it runs |
|---|---|
| `backend` | Python 3.13 (same as the Dockerfile), `pip install -e ".[dev]"`, `pytest tests/ --ignore=tests/e2e` |
| `js` | Node LTS, `npm ci`, `npx vitest run` |
| `e2e` | Same Python setup + Chromium with its system packages (`playwright install --with-deps chromium`; only `install-deps` when the browser is cached), `pytest tests/e2e/` with `--tracing retain-on-failure --screenshot only-on-failure` |

- pip, npm and the Playwright browser download are cached. The browser cache key is the resolved Playwright version, because each Playwright release pins its own Chromium build.
- When `e2e` fails (or times out — then only tests that failed before the hang have artifacts), the traces and screenshots of the failing tests are uploaded as the `playwright-traces` artifact (kept 14 days), one trace per browser context. Open a trace with `playwright show-trace <trace.zip>` or at trace.playwright.dev. Only contexts created through pytest-playwright are recorded — the `page`/`context` fixtures and `competition.new_context()`. A bare `browser.new_context()` produces no trace, so new tests must not use it (the remaining one is `test_rejoin_via_qr_keeps_connect_button_visible` in the VPortal-protected `test_vportal_integration.py`).
- A new push to a PR cancels the still-running CI of the previous push.
- CI records a trace for every browser context, which makes E2E runs slightly slower than a plain local `pytest tests/e2e/`. If a test flakes in CI but not locally, rerun it locally with `--tracing on` before blaming the code — the timing-sensitive tests in [docs/e2e-known-risks.md](docs/e2e-known-risks.md) are the first suspects.
- No automatic retries. **Why:** retries hide flaky tests; a flaky test is fixed or documented in [docs/e2e-known-risks.md](docs/e2e-known-risks.md).
- Branch protection on `main` (configured by the maintainer in the repo settings): merge only via PR, `backend`, `js`, `e2e` and `image` required, branch must be up to date. No required reviewer approval — a sole maintainer cannot approve their own PRs on GitHub.

### Image check

[.github/workflows/image.yml](.github/workflows/image.yml) (job `image`, required on PRs) builds the Docker image with Buildx (GitHub Actions layer cache, `APP_VERSION=sha-<head commit>`), starts it with a named `/data` volume and `ALLOWED_ORIGIN=http://127.0.0.1:8000` (so the WebSocket smoke test exercises the real origin check) and runs the `remote_safe` E2E subset (see [Staging](#staging-release-chain)) against the **running container** from outside: `pytest tests/e2e/ -m remote_safe` with `E2E_BASE_URL=http://127.0.0.1:8000` and the raised staging rate limits (`RATE_LIMIT_SESSION_CREATE=60/hour`, `RATE_LIMIT_SESSION_LOOKUP=120/minute`). Afterwards it stops the container and requires `/data/sessions.json` to have been written by the app — proof that the entrypoint handed the root-owned volume to `appuser`. Container logs are always printed; Playwright traces go to the `playwright-traces-image` artifact on failure. **Why:** the other jobs test the source tree; a file dropped by `.dockerignore` or package data, a broken entrypoint or wrong permissions only show up in the built image. **Why the whole `remote_safe` subset and not only the smoke test:** it is exactly what staging runs before a release, so a test marked `remote_safe` that cannot run against a deployed server fails on its PR, not at release time.

The [Main workflow](.github/workflows/main.yml) runs `ci.yml` and `image.yml` on every push to `main` and pushes the tested image to GHCR only when both are green. For a release commit it continues with the staging run below and the [Release workflow](.github/workflows/release.yml). See [docs/release.md](docs/release.md).

### Staging (release chain)

For a release commit (version in `pyproject.toml` without a `v<version>` tag), job `staging` in `main.yml` deploys `sha-<commit>` to Railway staging (`https://ironverdict-staging.up.railway.app`) after the maintainer's approval and runs `pytest tests/e2e/ -m remote_safe` against it (`E2E_BASE_URL`, `E2E_EXPECTED_APP_VERSION=sha-<commit>`). Traces go to the `playwright-traces-staging` artifact. Green is required before the second approval can tag the release.

Tests marked `@pytest.mark.remote_safe` (marker registered in `pyproject.toml`): `test_smoke.py`, `test_competition_flow.py`, `test_judge_reconnection.py` and `test_reload_reconnecting.py` without its VPortal test. They exercise what only the real deployment has — Railway's proxy and TLS, WebSocket over the public domain, `ALLOWED_ORIGIN`, the `/data` volume — through the main flow, reconnection and reload.

Not marked, because they cannot run against a deployed server:

- **VPortal tests** (`fake_vportal_url`): need `TEST_MODE=1` and the fake server on the runner's `localhost`, which Railway cannot reach; `TEST_MODE` does not belong in a production-like environment. VPortal stays covered by the fake-server tests in the `e2e` job.
- **Tests that read or reset in-process state** (`session_manager`, `connection_manager`, `limiter`): the state lives in another process.
- Everything else stays in-process for run time: the subset covers the deployment-specific paths; feature edge cases do not depend on where the server runs.

Mark a new test `remote_safe` only if it uses neither of the above; the `image` job proves on the PR that it runs against a deployed server (over plain `http://127.0.0.1` — behaviour that differs only under `https` shows first on staging). Each staging test ends its sessions afterwards (`created_sessions`), and staging raises the rate limits per env var (the subset creates about 20 sessions from one runner IP; `60/hour` leaves room for a re-run, and keeps the publicly reachable staging from being flooded with sessions), never via `TEST_MODE`.

## Claude cloud environment setup

Claude Code cloud sessions start from a fresh VM. The maintainer enters this script under **Setup script** in the environment settings on claude.ai/code, so every session can run the full suite right away:

```bash
#!/bin/bash
set -euo pipefail
cd /home/user/iron_verdict
python -m pip install -e ".[dev]"
npm ci
python -m playwright install --with-deps chromium
# The VM ships a standalone pytest (uv tool) that shadows the project's
# pytest and lacks its plugins; remove it so plain `pytest` works.
uv tool uninstall pytest || true
```

Requirements and caveats:

- **Network access** (Network access → Custom, keep the default package-manager list): add `cdn.playwright.dev` — the Chromium build pre-installed on the VM rarely matches the Playwright version pip resolves; without the download E2E tests fail with "Executable doesn't exist". The app itself needs no external host at runtime (`test_offline_assets.py` enforces this), so no CDN has to be allowed.
- The script runs once per environment and the result is cached for roughly seven days. After a dependency change in `pyproject.toml` or `package.json`, run `pip install -e ".[dev]"` / `npm ci` in the session (or edit the script to force a rebuild).
- If plain `pytest` reports `ModuleNotFoundError` for a project dependency, it is the VM's standalone pytest — use `python -m pytest`.

## Conventions

- `pyproject.toml` sets `asyncio_mode = "auto"` — every `async def test_*` is automatically run as an asyncio test. No `@pytest.mark.asyncio` decorator needed.
- Backend tests rely on descriptive function names (no docstrings).
- E2E tests get a docstring — multi-step flows aren't obvious from the name alone.
- E2E tests find elements by `data-testid` (`get_by_test_id`), role, text or domain CSS classes (`.vote-btn`, `.lock-btn`) — never by Alpine attributes (`x-model`, `x-show`, `x-if`, `x-data`) and never through `_x_dataStack`. They set up state the way a user would (e.g. the head judge picks the lift type in the settings select), not by writing into the component. Screen roots carry `data-testid="<screen>-screen"`. **Why:** the frontend is split into several Alpine components (#65–#67) without visible change; tests tied to Alpine internals would break and could no longer prove that.
- `pythonpath = ["src"]` is set in `pyproject.toml`.
- [tests/conftest.py](tests/conftest.py) sets `ALLOWED_ORIGIN=*` before the app is imported (the app refuses to start without it), and reorders collection so every backend test runs before any E2E test. **Why:** pytest-playwright's session-scoped fixture creates an asyncio loop on the main thread and leaves it running for the rest of the session; once that happens, pytest-asyncio's per-test `Runner.run()` refuses to start with "cannot be called from a running event loop". Backend-first ordering keeps Playwright's loop out of the way so a single `pytest` invocation runs both suites cleanly. [tests/test_collection_ordering.py](tests/test_collection_ordering.py) guards the ordering.

## Backend tests

| File | Purpose |
|---|---|
| [tests/test_session.py](tests/test_session.py) | `SessionManager` unit. Code generation, create/join, vote-lock state machine, IPF rule (disconnected non-voter blocks results), timer-freeze math, settings, reconnect-token lifecycle, snapshot save/restore (write only on change, `{}` once after the last session is deleted, write in a worker thread, shutdown save waits for an in-flight write; the lifespan `cleanup_loop` uses the threaded save, logs and survives a failed write or cleanup, and shutdown still completes after a failed write), `kind` field validation (`generic` / `vportal` / reject unknown). |
| [tests/test_connection.py](tests/test_connection.py) | `ConnectionManager` unit with mocked WebSockets. Add/remove/get, broadcast variants, error-swallowing on send failure, heartbeat plumbing (`mark_pong`, `_last_pong`). |
| [tests/test_logging_config.py](tests/test_logging_config.py) | `JsonFormatter` produces valid JSON with `level`/`message`/`timestamp` and emits the whitelisted record extras (`_EXTRA_FIELDS`), including the VPortal proxy and login-failure fields — a new log field must be added to the whitelist or it is silently dropped. |
| [tests/test_config.py](tests/test_config.py) | `Settings` env-var parsing: `VPORTAL_FETCH_INTERVAL_MS` default, honor, and clamp-to-2000 minimum; `TEST_MODE` and `EXPOSE_VPORTAL_STAGING` boolean parsing; `ALLOWED_ORIGIN` required at startup (missing/empty → `ERROR` log, app startup fails and `python run.py` exits non-zero; explicit `*` and a concrete domain are accepted and logged); `RATE_LIMIT_SESSION_CREATE` / `_LOOKUP` default to `10/hour` / `30/minute`, an invalid value refuses startup, and configured values reach the endpoints (subprocess app: third request answers 429). |
| [tests/test_http.py](tests/test_http.py) | Integration — HTTP surface: session creation (validation, rate limit, `kind` accepted / rejected), rate limits counted per `CF-Connecting-IP` and not bypassed by a spoofed `X-Forwarded-For`, session lookup (exists / not found / malformed-format rejection / 404 log event incl. `client_ip` source / `kind` + `staging_available` in body), `/vportal` route serves identical HTML as `/`, `/static` responses carry `Cache-Control: no-cache` and answer `If-None-Match` with 304, `/health`, security headers, and the `session_created` log event. |
| [tests/test_vportal_proxy.py](tests/test_vportal_proxy.py) | Integration — VPortal proxy: host allowlist (production + staging accepted, localhost rejected without TEST_MODE, attackers rejected), operation allowlist (known reads accepted, mutations and unknown queries rejected with 400), login endpoint forwards cookie→JWT chain (session cookie `__Host-VPORTAL` or legacy `VPORTAL`, sent back under the name it arrived with) and returns the server-clamped polling interval, token rejection (302/401/403 → 401) writes one `vportal_login_rejected` info log without secrets, login upstream failures (no session cookie, token exchange status, missing/non-JSON token, transport error on either request) return 424 with their reason code and one `vportal_login_failed` warning whose formatted output contains no cookie values, credentials or bodies, GraphQL forwarding propagates 401 verbatim and maps 5xx to 502 (neither retried), retries once on a transport error (info log) and maps a second one to 502 with a warning log, maps a non-JSON body (200 HTML, 3xx empty) to 502 with a warning log containing no body or token, and passes JSON from other statuses through unchanged. Upstream simulated via `httpx.MockTransport`. |
| [tests/test_websocket.py](tests/test_websocket.py) | Integration — WebSocket protocol: join, vote lock (color, reason, mandatory-reason gate), `vote_ack` / idempotent duplicate ack / `vote_rejected` incl. stale `lift_id`, head-judge-only role checks (side judges get `error`, state unchanged), settings broadcast, timer, origin check, flood disconnect, reconnect tokens, concurrent joins/reconnects on one role (exactly one succeeds), `judge_status_update`, pong heartbeat, heartbeat interval/stale limit and `heartbeat_sweep` (ping fresh, close and remove stale, remove unpingable connections — never a newer one of the same role — and mark such judges disconnected), no orphaned entry after a second join, flood disconnect or handler exception, display cap, and `caplog` assertions on every major WS log event (incl. `client_ip` from `CF-Connecting-IP`). |
| [tests/test_changelog_section.py](tests/test_changelog_section.py) | `scripts/changelog_section.py` (release notes for the Release workflow): extracts a version's CHANGELOG section with its compare link, exact version match (no prefix), CRLF input, errors on missing or entry-less sections, CLI exit codes, and that the real `CHANGELOG.md` parses. |
| [tests/test_railway_deploy.py](tests/test_railway_deploy.py) | `scripts/railway_deploy.sh` (staging deploy of the release chain) against a fake Railway API and app on one local HTTP server: sends the project token, sets the image and deploys, waits for deployment status `SUCCESS` and then the footer version — also when staging already serves that version (re-run); fails on a GraphQL error (before deploying), a failed/crashed deployment, a deployment that never succeeds, and a footer that never shows the version. |
| [tests/test_collection_ordering.py](tests/test_collection_ordering.py) | Regression — asserts the collection hook in `tests/conftest.py` keeps every backend test ordered before any E2E test, so bare `pytest` keeps working. **Known false-negative on Windows + Python 3.14:** the test spawns `pytest --collect-only` as a subprocess and hits a Windows handle-capture quirk that fails even though the ordering it audits is correct. Verifiable by running `python -m pytest --collect-only -q` manually. |

## End-to-end tests

[tests/e2e/conftest.py](tests/e2e/conftest.py) provides:

- `server_url` (session-scoped) — starts Uvicorn on a random port, yields the URL, shuts down at session exit. With `E2E_BASE_URL` set it yields that URL instead and starts nothing (external mode: the Docker image in CI, Railway staging in the release chain).
- `_reset_server_state` (autouse) — clears sessions, connections, and rate limiter between tests. No-op in external mode.
- `created_sessions` (autouse) — in external mode, ends every session the test created once the test is over (also after a failure): joins as head judge over `/ws`, sends `end_session_confirmed` and checks that `GET /api/sessions/{code}` answers 404. Browser-created sessions are recorded automatically: the conftest overrides pytest-playwright's `new_context` so every context tracks its `POST /api/sessions` requests and records the code as soon as a response has fully arrived (after a reload its body is gone); requests still pending when the context is closed are waited for then (a test may end before the response of its last click arrived). A test that creates a session over plain HTTP appends the code to `created_sessions` itself. If the head-judge slot is still taken (a browser context not closed by the fixtures) or a connection error occurs (`httpx.TransportError`, or `WebSocketNetworkError` once the socket is open; e.g. a TLS read error over Railway's proxy, #143), it retries for 20 s, each connection error on a fresh client; the tests themselves are never retried. Other errors (e.g. `403` on the upgrade) fail at once; every session that cannot be ended, and every creation response that could not be read, fails the teardown with all codes listed. A session the test ended itself is skipped ("Session not found", logged by the server as `role_join_failed`). No-op in process. **Why:** runs against staging or production must not leave test sessions in the server's snapshot until they expire after `SESSION_TIMEOUT_HOURS` (#137).
- `competition` — yields a `CompetitionHelper` that encapsulates session creation, role joining, voting, and browser-context cleanup. `competition.new_context()` opens an extra context for manual flows; it goes through pytest-playwright's `new_context` fixture so the context is traced on failure.
- `fake_vportal_url` (session-scoped) — starts [tests/e2e/fake_vportal.py](tests/e2e/fake_vportal.py) (a tiny FastAPI app that mimics VPortal's `/account/login`, `/auth/token`, and `/graphql`) on a random port and yields `host:port`. Used by `test_vportal_integration.py`; skips in external mode (needs the in-process server's `TEST_MODE`). Sets `TEST_MODE=1` and `VPORTAL_FETCH_INTERVAL_MS=2000` at module import so the proxy accepts the fake host and polls fast enough for tests. The fake server exposes `/_control/{force_token_invalid,unreachable,clear_attempt,restore_attempt,reset}` so tests can simulate error states.

[tests/e2e/network_switch.py](tests/e2e/network_switch.py) is a shared helper (not a fixture): `join_with_network_switch` joins a judge or display in a context with an init-script `WebSocket` patch; `cut_network` closes its socket and sends every further attempt to a closed port, `restore_network` lets attempts through again (pass `conn_dot=".display-tag .conn-dot"` to `cut_network` for a display). The switch lives in `localStorage`, so it survives reloads. `window.__ivSocketCount()` / `__ivLastSocketClosed()` expose connection attempts for timing assertions.

| File | Scenario |
|---|---|
| [test_smoke.py](tests/e2e/test_smoke.py) | Landing renders; "Create New Session" reaches the role select; `/health`; every static asset the app loads (followed from `/`, `/vportal`, ES-module imports and CSS `url()`, including the vendored libraries and fonts) is served; app version rendered (`E2E_EXPECTED_APP_VERSION` pins it); WebSocket join as head judge (sends the page's `Origin`, like a browser); VPortal client modules load. `remote_safe`: runs in the `image` job against the container and on Railway staging before a release, so no in-process state. |
| [test_offline_assets.py](tests/e2e/test_offline_assets.py) | Venue without internet: every browser context aborts requests to hosts other than the test server; full competition still works (create, QR code on role select, 3 judges + display join, vote, verdict, judge reload, Next Lift, End Session), the real fonts are loaded (no fallback), and no host other than the deferred Umami analytics was even attempted. Fails if anything on the page comes from a CDN again. |
| [test_static_cache.py](tests/e2e/test_static_cache.py) | Stale browser cache after a deploy: imports a temporary module under `/static` with a `Last-Modified` 30 days back, changes it on the server, opens the app again in the same context (warm HTTP cache) and expects the new version. Without `Cache-Control: no-cache` the browser serves the old file heuristically and the test fails. In-process only (writes into the static directory); no `page.route`, because routing disables Chromium's HTTP cache. |
| [test_boot_loading.py](tests/e2e/test_boot_loading.py) | Boot state: holds the Alpine script request with `page.route` (no sleep) and checks that only the loading indicator is visible — never the VPortal modal or a screen — and that every rendered frame (sampled by an init script per `requestAnimationFrame`) showed either the indicator or the landing screen; aborted Alpine download shows the bilingual fallback at once and its reload link starts the app; a never-answered Alpine request shows the fallback after the 10 s CSS timeout (~10 s test); judge reload during a session shows only the indicator, then rejoins and votes. |
| [test_join_invalid_code.py](tests/e2e/test_join_invalid_code.py) | Landing-screen validation — Join button enables only at 8 chars; unknown code shows inline error and blocks navigation to role-select; typing clears the error; stale QR (`?session=...`) lands on landing with the code pre-filled and the error visible. |
| [test_competition_flow.py](tests/e2e/test_competition_flow.py) | **Regression gate.** Full lift cycle (white sweep + mixed verdict with a blue vote shown as red light with blue card + Next Lift), required-reasons branch, timer start/reset across all four screens. |
| [test_double_vote_prevention.py](tests/e2e/test_double_vote_prevention.py) | Locked vote survives refresh; re-voting blocked; Next Lift clears the lock. |
| [test_judge_reconnection.py](tests/e2e/test_judge_reconnection.py) | Refresh before/after voting, manual role-reselect, all judges refresh simultaneously, timer-frozen-after-results-and-rejoin. |
| [test_vote_delivery.py](tests/e2e/test_vote_delivery.py) | Vote cast while offline shows "Sending…" and is delivered after reconnect; pending vote survives a reload; stale vote after Next Lift is discarded with a message (also when reasons became mandatory meanwhile — `lift_changed` wins over `reason_required`); server-rejected vote (reason became mandatory) unlocks the screen with an inline message, no alert. Cuts the network with the init-script `WebSocket` patch from [network_switch.py](tests/e2e/network_switch.py), whose on/off switch lives in `localStorage`, so it survives reloads. |
| [test_session_stuck_states.py](tests/e2e/test_session_stuck_states.py) | Next Lift mid-vote, continue after a judge disconnects mid-vote, IPF rule via the browser, full reset of vote state. |
| [test_connectivity_indicators.py](tests/e2e/test_connectivity_indicators.py) | L/R dots on head screen update as side judges join/disconnect/reconnect; own dot transitions connected → reconnecting → connected (uses an init script to monkey-patch `WebSocket`); `server_restarting` broadcast renders the label. |
| [test_fast_reconnect.py](tests/e2e/test_fast_reconnect.py) | Reconnect speed: after an outage long enough for the retry wait to reach its 3 s cap, the judge is connected again within ~5 s of the network returning (vote confirmed, reload reconnects); a synthetic `online` event right after a failed attempt connects within 1.5 s with exactly one new socket (`visibilitychange` / `pageshow` share the code path; Vitest only). Uses the network switch from `network_switch.py`; ~10–15 s per test (waits out the real retry delays). Fails against the old 16 s backoff. |
| [test_heartbeat_watchdog.py](tests/e2e/test_heartbeat_watchdog.py) | Client heartbeat watchdog: an init script turns the first socket half-open (incoming messages and close event swallowed); judge and display switch to "reconnecting", reconnect on a new socket, and keep working (vote confirmed, result shown, reload). Also checks a healthy display keeps its socket for 20 s (no false reconnect). ~20–40 s per test because it waits out the real 15 s watchdog. |
| [test_orphaned_connections.py](tests/e2e/test_orphaned_connections.py) | No orphaned server registration: with `DISPLAY_CAP` = 1 the display's socket sends a second `join` (rejected), then display and left judge lose the connection, reconnect and reload; the display gets its slot back each time, the head judge sees L disconnected and connected again, the vote reaches the display, and `connection_manager` holds one entry per device. Not `remote_safe` (patches settings, reads in-process state). |
| [test_show_reasons_default.py](tests/e2e/test_show_reasons_default.py) | "Show reasons on display" is checked in a new session and a red vote's reason reaches the display without touching it; unchecking hides reasons on the next lift; after reloading display and head judge the setting stays off (stored value wins over the default). |
| [test_display_resilience.py](tests/e2e/test_display_resilience.py) | Display refresh recovers; mid-competition display join; two displays receive identical results. |
| [test_session_cleanup.py](tests/e2e/test_session_cleanup.py) | Teardown helper `_end_session` (used by `created_sessions` in external mode) against the in-process server with injected network errors: one TLS read error on connect, or one network error while reading the join reply → a fresh connection ends the session; errors until the deadline → the failure names the step and the error, the session stays open. |
| [test_end_session.py](tests/e2e/test_end_session.py) | Only head sees End Session; ending redirects all four screens; ended code unjoinable. |
| [test_role_protection.py](tests/e2e/test_role_protection.py) | Taken role rejected; role freed on disconnect; role switch via session-code link; head=center invariant. |
| [test_reason_catalog.py](tests/e2e/test_reason_catalog.py) | Rulebook wording of the reason catalog (issue #98): German UI (language stored in `localStorage`, then reload) — bench yellow offers "Kopf/Schultern angehoben" and "Handbewegung" separately and the shortened texts, the chosen reason appears verbatim on the display; deadlift red offers "Shoulders not behind bar" / "Schultern nicht hinter Hantel" and it locks in. |
| [test_red_light_card.py](tests/e2e/test_red_light_card.py) | Lights white/red with card in the card colour (issue #115): white / blue + reason / yellow without reason → display and every judge's results show white, red, red with blue and yellow cards, none under white, reason only under the blue card; the lights do not move between idle and result. "Show reasons on display" off → red card still shown, no reason text. Display reload shows the same lights, card and reason; a lift voted while the display's network is cut (switch from [network_switch.py](tests/e2e/network_switch.py)) appears with its cards after reconnect. Vote buttons keep four colours. At zoom 1.5 (restored after a reload) on 1920×1080, 1366×768 and 1280×720, timer and verdict stay on screen while waiting and with a result, and the lights do not move (waits for the lights' 0.3 s size transition after each resize via `document.getAnimations()`). |
| [test_reason_centering.py](tests/e2e/test_reason_centering.py) | Reason layout under the lights (issue #114): measures every light/reason pair — text centre under the light centre (±1.5 px), no overflow of its box, no mid-word break, no soft-hyphen break of a word that fits unhyphenated, box within half the gap to the neighbour and inside the row/screen, lights do not move when reasons appear. One real vote round (bench, German, longest words) on a 1920×1080 display and in the judges' results panel; plus a sweep of every reason (de + en, all lifts) injected via the stores — display at 1920×1080, 1280×720 and zoom 1.5, judge results on 320, 375 and 412 px phones — a long German word that breaks anywhere but at a soft hyphen in `de.json` fails here. |
| [test_scroll_indicator.py](tests/e2e/test_scroll_indicator.py) | `.has-overflow-bottom` class appears for bench-yellow (12 reasons), absent for bench-red (2 reasons). The head judge picks "Bench" in the settings select. |
| [test_demo_guide.py](tests/e2e/test_demo_guide.py) | Demo guide wording (issue #95): German → "Why Iron Verdict?" terms are German ("Athlet:innen", …), the rulebook link opens `bvdk.de/regelwerk` in a new tab (`noopener noreferrer`), date "1. März 2026"; back to landing, English → English terms, link to the IPF technical rules page. |
| [test_demo_popups.py](tests/e2e/test_demo_popups.py) | Demo launch with blocked pop-ups (issue #96), `window.open` replaced by an init script (no real pop-ups): all four open → "Demo running", no hint; from the second call `null` → hint names both ways out (allow pop-ups / click "DEMO"), relaunch with all open shows "Demo running"; all `null` (German) → only "allow pop-ups"; a window returned already `closed` counts as blocked. Demo windows (`?code=…&demo=left_judge` / `display`) show a clickable "DEMO" instead of code/name, also after a reload; it leads to role-select (real code shown), and after a reload there another role shows "DEMO" again; a regular judge still shows the code. |
| [test_privacy.py](tests/e2e/test_privacy.py) | "Privacy & Legal Notice" footer link → privacy and legal notice screen (DE/EN headings, address, `mailto:` link) → Back returns to landing. |
| [test_role_taken_over.py](tests/e2e/test_role_taken_over.py) | Position taken by another device: device A (network switch) goes offline, device B takes "Left". A — after a reload, and on its live judge screen without reload — shows role-select with the notice after the 25 s give-up limit (follows the language toggle, no popup, token dropped, no further connection attempts) while B stays connected and votes. Counter-case: B leaves within the limit and A rejoins silently. The give-up tests wait the real 25 s. |
| [test_rate_limit_client_ip.py](tests/e2e/test_rate_limit_client_ip.py) | Rate limits per client IP (issue #124): a context with one `CF-Connecting-IP` uses up the 30/minute session lookup and gets 429; a judge with another `CF-Connecting-IP` still joins, reloads back to the judge screen and gets a vote confirmed. Not `remote_safe` (needs the default limits and `limiter.reset()`). |
| [test_reload_reconnecting.py](tests/e2e/test_reload_reconnecting.py) | Reload recovery: an init script records every screen root (`data-testid="<screen>-screen"`) that becomes visible (MutationObserver plus one sample per `requestAnimationFrame`); judge, display and role-select reloads never show the landing screen; a display connected to the fake VPortal reloads without the landing screen or the VPortal dialog and its lifter overlay refills (polling restarts). Reload while the network is cut (switch from [network_switch.py](tests/e2e/network_switch.py)) stays on "Connecting…" with the session code across several failed attempts, then reaches the judge screen when the network returns; Cancel goes to landing and clears `iv_session`, also when a role-select session lookup (held with `page.route`) only answers after Cancel; reopening the app after the session ended shows landing with an inline message, no popup. |
| [test_back_navigation.py](tests/e2e/test_back_navigation.py) | Clickable display-screen session name returns to role-select; browser back navigates judge/display → role-select → landing; two-step `history.go(-2)` jump from judge tears down the WebSocket; QR-entry → back returns to landing; reload-recovery rejoin → back returns to role-select (second back → landing); reloading on role-select or after returning to it stays on role-select. |
| [test_vportal_store.py](tests/e2e/test_vportal_store.py) | VPortal state shared across screens: after the display, browser back to role-select still shows "Connected to BVDK · Platform 1", the dialog reopens on the connected step and disconnect resets the button; a display whose WebSocket is cut (switch from [network_switch.py](tests/e2e/network_switch.py)) keeps the lifter overlay while reconnecting, recovers, and refills it after a reload; a display reloaded while the session lookup fails (`page.route` abort) shows the banner and fills the overlay once the lookup works, without another reload; after two display → role-select → display round trips no polling runs on role-select and exactly one poller runs on the display (poll ticks counted over a fixed window — the test measures a rate, so it waits). |
| [test_vportal_integration.py](tests/e2e/test_vportal_integration.py) | Full VPortal flow against the `fake_vportal_url` fixture: connect modal (federation → credentials → stage), display overlay populates from polling, token-expiry mid-session hides overlay and shows banner, three consecutive upstream failures show banner, empty active group hides overlay without banner, login failures name their cause in the dialog (VPortal host refusing connections; fake `unreachable` → no session cookie), a failed stage list after login (`/api/vportal/graphql` fulfilled with 502 via `page.route`) shows an error on the stage step instead of loading forever and after disconnect → reconnect shows no stale stages from the first connect, session-driven visibility (device that joined via plain `/` still sees the connect button when the underlying session is `kind=vportal`). |
| [test_display_sizing.py](tests/e2e/test_display_sizing.py) | Display screen settings panel: gear/`S` key open, slider updates `--display-zoom`, reset returns to 1.0×, zoom persists across reload via `localStorage`, dismiss via Escape and click-outside. |
| [test_display_contrast.py](tests/e2e/test_display_contrast.py) | Display contrast mode (issue #105): off by default with today's colours; switch on → reload → still on, red light with card and reason and the verdict shown as usual; on → off stays off after reload; with contrast on every display text (session name, timer running and expired, waiting text, reasons, Good/No Lift) and the VPortal corners (fake VPortal) reach ≥ 7:1, computed from the rendered colours; mode survives a cut and restored display connection (switch from [network_switch.py](tests/e2e/network_switch.py)) and the next lift's lights arrive. |

## Regression gate

`test_competition_flow.py` is the primary cross-feature breakage gate. It must exercise the full happy-path lifecycle: create → judges join → vote → display updates → next attempt → end session. Update it when new features change the main flow; feature-specific behaviour goes in its own file alongside.

## Known flakiness risks

Three E2E tests have latent timing/race risks documented in [docs/e2e-known-risks.md](docs/e2e-known-risks.md). They pass today but should be re-checked with `pytest-repeat --count=10` when nearby code is modified:

- `test_timer_flow` — timer assertion race.
- `test_cannot_join_taken_role` — role rejection + auto-reconnect.
- `test_display_reconnects_after_refresh` — display orphan connections.

`test_timer_flow` is also `remote_safe`: against staging, network latency to Railway adds to its timer race. A staging failure there is checked against this risk first. "Re-run failed jobs" on the staging job is meant for Railway outages, not for retrying a flaky test.

## Frontend

Frontend coverage comes from two sources: Vitest unit tests for plain JS modules (`timer.js`, `i18n.js`, the reason catalog in `constants.js` against both locale files, `voteLight.js`, `voteDelivery.js` with the judge store, `vportalErrors.js`, `vportalStore.js`, `sessionStore.js`, `connection.js` with real nav/judge/display/timer/settings stores, the watchdog, retry schedule and reconnect triggers in `websocket.js`), and the Playwright E2E suite for observable browser behaviour. Stores and the connection are tested as plain objects with injected fakes; the screen components (`js/screens/`) have no dedicated unit tests and are covered only through E2E.

**What E2E tests cover:**

| Behaviour | Test file |
|---|---|
| Vote flow — color select, reason step, lock-in | `test_competition_flow.py`, `test_double_vote_prevention.py` |
| Judge reconnection — refresh before/after vote | `test_judge_reconnection.py` |
| Vote delivery — sending/confirmed states, offline vote, reload, rejection | `test_vote_delivery.py` |
| Display — orbs, verdict, timer | `test_competition_flow.py`, `test_display_resilience.py` |
| Connectivity indicators (L/R dots) | `test_connectivity_indicators.py` |
| Reconnect speed — capped retry wait, `online` trigger | `test_fast_reconnect.py` |
| Half-open connection detected by the heartbeat watchdog | `test_heartbeat_watchdog.py` |
| No orphaned server registration after a second join / connection loss | `test_orphaned_connections.py` |
| Reason list scroll overflow indicator | `test_scroll_indicator.py` |
| Reason catalog wording per lift type (judge list + display, German and English) | `test_reason_catalog.py` |
| Reasons centred under the lights, long words (display + judge results) | `test_reason_centering.py` |
| White/red lights with card colour below, lights do not move (display + judge results, reload, reconnect) | `test_red_light_card.py` |
| Display settings — zoom, contrast mode (reload, reconnect, WCAG AAA contrast) | `test_display_sizing.py`, `test_display_contrast.py` |
| Session end, role protection | `test_end_session.py`, `test_role_protection.py` |
| requireReasons lock-block + white-vote bypass | `test_require_reasons.py` |
| Language switching + localStorage persistence | `test_language_switching.py` |
| Demo guide — translated terms, rulebook link per language | `test_demo_guide.py` |
| Session-code validation on landing | `test_join_invalid_code.py` |
| Back navigation — display name click, browser back button | `test_back_navigation.py` |
| Boot state — loading indicator, no flash of screens/modal, load-failure fallback | `test_boot_loading.py` |
| New static files after a deploy despite a warm browser cache | `test_static_cache.py` |
| Reload recovery — "Connecting…" state, no landing flash, Cancel, ended session | `test_reload_reconnecting.py` |
| Position taken by another device while offline — give-up notice, short race stays silent | `test_role_taken_over.py` |

## JS unit tests

Run with `npm test` (Vitest). Independent from pytest — both run in parallel in CI.

| File | Purpose |
|---|---|
| [tests/js/timer.test.js](tests/js/timer.test.js) | `startTimerCountdown`: tick values, expiry, auto-stop, `stopTimer`, second-call cancellation. |
| [tests/js/voteDelivery.test.js](tests/js/voteDelivery.test.js) | Pending-vote storage (session/role scoping, corrupt data), `reconcileVote` decisions, `vote_lock` message, rejection-code → i18n key mapping, the vote-delivery methods of the judge store, the in-memory fallback when `sessionStorage` writes fail, and `handleResetForNextLift` while a vote is still sending. |
| [tests/js/roleTakeover.test.js](tests/js/roleTakeover.test.js) | Role-taken tracker with an injected clock: give up exactly at the 25 s limit since the first rejection, new streak after reset; notice text per position (multi-line label on one line). |
| [tests/js/websocket.test.js](tests/js/websocket.test.js) | Heartbeat watchdog in `createWebSocket` with fake timers and a fake `WebSocket`: reconnect after 15 s of silence, no reconnect while pings or other messages arrive, late events from the abandoned socket ignored, new socket watched, timer pause (background tab) restarts the count, no watchdog after `close()` or while not open. Retry schedule: base waits 0.5/1/2/3 s and ±20 % jitter bounds, measured waits between failed attempts, reset after open. Reconnect triggers: `online`, `visibilitychange` (visible only) and `pageshow` (persisted only) cancel a pending retry and connect at once; open sockets and attempts in progress are left alone; a socket closed without close event (bfcache) is replaced once; no reaction after `close()`, listeners removed on `close()`. |
| [tests/js/vportalErrors.test.js](tests/js/vportalErrors.test.js) | VPortal login error → message: 401, each 424 reason (token-exchange status inserted), unknown reason and non-JSON body fall back to the generic message with HTTP status, `fetch` failure → no connection to the server. |
| [tests/js/sessionStore.test.js](tests/js/sessionStore.test.js) | Session store defaults (no session, no role, disconnected, no judge connected, empty landing form) and that each store gets its own judge-connectivity object. |
| [tests/js/connection.test.js](tests/js/connection.test.js) | `createConnection` with real stores, a fake socket factory and history: join sends `join` with the stored reconnect token on open, VPortal display overlay starts only for the display; every way out (role-select, landing, `session_ended`, final `join_error`, back button) stops the overlay and closes the socket; messages reach the right stores (`show_results`, `reset_for_next_lift`, `settings_update`, `ping`), an unknown type is logged; session lookup found / 404; reload recovery rejoins behind *reconnecting* and replaces the history entry. |
| [tests/js/vportalStore.test.js](tests/js/vportalStore.test.js) | VPortal store with a mocked `vportalClient` and `fetch`: dialog opens on the federation or connected step, login uses the federation's host (or `window._testVportalHost`) and preselects the first stage, a login failure shows its error on the credentials step (stage-list failure: E2E in `test_vportal_integration.py`), stale stages cleared before a new login, confirm stage / disconnect, staging flag from the session lookup, display overlay polls only for `kind=vportal` with a stored stage, stale ticks keep the lifter, errors show the banner and the next attempt clears it; a failed session lookup is retried at the polling interval with the banner shown (only with a stored VPortal login), leaving the display stops poller and retry (also while a lookup is in flight), and a restart stops the previous poller. |
| [tests/js/reasonCatalog.test.js](tests/js/reasonCatalog.test.js) | Every reason key in `CARD_REASONS` has a text in `en.json` and `de.json` (a missing key would be shown raw on the display); bench yellow lists buttocks, head/shoulders and hand movement in rulebook order. |
| [tests/js/voteLight.test.js](tests/js/voteLight.test.js) | Vote → light colour (white stays white, red/blue/yellow become red) and card colour (none for white or no vote). |
| [tests/js/i18n.test.js](tests/js/i18n.test.js) | `t()` key resolution and fallback; `resolveLanguage` priority (localStorage → navigator → default); `setLanguage` persistence; `getSupportedLanguages`. |

**What is not tested:**

| Area | Gap |
|---|---|
| `websocket.js` | Backoff algorithm and reconnect-token handling untested at unit level. E2E tests exercise the outcome, not the mechanism. |
| Demo mode | Pop-up opening not Playwright-testable; demo flow untested. |
| Contact form | Third-party (web3forms) — would need mocking. |
| QR code generation | DOM side-effect; not tested. |
