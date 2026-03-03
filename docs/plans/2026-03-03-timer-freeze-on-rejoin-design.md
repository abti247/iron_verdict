# Design: Timer freeze on rejoin after all votes locked

## Problem

When all 3 judges lock in votes, `show_results` is broadcast and each client calls `stopTimer()` locally. However, `timer_started_at` on the server is never cleared. If a judge navigates away and rejoins, the server calculates a non-zero `time_remaining_ms` from the still-running server timestamp and the client restarts the countdown.

Expected behavior: the rejoining judge sees the frozen timer, their locked vote, and the results panel — the same state as before leaving.

## Approach

Add explicit session phase tracking on the server. When all votes lock in, store the frozen timer value and mark the session as in `"results"` phase. On rejoin, the server detects the phase and replays `show_results` to that specific connection.

## Server state (session.py)

Two new fields per session:

```python
"phase": "voting",       # "voting" | "results"
"timer_frozen_ms": None  # int | None — ms remaining when votes locked
```

**When all votes lock in** (`lock_vote()`):
- Compute `timer_frozen_ms = max(0, 60000 - elapsed * 1000)` if `timer_started_at` is set, else `None`
- Set `phase = "results"`
- Clear `timer_started_at = None`

**On `timer_reset`** and **on `reset_for_next_lift`**:
- Reset `phase = "voting"`
- Reset `timer_frozen_ms = None`

## Message flow on rejoin (main.py)

After sending `join_success` to the rejoining judge, check session `phase`. If `"results"`, immediately send a targeted `show_results` message to that one connection — same format as the broadcast, plus `timer_frozen_ms`.

No new message types needed.

## Client changes (handlers.js, timer.js)

`handleShowResults` currently calls `stopTimer()` but does not set a display value. For a rejoining judge the countdown never started, so the display would show the default (60s).

- Add `timer_frozen_ms` to `show_results` payload (sent by server)
- `handleShowResults` reads `timer_frozen_ms` and calls a new `setTimerDisplay(seconds)` helper
- Add `setTimerDisplay(seconds)` to timer.js — sets the display element value without starting a countdown

## E2E test

New test covering the rejoin scenario:

1. 3 judges join, head judge starts timer
2. All 3 judges lock votes → results appear, timer freezes
3. Left judge clicks session code → returns to role selection screen
4. Left judge rejoins as left judge
5. Assert: timer display is not counting down, vote is still shown as locked, results panel is visible
