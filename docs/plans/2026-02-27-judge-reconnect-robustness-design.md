# Judge Reconnect Robustness — Design

**Date:** 2026-02-27

## Problem

A judge who disconnects mid-round (e.g. mobile browser swipe-back) can leave the session permanently stuck:

1. **"Role already taken" cascade failure** — If the judge's new connection arrives at the server before the old TCP disconnect fires, `join_session` returns "Role already taken". `handleJoinError` then calls `ws.close()` (sets `stopped=true`, killing all future auto-reconnects) and clears `sessionStorage`. The judge is left on the voting screen with a dead socket; their vote tap is silently dropped.

2. **bfcache silent death** — Mobile browsers restore pages from the back-forward cache without a full reload. The WebSocket is dead but the page looks normal. `init()` is never re-called, so no rejoin occurs.

3. **No head judge escape hatch** — "Next Lift" is gated on `resultsShown=true` in the UI. If results never show (e.g. because a judge's vote was never received), the head judge cannot advance. No override exists.

## Design

### Section 1 — Server: Connection Replacement with Reconnect Token

**Reconnect token.** On first successful `join`, the server generates a random token (`reconnect_token`, 16 hex chars) and:
- Stores it in `session["judges"][position]["reconnect_token"]`
- Includes it in the `join_success` response
- Client stores `{code, role, reconnect_token}` in `sessionStorage`

**Replacement logic** (in the `join` handler in `main.py`). When `join_session` returns "Role already taken":
- If the request includes the **matching** `reconnect_token` → close the old WebSocket, remove it from `connection_manager`, set `connected=False`, then re-run `join_session` (now succeeds)
- If no token or wrong token → send `join_error: "Role already taken"` as before

**Disconnect identity guard.** When a WebSocket is closed because it was replaced, its `except WebSocketDisconnect` handler still runs. To prevent it from overwriting the fresh connection's `connected=True`, the handler checks `connection_manager.get_connection(session_code, role)`. If the disconnecting WebSocket is no longer the registered one, it skips the `connected=False` update.

**Token lifecycle:**
- Persists for the entire session (survives `reset_for_next_lift`)
- Not included in snapshots (tokens are runtime-only; after a server restart all `connected` flags reset to `False`, so the token check is never reached)
- Invalidated only when the judge intentionally leaves (`returnToLanding` / `returnToRoleSelection` clear `sessionStorage`)

**New `ConnectionManager` method:** `get_connection(session_code, role) → WebSocket | None`

### Section 2 — Server: Judge Connectivity Status Broadcast

**No auto-resolve on disconnect.** The session continues to wait for all connected judges to vote. The head judge decides when to force-advance.

**`judge_status_update` broadcast.** Sent to all clients whenever a judge's connectivity changes:
```json
{ "type": "judge_status_update", "position": "right", "connected": false }
```
Broadcast from two places:
- Disconnect handler (after setting `connected=False`)
- `join` handler after a judge successfully joins (currently broadcasts nothing)

**Head judge UI — connectivity indicators.** A persistent status bar on the head judge screen shows a live connected/disconnected indicator for left and right judges. Center is always the head judge, so less relevant to display.

**"Next Lift" always active.** The button is available to the head judge unconditionally. If pressed before `resultsShown=true`, a confirmation dialog appears: *"Results haven't been shown yet — advance anyway?"*. Server-side `next_lift` handling is unchanged (already has no state restriction).

### Section 3 — Client: bfcache Handling & `handleJoinError` Fix

**`pageshow` listener.** Registered in `init()`. If `event.persisted=true` and the WebSocket is not open, force a re-join using the stored `sessionStorage` credentials. Covers mobile "swipe back, swipe forward" without full reload.

**`handleJoinError` — differentiate error types:**
- `"Role already taken"` → do not close ws, do not clear sessionStorage, show no alert. The server closes the socket after sending `join_error`, triggering auto-reconnect in `websocket.js`. By the time the 1s retry fires, the old disconnect has landed and the role is free.
- All other errors (`"Session not found"`, `"Display cap reached"`, etc.) → keep current behavior (close ws, clear storage, show alert).

### Section 4 — Testing

**`test_session.py`**
- `join_session` returns `reconnect_token` on first successful join
- Second join with correct token succeeds
- Second join with wrong/missing token returns "Role already taken"
- Token survives `reset_for_next_lift`
- Token not included in snapshot output

**`test_main.py`**
- New WebSocket with correct token replaces stale connection; stale disconnect does not set `connected=False`
- New WebSocket with wrong token is rejected
- `judge_status_update` broadcast on judge disconnect
- `judge_status_update` broadcast on judge join
- Head judge can send `next_lift` in `"waiting"` state (regression)

**`test_connection.py`**
- `get_connection(session_code, role)` returns registered WebSocket or `None`

## Files Affected

| File | Change |
|------|--------|
| `src/iron_verdict/session.py` | Add `reconnect_token` to judge state; generate on join; exclude from snapshot |
| `src/iron_verdict/connection.py` | Add `get_connection()` method |
| `src/iron_verdict/main.py` | Connection replacement logic in `join` handler; `judge_status_update` broadcasts; disconnect identity guard |
| `src/iron_verdict/static/js/handlers.js` | Fix `handleJoinError`; add `handleJudgeStatusUpdate` |
| `src/iron_verdict/static/js/app.js` | `pageshow` listener in `init()`; store/read `reconnect_token` in sessionStorage |
| `src/iron_verdict/static/index.html` | Connectivity status bar on head judge screen; unconditional Next Lift button |
| `tests/test_session.py` | New token tests |
| `tests/test_connection.py` | `get_connection` test |
| `tests/test_main.py` | Reconnect, broadcast, and next_lift tests |
