# Testing

Three tiers, kept honest by tooling boundaries:

- **Backend unit** — modules tested in isolation. No FastAPI involved.
- **Backend integration** — drives the FastAPI app through ASGI (`TestClient` for HTTP, `httpx_ws.aconnect_ws` for WebSocket).
- **End-to-end** — real Uvicorn on a random port; Playwright drives the browser against the real DOM.

## How to run

```
pytest tests/ --ignore=tests/e2e   # backend unit + integration
pytest tests/e2e/                  # E2E
pytest                             # everything
pytest --tb=short -v               # readable pass/fail
```

## Conventions

- `pyproject.toml` sets `asyncio_mode = "auto"` — every `async def test_*` is automatically run as an asyncio test. No `@pytest.mark.asyncio` decorator needed.
- Backend tests rely on descriptive function names (no docstrings).
- E2E tests get a docstring — multi-step flows aren't obvious from the name alone.
- `pythonpath = ["src"]` is set in `pyproject.toml`.
- [tests/conftest.py](tests/conftest.py) reorders collection so every backend test runs before any E2E test. **Why:** pytest-playwright's session-scoped fixture creates an asyncio loop on the main thread and leaves it running for the rest of the session; once that happens, pytest-asyncio's per-test `Runner.run()` refuses to start with "cannot be called from a running event loop". Backend-first ordering keeps Playwright's loop out of the way so a single `pytest` invocation runs both suites cleanly. [tests/test_collection_ordering.py](tests/test_collection_ordering.py) guards the ordering.

## Backend tests

| File | Purpose |
|---|---|
| [tests/test_session.py](tests/test_session.py) | `SessionManager` unit. Code generation, create/join, vote-lock state machine, IPF rule (disconnected non-voter blocks results), timer-freeze math, settings, reconnect-token lifecycle. |
| [tests/test_connection.py](tests/test_connection.py) | `ConnectionManager` unit with mocked WebSockets. Add/remove/get, broadcast variants, error-swallowing on send failure, heartbeat plumbing (`mark_pong`, `_last_pong`). |
| [tests/test_logging_config.py](tests/test_logging_config.py) | `JsonFormatter` produces valid JSON with `level`/`message`/`timestamp` and merges arbitrary record extras. |
| [tests/test_http.py](tests/test_http.py) | Integration — HTTP surface: session creation (validation, rate limit), session lookup (exists / not found / malformed-format rejection / 404 log event), `/health`, security headers, and the `session_created` log event. |
| [tests/test_websocket.py](tests/test_websocket.py) | Integration — WebSocket protocol: join, vote lock (color, reason, mandatory-reason gate), settings broadcast, timer, origin check, flood disconnect, reconnect tokens, `judge_status_update`, pong heartbeat, display cap, and `caplog` assertions on every major WS log event. |
| [tests/test_collection_ordering.py](tests/test_collection_ordering.py) | Regression — asserts the collection hook in `tests/conftest.py` keeps every backend test ordered before any E2E test, so bare `pytest` keeps working. |

## End-to-end tests

[tests/e2e/conftest.py](tests/e2e/conftest.py) provides:

- `server_url` (session-scoped) — starts Uvicorn on a random port, yields the URL, shuts down at session exit.
- `_reset_server_state` (autouse) — clears sessions, connections, and rate limiter between tests.
- `competition` — yields a `CompetitionHelper` that encapsulates session creation, role joining, voting, and browser-context cleanup.

| File | Scenario |
|---|---|
| [test_smoke.py](tests/e2e/test_smoke.py) | Landing renders; "Create New Session" reaches the role select. Sentinel that the Uvicorn fixture is healthy. |
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
| [test_back_navigation.py](tests/e2e/test_back_navigation.py) | Clickable display-screen session name returns to role-select; browser back navigates judge/display → role-select → landing; two-step `history.go(-2)` jump from judge tears down the WebSocket; QR-entry and reload-recovery paths both end at landing on back. |

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
