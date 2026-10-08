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
- E2E tests need `cdn.jsdelivr.net` at runtime (Alpine.js and the QR library, until issue #54 ships them locally). If **every** E2E test times out waiting for the first input, check that CDN before suspecting a regression.
- A new push to a PR cancels the still-running CI of the previous push.
- CI records a trace for every browser context, which makes E2E runs slightly slower than a plain local `pytest tests/e2e/`. If a test flakes in CI but not locally, rerun it locally with `--tracing on` before blaming the code — the timing-sensitive tests in [docs/e2e-known-risks.md](docs/e2e-known-risks.md) are the first suspects.
- No automatic retries. **Why:** retries hide flaky tests; a flaky test is fixed or documented in [docs/e2e-known-risks.md](docs/e2e-known-risks.md).
- Branch protection on `main` (configured by the maintainer in the repo settings): merge only via PR, `backend`, `js`, `e2e` and `image` required, branch must be up to date. No required reviewer approval — a sole maintainer cannot approve their own PRs on GitHub.

### Image check

[.github/workflows/image.yml](.github/workflows/image.yml) (job `image`, required on PRs) builds the Docker image with Buildx (GitHub Actions layer cache, `APP_VERSION=sha-<head commit>`), starts it with a named `/data` volume and smoke-tests the **running container** from outside: `pytest tests/e2e/test_smoke.py` with `E2E_BASE_URL=http://127.0.0.1:8000`. Afterwards it stops the container and requires `/data/sessions.json` to have been written by the app — proof that the entrypoint handed the root-owned volume to `appuser`. Container logs are always printed; Playwright traces go to the `playwright-traces-image` artifact on failure. **Why:** the other jobs test the source tree; a file dropped by `.dockerignore` or package data, a broken entrypoint or wrong permissions only show up in the built image.

The [Main workflow](.github/workflows/main.yml) runs `ci.yml` and `image.yml` on every push to `main` and pushes the tested image to GHCR only when both are green; the [Release workflow](.github/workflows/release.yml) re-tags it on `v*` tags. See [docs/release.md](docs/release.md).

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

- **Network access** (Network access → Custom, keep the default package-manager list; the default list blocks both hosts):
  - `cdn.playwright.dev` — the Chromium build pre-installed on the VM rarely matches the Playwright version pip resolves; without the download E2E tests fail with "Executable doesn't exist".
  - `cdn.jsdelivr.net` — the app still loads Alpine.js and the QR library from this CDN (until issue #54 ships them locally); without it the landing page never renders and every E2E test times out waiting for the first input.
- The script runs once per environment and the result is cached for roughly seven days. After a dependency change in `pyproject.toml` or `package.json`, run `pip install -e ".[dev]"` / `npm ci` in the session (or edit the script to force a rebuild).
- If plain `pytest` reports `ModuleNotFoundError` for a project dependency, it is the VM's standalone pytest — use `python -m pytest`.

## Conventions

- `pyproject.toml` sets `asyncio_mode = "auto"` — every `async def test_*` is automatically run as an asyncio test. No `@pytest.mark.asyncio` decorator needed.
- Backend tests rely on descriptive function names (no docstrings).
- E2E tests get a docstring — multi-step flows aren't obvious from the name alone.
- `pythonpath = ["src"]` is set in `pyproject.toml`.
- [tests/conftest.py](tests/conftest.py) reorders collection so every backend test runs before any E2E test. **Why:** pytest-playwright's session-scoped fixture creates an asyncio loop on the main thread and leaves it running for the rest of the session; once that happens, pytest-asyncio's per-test `Runner.run()` refuses to start with "cannot be called from a running event loop". Backend-first ordering keeps Playwright's loop out of the way so a single `pytest` invocation runs both suites cleanly. [tests/test_collection_ordering.py](tests/test_collection_ordering.py) guards the ordering.

## Backend tests

| File | Purpose |
|---|---|
| [tests/test_session.py](tests/test_session.py) | `SessionManager` unit. Code generation, create/join, vote-lock state machine, IPF rule (disconnected non-voter blocks results), timer-freeze math, settings, reconnect-token lifecycle, `kind` field validation (`generic` / `vportal` / reject unknown). |
| [tests/test_connection.py](tests/test_connection.py) | `ConnectionManager` unit with mocked WebSockets. Add/remove/get, broadcast variants, error-swallowing on send failure, heartbeat plumbing (`mark_pong`, `_last_pong`). |
| [tests/test_logging_config.py](tests/test_logging_config.py) | `JsonFormatter` produces valid JSON with `level`/`message`/`timestamp` and merges arbitrary record extras. |
| [tests/test_config.py](tests/test_config.py) | `Settings` env-var parsing for the VPortal config surface: `VPORTAL_FETCH_INTERVAL_MS` default, honor, and clamp-to-2000 minimum; `TEST_MODE` and `EXPOSE_VPORTAL_STAGING` boolean parsing. |
| [tests/test_http.py](tests/test_http.py) | Integration — HTTP surface: session creation (validation, rate limit, `kind` accepted / rejected), session lookup (exists / not found / malformed-format rejection / 404 log event / `kind` + `staging_available` in body), `/vportal` route serves identical HTML as `/`, `/health`, security headers, and the `session_created` log event. |
| [tests/test_vportal_proxy.py](tests/test_vportal_proxy.py) | Integration — VPortal proxy: host allowlist (production + staging accepted, localhost rejected without TEST_MODE, attackers rejected), operation allowlist (known reads accepted, mutations and unknown queries rejected with 400), login endpoint forwards cookie→JWT chain and returns the server-clamped polling interval, GraphQL forwarding propagates 401 verbatim and maps 5xx to 502. Upstream simulated via `httpx.MockTransport`. |
| [tests/test_websocket.py](tests/test_websocket.py) | Integration — WebSocket protocol: join, vote lock (color, reason, mandatory-reason gate), settings broadcast, timer, origin check, flood disconnect, reconnect tokens, `judge_status_update`, pong heartbeat, display cap, and `caplog` assertions on every major WS log event. |
| [tests/test_changelog_section.py](tests/test_changelog_section.py) | `scripts/changelog_section.py` (release notes for the Release workflow): extracts a version's CHANGELOG section with its compare link, exact version match (no prefix), CRLF input, errors on missing or entry-less sections, CLI exit codes, and that the real `CHANGELOG.md` parses. |
| [tests/test_collection_ordering.py](tests/test_collection_ordering.py) | Regression — asserts the collection hook in `tests/conftest.py` keeps every backend test ordered before any E2E test, so bare `pytest` keeps working. **Known false-negative on Windows + Python 3.14:** the test spawns `pytest --collect-only` as a subprocess and hits a Windows handle-capture quirk that fails even though the ordering it audits is correct. Verifiable by running `python -m pytest --collect-only -q` manually. |

## End-to-end tests

[tests/e2e/conftest.py](tests/e2e/conftest.py) provides:

- `server_url` (session-scoped) — starts Uvicorn on a random port, yields the URL, shuts down at session exit. With `E2E_BASE_URL` set it yields that URL instead and starts nothing (external mode: the Docker image in CI, later staging).
- `_reset_server_state` (autouse) — clears sessions, connections, and rate limiter between tests. No-op in external mode.
- `competition` — yields a `CompetitionHelper` that encapsulates session creation, role joining, voting, and browser-context cleanup. `competition.new_context()` opens an extra context for manual flows; it goes through pytest-playwright's `new_context` fixture so the context is traced on failure.
- `fake_vportal_url` (session-scoped) — starts [tests/e2e/fake_vportal.py](tests/e2e/fake_vportal.py) (a tiny FastAPI app that mimics VPortal's `/account/login`, `/auth/token`, and `/graphql`) on a random port and yields `host:port`. Used by `test_vportal_integration.py`; skips in external mode (needs the in-process server's `TEST_MODE`). Sets `TEST_MODE=1` and `VPORTAL_FETCH_INTERVAL_MS=2000` at module import so the proxy accepts the fake host and polls fast enough for tests. The fake server exposes `/_control/{force_token_invalid,unreachable,clear_attempt,restore_attempt,reset}` so tests can simulate error states.

| File | Scenario |
|---|---|
| [test_smoke.py](tests/e2e/test_smoke.py) | Landing renders; "Create New Session" reaches the role select; `/health`; every static asset the app loads (followed from `/`, `/vportal` and ES-module imports) is served; app version rendered (`E2E_EXPECTED_APP_VERSION` pins it); WebSocket join as head judge; VPortal client modules load. Also the **container smoke test** (`image` job): must work in external mode, so no in-process state and only a few sessions (creation is rate-limited to 10/hour per IP). |
| [test_join_invalid_code.py](tests/e2e/test_join_invalid_code.py) | Landing-screen validation — Join button enables only at 8 chars; unknown code shows inline error and blocks navigation to role-select; typing clears the error; stale QR (`?session=...`) lands on landing with the code pre-filled and the error visible. |
| [test_competition_flow.py](tests/e2e/test_competition_flow.py) | **Regression gate.** Full lift cycle (white sweep + mixed verdict + Next Lift), required-reasons branch, timer start/reset across all four screens. |
| [test_double_vote_prevention.py](tests/e2e/test_double_vote_prevention.py) | Locked vote survives refresh; re-voting blocked; Next Lift clears the lock. |
| [test_judge_reconnection.py](tests/e2e/test_judge_reconnection.py) | Refresh before/after voting, manual role-reselect, all judges refresh simultaneously, timer-frozen-after-results-and-rejoin. |
| [test_session_stuck_states.py](tests/e2e/test_session_stuck_states.py) | Next Lift mid-vote, continue after a judge disconnects mid-vote, IPF rule via the browser, full reset of vote state. |
| [test_connectivity_indicators.py](tests/e2e/test_connectivity_indicators.py) | L/R dots on head screen update as side judges join/disconnect/reconnect; own dot transitions connected → reconnecting → connected (uses an init script to monkey-patch `WebSocket`); `server_restarting` broadcast renders the label. |
| [test_display_resilience.py](tests/e2e/test_display_resilience.py) | Display refresh recovers; mid-competition display join; two displays receive identical results. |
| [test_end_session.py](tests/e2e/test_end_session.py) | Only head sees End Session; ending redirects all four screens; ended code unjoinable. |
| [test_role_protection.py](tests/e2e/test_role_protection.py) | Taken role rejected; role freed on disconnect; role switch via session-code link; head=center invariant. |
| [test_scroll_indicator.py](tests/e2e/test_scroll_indicator.py) | `.has-overflow-bottom` class appears for bench-yellow (12 reasons), absent for bench-red (2 reasons). Reaches into Alpine via `_x_dataStack` to set `liftType`. |
| [test_privacy.py](tests/e2e/test_privacy.py) | Privacy footer link → privacy screen → Back returns to landing. |
| [test_back_navigation.py](tests/e2e/test_back_navigation.py) | Clickable display-screen session name returns to role-select; browser back navigates judge/display → role-select → landing; two-step `history.go(-2)` jump from judge tears down the WebSocket; QR-entry → back returns to landing; reload-recovery rejoin → back returns to role-select (second back → landing); reloading on role-select or after returning to it stays on role-select. |
| [test_vportal_integration.py](tests/e2e/test_vportal_integration.py) | Full VPortal flow against the `fake_vportal_url` fixture: connect modal (federation → credentials → stage), display overlay populates from polling, token-expiry mid-session hides overlay and shows banner, three consecutive upstream failures show banner, empty active group hides overlay without banner, session-driven visibility (device that joined via plain `/` still sees the connect button when the underlying session is `kind=vportal`). |
| [test_display_sizing.py](tests/e2e/test_display_sizing.py) | Display screen settings panel: gear/`S` key open, slider updates `--display-zoom`, reset returns to 1.0×, zoom persists across reload via `localStorage`, dismiss via Escape and click-outside. |

## Regression gate

`test_competition_flow.py` is the primary cross-feature breakage gate. It must exercise the full happy-path lifecycle: create → judges join → vote → display updates → next attempt → end session. Update it when new features change the main flow; feature-specific behaviour goes in its own file alongside.

## Known flakiness risks

Three E2E tests have latent timing/race risks documented in [docs/e2e-known-risks.md](docs/e2e-known-risks.md). They pass today but should be re-checked with `pytest-repeat --count=10` when nearby code is modified:

- `test_timer_flow` — timer assertion race.
- `test_cannot_join_taken_role` — role rejection + auto-reconnect.
- `test_display_reconnects_after_refresh` — display orphan connections.

## Frontend

Frontend coverage comes from two sources: Vitest unit tests for pure JS modules (`timer.js`, `i18n.js`), and the Playwright E2E suite for observable browser behaviour. Alpine components have no dedicated unit tests — they are covered only through E2E.

**What E2E tests cover:**

| Behaviour | Test file |
|---|---|
| Vote flow — color select, reason step, lock-in | `test_competition_flow.py`, `test_double_vote_prevention.py` |
| Judge reconnection — refresh before/after vote | `test_judge_reconnection.py` |
| Display — orbs, verdict, timer | `test_competition_flow.py`, `test_display_resilience.py` |
| Connectivity indicators (L/R dots) | `test_connectivity_indicators.py` |
| Reason list scroll overflow indicator | `test_scroll_indicator.py` |
| Session end, role protection | `test_end_session.py`, `test_role_protection.py` |
| requireReasons lock-block + white-vote bypass | `test_require_reasons.py` |
| Language switching + localStorage persistence | `test_language_switching.py` |
| Session-code validation on landing | `test_join_invalid_code.py` |
| Back navigation — display name click, browser back button | `test_back_navigation.py` |

## JS unit tests

Run with `npm test` (Vitest). Independent from pytest — both run in parallel in CI.

| File | Purpose |
|---|---|
| [tests/js/timer.test.js](tests/js/timer.test.js) | `startTimerCountdown`: tick values, expiry, auto-stop, `stopTimer`, second-call cancellation. |
| [tests/js/i18n.test.js](tests/js/i18n.test.js) | `t()` key resolution and fallback; `resolveLanguage` priority (localStorage → navigator → default); `setLanguage` persistence; `getSupportedLanguages`. |

**What is not tested:**

| Area | Gap |
|---|---|
| `websocket.js` | Backoff algorithm and reconnect-token handling untested at unit level. E2E tests exercise the outcome, not the mechanism. |
| Demo mode | Pop-up opening not Playwright-testable; demo flow untested. |
| Contact form | Third-party (web3forms) — would need mocking. |
| QR code generation | DOM side-effect; not tested. |
