# Fix: Double Vote After Page Reload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent a judge from voting twice after a page reload wipes their locked-in vote from the client UI.

**Architecture:** Two-layer fix. Server: reject `vote_lock` if the judge is already locked. Client: restore `voteLocked`/`selectedVote` from `session_state` in `handleJoinSuccess` so the judge sees the correct locked UI on reconnect.

**Tech Stack:** Python/FastAPI (pytest), vanilla JS/Alpine.js (manual verification)

---

### Context

Chrome's back/forward cache is blocked by open WebSocket connections, so navigation triggers a **full page reload** — not a bfcache restore. On reload, Alpine initialises with `voteLocked: false`. `handleJoinSuccess` receives the server's session state (which correctly has `locked: true` for the judge) but ignores those fields. The judge's UI shows the default unvoted screen, so they can vote again. The server has no guard and silently overwrites the original vote.

---

### Task 1: Server guard — reject duplicate `vote_lock`

**Files:**
- Modify: `src/iron_verdict/session.py:110-143`
- Test: `tests/test_session.py`

**Step 1: Write the failing test**

Add at the end of `tests/test_session.py`:

```python
async def test_lock_vote_rejects_already_locked_judge():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")

    await manager.lock_vote(code, "left", "blue")
    result = await manager.lock_vote(code, "left", "red")  # second attempt

    assert result["success"] is False
    assert "already locked" in result["error"].lower()
    # original vote must not be overwritten
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "blue"
```

**Step 2: Run test to verify it fails**

```
cd .worktrees/feat/judge-reconnect
pytest tests/test_session.py::test_lock_vote_rejects_already_locked_judge -v
```

Expected: FAIL — second `lock_vote` currently succeeds and overwrites the vote.

**Step 3: Implement the guard**

In `src/iron_verdict/session.py`, inside `lock_vote()`, add this check immediately after retrieving `judge` and before overwriting any fields (after line 128):

```python
if judge["locked"]:
    return {"success": False, "error": "Vote already locked"}
```

The full updated block (lines ~123–133) becomes:

```python
async with self._lock:
    if code not in self.sessions:
        return {"success": False, "error": "Session not found"}

    session = self.sessions[code]
    judge = session["judges"][position]

    if judge["locked"]:
        return {"success": False, "error": "Vote already locked"}

    judge["current_vote"] = color
    judge["current_reason"] = reason
    judge["locked"] = True
    session["last_activity"] = datetime.now()
```

**Step 4: Run test to verify it passes**

```
pytest tests/test_session.py::test_lock_vote_rejects_already_locked_judge -v
```

Expected: PASS

**Step 5: Run the full test suite to check for regressions**

```
pytest tests/test_session.py -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add tests/test_session.py src/iron_verdict/session.py
git commit -m "fix: reject duplicate vote_lock if judge already locked"
```

---

### Task 2: Client — restore locked vote state on reconnect

**Files:**
- Modify: `src/iron_verdict/static/js/handlers.js:3-38`

No automated test available (JS, no test framework). Verification is manual (see Task 3).

**Step 1: Edit `handleJoinSuccess`**

After the existing `judgeConnected` block (after line 16 in handlers.js), add:

```javascript
// Restore this judge's vote state if they were already locked before reconnecting
if (app.role && app.role.endsWith('_judge')) {
    const position = app.role.replace('_judge', '');
    const myState = judges?.[position];
    if (myState?.locked) {
        app.voteLocked = true;
        app.selectedVote = myState.current_vote;
    }
}
```

The full updated `handleJoinSuccess` function:

```javascript
export function handleJoinSuccess(app, message) {
    app.isHead = message.is_head;
    app.sessionName = message.session_state?.name || '';
    app.screen = app.role === 'display' ? 'display' : 'judge';

    // Initialize live connectivity state from session snapshot
    const judges = message.session_state?.judges;
    if (judges) {
        app.judgeConnected = {
            left: judges.left?.connected ?? false,
            center: judges.center?.connected ?? false,
            right: judges.right?.connected ?? false,
        };
    }

    // Restore this judge's vote state if they were already locked before reconnecting
    if (app.role && app.role.endsWith('_judge')) {
        const position = app.role.replace('_judge', '');
        const myState = judges?.[position];
        if (myState?.locked) {
            app.voteLocked = true;
            app.selectedVote = myState.current_vote;
        }
    }

    // Persist reconnect token for future reconnections
    if (message.reconnect_token) {
        const stored = sessionStorage.getItem('iv_session');
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                parsed.reconnect_token = message.reconnect_token;
                sessionStorage.setItem('iv_session', JSON.stringify(parsed));
            } catch (_e) {}
        }
    }

    if (app.isHead) {
        app.requireReasons = message.session_state?.settings?.require_reasons ?? false;
        app.saveSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        app.startTimerCountdown(trms);
    }
}
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/js/handlers.js
git commit -m "fix: restore judge vote lock state on reconnect"
```

---

### Task 3: Manual verification

Start the app and open two browser tabs — one as a judge, one as display.

**Scenario A — reload after voting:**
1. Join as right judge, vote blue, lock in → UI shows locked blue
2. Reload the page (F5)
3. Expected: judge screen shows blue locked in (not the default unvoted screen)

**Scenario B — double-vote attempt via DevTools:**
1. Join as right judge, vote blue, lock in
2. Open DevTools console, run:
   ```js
   // reach the ws object from Alpine
   document.querySelector('[x-data]').__x.$data.wsSend({ type: 'vote_lock', color: 'red' })
   ```
3. Expected: server returns `{"type": "error", "message": "Vote already locked"}` (check Network > WS frames) — display is unchanged

**Scenario C — back/forward navigation (the original bug):**
1. Join as right judge, vote blue, lock in
2. Navigate to another URL then press Back
3. Expected: judge screen shows blue locked in, the display is not affected

---

### Task 4: Update CHANGELOG

**File:** `CHANGELOG.md`

Add under `[Unreleased] > Fixed`:

```
- Judges who reload or navigate back after voting now see their vote correctly locked in, preventing accidental double voting
```

**Commit:**

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for double-vote fix"
```

---

## Unresolved Questions

None — root cause confirmed, scope is clear.
