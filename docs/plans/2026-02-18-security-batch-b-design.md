# Security Hardening Batch B — Design

**Date:** 2026-02-18
**Issues:** C2, M3, L2
**Ref:** docs/plans/2026-02-12-security-hardening-design.md

---

## C2 — Session cleanup

Add `cleanup_expired()` to `SessionManager`: calls `get_expired_sessions(SESSION_TIMEOUT_HOURS)` then `delete_session()` for each result. Synchronous; no lock needed (only targets stale sessions, can't race with fresh creates).

Add `lifespan` context manager to `main.py`. Spawns an `asyncio.Task` that loops: sleep 30 min, call `session_manager.cleanup_expired()`. Cancels task on shutdown. Replace `FastAPI(title="JudgeMe")` with `FastAPI(title="JudgeMe", lifespan=lifespan)`.

---

## M3 — Asyncio lock for SessionManager

Add `self._lock = asyncio.Lock()` to `SessionManager.__init__` (mirrors `ConnectionManager`).

Convert to `async def` and guard with `async with self._lock`:
- `create_session`
- `lock_vote`
- `reset_for_next_lift`

`delete_session` and `update_settings` remain synchronous and unlocked (per spec).

**Rationale:** making methods `async` removes the implicit atomicity guarantee of synchronous code. The lock restores it as an explicit, enforced invariant. Also closes a latent TOCTOU in `create_session` (uniqueness check → dict write) that would become exploitable if any `await` were ever added inside.

**Ripple effects:**
- `main.py`: all three call sites need `await`
- `test_main.py`: `session_code` fixture → `async def`
- `test_session.py`: tests for the three locked methods → `async def test_...`

---

## L2 — Display cap (UUID-per-display)

**ConnectionManager — new methods:**
- `count_displays(session_code) -> int`: counts active connections whose key starts with `"display_"`, under lock.
- `send_to_displays(session_code, message)`: sends to all `"display_*"` connections. Replaces the single `send_to_role(session_code, "display", ...)` call in `main.py`.

**SessionManager:** remove `session["displays"]` list. `join_session` for role `"display"` validates only (session exists, role valid) and returns `{"success": True, "is_head": False}`. Display tracking is now owned entirely by `ConnectionManager`.

**config.py:** add `DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))`.

**main.py `join` handler, display path:**
1. Call `session_manager.join_session(session_code, "display")` to validate.
2. `await connection_manager.count_displays(session_code)` — if `>= settings.DISPLAY_CAP`, send `join_error` and close.
3. `role = f"display_{secrets.token_hex(4)}"`.
4. `await connection_manager.add_connection(session_code, role, websocket)`.
5. `WebSocketDisconnect` handler already removes the right key because `role` holds the UUID-based string.

---

## Test changes

| File | Change |
|---|---|
| `test_session.py` | `async def` for `create_session`/`lock_vote`/`reset_for_next_lift` tests; update display test (remove `displays` assertion); add `cleanup_expired` test |
| `test_main.py` | `session_code` fixture → `async def`; add display-cap rejection test |

---

## No new dependencies. No schema changes.
