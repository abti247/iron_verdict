# Timer Freeze on Rejoin — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When all 3 judges lock votes, freeze the timer on the server so that any judge who leaves and rejoins sees the frozen timer, their locked vote, and the results panel — exactly as before they left.

**Architecture:** Add `phase` ("voting"|"results") and `timer_frozen_ms` to session state. When all votes lock in, store the frozen ms and clear `timer_started_at`. On rejoin, the server detects phase="results" and sends a targeted `show_results` message (same format, plus `timer_frozen_ms`) to the specific reconnecting client. The client sets the timer display to the frozen value when it receives `show_results`.

**Tech Stack:** Python/FastAPI/WebSockets (backend), Alpine.js (frontend), Playwright/pytest (E2E tests), pytest-asyncio (unit tests)

---

### Task 1: Add phase and timer_frozen_ms to session state

**Files:**
- Modify: `tests/test_session.py`
- Modify: `src/iron_verdict/session.py`

**Step 1: Write failing unit tests**

Append to `tests/test_session.py`:

```python
async def test_lock_vote_sets_phase_results_when_all_locked():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    result = await manager.lock_vote(code, "right", "white")

    assert result["all_locked"] is True
    assert manager.sessions[code]["phase"] == "results"


async def test_lock_vote_computes_timer_frozen_ms_when_timer_running():
    import time
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")
    manager.sessions[code]["timer_started_at"] = time.time() - 10  # 10s elapsed

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    frozen = manager.sessions[code]["timer_frozen_ms"]
    assert frozen is not None
    assert 49000 < frozen < 51000  # ~50s remaining
    assert manager.sessions[code]["timer_started_at"] is None


async def test_lock_vote_timer_frozen_ms_none_when_no_timer():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")
    # timer_started_at remains None

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    assert manager.sessions[code]["timer_frozen_ms"] is None


async def test_reset_for_next_lift_clears_phase_and_frozen_ms():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    await manager.reset_for_next_lift(code)

    assert manager.sessions[code]["phase"] == "voting"
    assert manager.sessions[code]["timer_frozen_ms"] is None


async def test_create_session_has_voting_phase():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["phase"] == "voting"
    assert manager.sessions[code]["timer_frozen_ms"] is None
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_session.py::test_lock_vote_sets_phase_results_when_all_locked tests/test_session.py::test_lock_vote_computes_timer_frozen_ms_when_timer_running tests/test_session.py::test_lock_vote_timer_frozen_ms_none_when_no_timer tests/test_session.py::test_reset_for_next_lift_clears_phase_and_frozen_ms tests/test_session.py::test_create_session_has_voting_phase -v
```

Expected: FAIL with `KeyError: 'phase'` or similar.

**Step 3: Implement session.py changes**

In `create_session()`, add two fields after `"timer_started_at": None` (line 61):

```python
"timer_started_at": None,
"phase": "voting",
"timer_frozen_ms": None,
```

In `lock_vote()`, replace lines 147–150:

```python
            if all_locked:
                session["state"] = "showing_results"
                session["phase"] = "results"
                if session["timer_started_at"] is not None:
                    elapsed_ms = (time.time() - session["timer_started_at"]) * 1000
                    session["timer_frozen_ms"] = max(0, 60000 - elapsed_ms)
                session["timer_started_at"] = None

            return {"success": True, "all_locked": all_locked}
```

In `reset_for_next_lift()`, add two lines after `session["timer_started_at"] = None` (line 166):

```python
            session["timer_started_at"] = None
            session["phase"] = "voting"
            session["timer_frozen_ms"] = None
```

**Step 4: Run tests to verify they pass**

```
pytest tests/test_session.py::test_lock_vote_sets_phase_results_when_all_locked tests/test_session.py::test_lock_vote_computes_timer_frozen_ms_when_timer_running tests/test_session.py::test_lock_vote_timer_frozen_ms_none_when_no_timer tests/test_session.py::test_reset_for_next_lift_clears_phase_and_frozen_ms tests/test_session.py::test_create_session_has_voting_phase -v
```

Expected: PASS for all 5.

**Step 5: Run the full test suite to check for regressions**

```
pytest tests/ -v --ignore=tests/e2e
```

Expected: all pass.

**Step 6: Commit**

```bash
git add tests/test_session.py src/iron_verdict/session.py
git commit -m "feat: track session phase and frozen timer ms when all votes lock in"
```

---

### Task 2: Write the E2E test (red phase)

**Files:**
- Modify: `tests/e2e/test_judge_reconnection.py`

**Step 1: Append failing test**

