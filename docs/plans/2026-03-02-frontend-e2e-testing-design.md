# Frontend E2E Testing Design

## Goal

Add Playwright-based E2E tests to guard critical competition flows. During a live powerlifting competition there is zero tolerance for bugs — judges must always be able to vote, sessions must never get stuck, and connectivity indicators must be accurate.

## Approach

- **Framework:** pytest-playwright (Python) — unified with existing pytest backend tests
- **Server:** Real FastAPI server started per test run via session-scoped fixture on random port
- **Multi-user:** Multiple browser contexts per test (one per judge + display) to simulate real competition
- **Location:** `tests/e2e/` directory, discoverable by existing pytest config
- **Run:** `pytest tests/e2e/` or `pytest tests/e2e/ --headed` for visual debugging

## Dependencies

- `pytest-playwright` (pulls in `playwright` Python package)
- `playwright install chromium` for browser binary

## Infrastructure

### Server Fixture (session-scoped)
Starts uvicorn with the FastAPI app on a random available port in a background thread. Tears down after all E2E tests.

### Competition Fixture (function-scoped)
Returns a helper that creates named browser contexts (head_judge, left_judge, right_judge, display), each with their own page pointed at the server. Cleans up contexts after each test.

## Test Suites

### Suite 1: `test_competition_flow.py` — Happy Path

| Test | Description |
|------|-------------|
| `test_full_lift_cycle` | Create session → 3 judges join → all vote white → results shown → next lift → vote again with mixed colors/reasons → results correct |
| `test_lift_cycle_with_required_reasons` | Head judge enables require_reasons → judges must pick reason → reasons shown on display |
| `test_timer_flow` | Head judge starts timer → visible on all screens → reset → timer clears |

### Suite 2: `test_judge_reconnection.py` — Reconnection

| Test | Description |
|------|-------------|
| `test_reconnect_before_voting` | Judge refreshes before voting → returns to judge screen, can vote |
| `test_reconnect_after_voting` | Judge refreshes after locking vote → vote restored, cannot re-vote |
| `test_reconnect_via_role_select` | Judge clicks session code → role-select → re-selects role → state preserved |
| `test_all_judges_reconnect_simultaneously` | All 3 refresh at once → all reconnect, session continues |

### Suite 3: `test_double_vote_prevention.py` — Vote Integrity

| Test | Description |
|------|-------------|
| `test_locked_vote_persists_after_refresh` | Lock vote → refresh → vote still locked |
| `test_cannot_vote_twice` | Lock vote → attempt second vote → rejected |
| `test_vote_clears_after_next_lift` | Full cycle → next lift → all judges can vote fresh |

### Suite 4: `test_role_protection.py` — Role Safety

| Test | Description |
|------|-------------|
| `test_cannot_join_taken_role` | Role occupied → second join attempt rejected |
| `test_role_freed_on_disconnect` | Judge disconnects → role becomes available |
| `test_switch_role_via_session_code` | Judge clicks session code → picks different role → old role freed |
| `test_head_judge_is_center` | Center judge gets head judge controls; side judges don't |

### Suite 5: `test_connectivity_indicators.py` — Status Indicators

| Test | Description |
|------|-------------|
| `test_lr_dots_connected_on_join` | L/R dots start disconnected → turn green as side judges join |
| `test_lr_dots_update_on_disconnect` | Side judge disconnects → corresponding dot goes disconnected |
| `test_lr_dots_recover_on_reconnect` | Side judge reconnects → dot returns to connected |
| `test_own_dot_green_when_connected` | Judge's own `.conn-dot` has `connected` class |
| `test_own_dot_orange_on_reconnecting` | Connection drops → dot shows `reconnecting` (orange, pulsing) → reconnects → green |
| `test_server_restart_message` | Server sends `server_restarting` → "Server restarting" label visible → server returns → label hidden, dot green |

### Suite 6: `test_session_stuck_states.py` — No Stuck Sessions

| Test | Description |
|------|-------------|
| `test_next_lift_when_not_all_voted` | Only 2/3 vote → head judge clicks Next Lift → confirms → all reset |
| `test_continue_after_judge_disconnect_mid_vote` | Judge disconnects after partial voting → remaining judges can still vote, head judge can reset |
| `test_next_lift_resets_all_state` | Full cycle → Next Lift → voteLocked false, selectedVote cleared, resultsShown false |

### Suite 7: `test_display_resilience.py` — Display Stability

| Test | Description |
|------|-------------|
| `test_display_reconnects_after_refresh` | Display refreshes → reconnects, shows current state |
| `test_display_joins_mid_competition` | Display joins after votes started → shows correct state |
| `test_multiple_displays_receive_results` | Two displays → both show identical results |

### Suite 8: `test_end_session.py` — End Session

| Test | Description |
|------|-------------|
| `test_only_head_judge_can_end` | Side judges have no End Session button |
| `test_end_redirects_all_participants` | Head judge ends → all 4 contexts return to landing |
| `test_session_gone_after_end` | Session ended → join with old code fails |

## Key Implementation Details

### L/R Connectivity Dots (Head Judge)
- Alpine state: `judgeConnected.left`, `judgeConnected.right`
- CSS: `.connectivity-dot.status-connected` (green) / `.status-disconnected` (gray)
- Updated via `judge_status_update` WebSocket message

### Own Connection Dot (All Judges/Display)
- Alpine state: `connectionStatus` (`connected` | `reconnecting` | `disconnected`)
- CSS: `.conn-dot.connected` (green glow) / `.conn-dot.reconnecting` (orange pulse)
- Alpine state: `serverRestarting` (boolean) → shows "Server restarting" label

### Double-Vote Prevention
- Server-side: `locked` flag per judge, checked on `vote_lock` message
- Client-side: `voteLocked` restored from `session_state` on reconnect via `handleJoinSuccess`

## Unresolved Questions

- Server restart test (Suite 5): requires actually restarting the server mid-test. May need a special fixture that can stop/start the server. Could be complex — consider deferring to a later iteration.
