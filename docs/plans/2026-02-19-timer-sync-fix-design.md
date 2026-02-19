# Timer Sync Fix Design

**Date:** 2026-02-19

## Problem

Two bugs, same root cause (server broadcasts absolute Unix timestamp; client computes elapsed time by subtracting `Date.now()` — breaks when server and client clocks differ):

1. **Clock skew on start:** Phone's clock was ~47s behind the server's clock, so `elapsed` was negative, making `remaining = 60000 - (-47000) = 107000ms` → display showed 107.
2. **Late joiners see 60:** Server never tracked timer state, so joining mid-timer gave clients a stale `timerDisplay = 60` with no running countdown.

## Design

Replace absolute `server_timestamp` with server-computed `time_remaining_ms`. Client counts down from that value using its own local clock — no cross-device clock comparison.

### `session.py`

Add `timer_started_at: None` to the initial session state dict.

### `main.py`

- **`timer_start` handler:** Set `session["timer_started_at"] = time.time()`. Broadcast `{"type": "timer_start", "time_remaining_ms": 60000}`.
- **`timer_reset` handler:** Set `session["timer_started_at"] = None`. Broadcast unchanged.
- **`join` handler:** Before sending `join_success`, compute `time_remaining_ms` from `timer_started_at` and inject into the `session_state` dict:
  ```python
  if session_state.get("timer_started_at"):
      elapsed_ms = (time.time() - session_state["timer_started_at"]) * 1000
      session_state["time_remaining_ms"] = max(0, 60000 - elapsed_ms)
  else:
      session_state["time_remaining_ms"] = None
  ```

### `index.html`

- **`startTimerCountdown(timeRemainingMs)`:** Accept milliseconds directly. Start `setInterval` that decrements from `timeRemainingMs` using local `Date.now()` delta. Remove `serverTimestamp * 1000` math.
- **`timer_start` handler:** Call `startTimerCountdown(message.time_remaining_ms)`.
- **`join_success` handler:** If `session_state.time_remaining_ms > 0`, call `startTimerCountdown(session_state.time_remaining_ms)`.

## Trade-offs

- Clients may be off by up to ~network latency ms (~50ms max) relative to each other — imperceptible on a 60s timer.
- `timer_started_at` is exposed in `session_state` sent to clients. Acceptable (it's just a float timestamp, not sensitive).