```python
def test_timer_frozen_after_all_votes_locked_and_rejoin(competition):
    """After all votes lock (timer running), a judge who leaves and rejoins sees
    the frozen timer, their locked vote, and the results — no countdown resumes."""
    head, left, right = competition.join_all_judges()

    head.get_by_role("button", name="Start Timer").click()
    # Wait for timer to start ticking (it won't show "60" anymore)
    from playwright.sync_api import expect
    expect(head.locator(".judge-timer")).not_to_have_text("60")

    competition.vote_all_white()

    # Results should be visible on left judge's screen
    expect(left.locator(".head-section").last).to_be_visible()

    # Capture the frozen timer value on left's screen
    frozen_display = left.locator(".judge-timer").text_content()
    assert frozen_display != "60", "Expected timer to have ticked before votes locked"

    # Left judge navigates back to role selection
    left.locator(".code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    # Left judge rejoins
    left.locator(".role-btn", has_text="Left").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    # Timer must not be counting down: wait 1.5s and verify it hasn't changed
    import time as _time
    timer_val_before = left.locator(".judge-timer").text_content()
    _time.sleep(1.5)
    timer_val_after = left.locator(".judge-timer").text_content()
    assert timer_val_before == timer_val_after, (
        f"Timer should be frozen but changed from {timer_val_before} to {timer_val_after}"
    )

    # Vote must still be locked
    expect(left.locator(".locked-status")).to_be_visible()

    # Results must be visible
    expect(left.locator(".head-section").last).to_be_visible()
```

**Step 2: Run to verify it fails**

```
pytest tests/e2e/test_judge_reconnection.py::test_timer_frozen_after_all_votes_locked_and_rejoin -v
```

Expected: FAIL — after rejoin, the timer will be counting down (timer restarts or shows wrong value).

---

### Task 3: Update main.py — include timer_frozen_ms in show_results broadcast and send targeted show_results on rejoin

**Files:**
- Modify: `src/iron_verdict/main.py`

**Step 1: Add timer_frozen_ms to the all-locked show_results broadcast**

Locate the `show_results` broadcast in the `vote_lock` handler (around lines 373–382). Add `timer_frozen_ms` to the payload:

```python
                        await connection_manager.broadcast_to_session(
                            session_code,
                            {
                                "type": "show_results",
                                "votes": votes,
                                "reasons": reasons,
                                "showExplanations": session_settings["show_explanations"],
                                "liftType": session_settings["lift_type"],
                                "timer_frozen_ms": session_manager.sessions[session_code].get("timer_frozen_ms"),
                            }
                        )
```

**Step 2: Add targeted show_results send after join_success**

After the `await websocket.send_json({"type": "join_success", ...})` block (around line 304), add:

```python
                # If session is in results phase, replay show_results to the rejoining client
                rejoined_session = session_manager.sessions.get(session_code)
                if rejoined_session and rejoined_session.get("phase") == "results":
                    r_judges = rejoined_session["judges"]
                    r_votes = {
                        pos: j["current_vote"]
                        for pos, j in r_judges.items()
                        if j["connected"]
                    }
                    r_reasons = {
                        pos: j["current_reason"]
                        for pos, j in r_judges.items()
                        if j["connected"]
                    }
                    r_settings = rejoined_session["settings"]
                    await websocket.send_json({
                        "type": "show_results",
                        "votes": r_votes,
                        "reasons": r_reasons,
                        "showExplanations": r_settings["show_explanations"],
                        "liftType": r_settings["lift_type"],
                        "timer_frozen_ms": rejoined_session.get("timer_frozen_ms"),
                    })
```

Place this block between the `join_success` send and the `judge_status_update` broadcast. The full sequence should be: join_success → (optional) show_results → judge_status_update.

**Step 3: Run the full non-E2E test suite**

```
pytest tests/ -v --ignore=tests/e2e
```

Expected: all pass.

---

### Task 4: Update handlers.js — set frozen timer display in handleShowResults

**Files:**
- Modify: `src/iron_verdict/static/js/handlers.js`

**Step 1: Update handleShowResults**

In `handleShowResults` (line 67), after the `stopTimer()` call (line 69), add:

```javascript
    if (message.timer_frozen_ms != null) {
        app.timerDisplay = String(Math.ceil(message.timer_frozen_ms / 1000));
    }
```

The full function becomes:

```javascript
export function handleShowResults(app, message) {
    app.resultsShown = true;
    stopTimer();
    if (message.timer_frozen_ms != null) {
        app.timerDisplay = String(Math.ceil(message.timer_frozen_ms / 1000));
    }
    app.judgeResultVotes = message.votes;
    app.judgeResultReasons = message.reasons || { left: null, center: null, right: null };
    if (app.role === 'display') {
        clearTimeout(app._phaseTimer1);
        app.displayVotes = app.judgeResultVotes;
        app.displayReasons = app.judgeResultReasons;
        app.displayShowExplanations = message.showExplanations;
        app.displayLiftType = message.liftType;
        app.displayPhase = 'votes';
        app.displayStatus = '';
    }
}
```

**Step 2: Run the E2E test**

```
pytest tests/e2e/test_judge_reconnection.py::test_timer_frozen_after_all_votes_locked_and_rejoin -v
```

Expected: PASS.

**Step 3: Run full E2E suite**

```
pytest tests/e2e/ -v
```

Expected: all pass.

**Step 4: Commit**

```bash
git add src/iron_verdict/main.py src/iron_verdict/static/js/handlers.js tests/e2e/test_judge_reconnection.py
git commit -m "fix: freeze timer on server when all votes lock, replay results to rejoining judges"
```

---

### Task 5: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

Add under `[Unreleased] > Fixed`:

```
- Timer no longer resumes for a judge who leaves and rejoins after all votes are locked — the frozen timer value, locked vote, and results are fully restored on rejoin
```

**Commit**

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for timer freeze fix"
```
