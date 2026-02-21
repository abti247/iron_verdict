# Judge Reason Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Judges select a specific reason after choosing a non-white color; the display screen shows that reason beneath the judge's light, replacing the old "all possible reasons" explanation phase.

**Architecture:** Four layers of change — (1) session state gets `current_reason` per judge and `require_reasons` setting, (2) `vote_lock` protocol gains an optional `reason` field with optional server-side validation, (3) `show_results` broadcast gains a `reasons` dict, (4) frontend adds a two-step voting flow and updated display. All frontend state is in `ironVerdictApp()` in the single HTML file.

**Tech Stack:** FastAPI + WebSockets (`src/iron_verdict/main.py`), session management (`src/iron_verdict/session.py`), Alpine.js 3 single-file frontend (`src/iron_verdict/static/index.html`), pytest (`tests/`)

---

### Task 1: Backend — Add `current_reason` to judge state and `lock_vote()`

**Files:**
- Modify: `src/iron_verdict/session.py`
- Test: `tests/test_session.py`

**Step 1: Write failing tests**

Add to `tests/test_session.py`:

```python
async def test_lock_vote_stores_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    result = await manager.lock_vote(code, "left", "yellow", reason="Buttocks up")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_reason"] == "Buttocks up"


async def test_lock_vote_reason_defaults_to_none():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "white")
    assert manager.sessions[code]["judges"]["left"]["current_reason"] is None


async def test_session_judges_have_current_reason_field():
    manager = SessionManager()
    code = await manager.create_session("Test")
    for judge in manager.sessions[code]["judges"].values():
        assert "current_reason" in judge
        assert judge["current_reason"] is None


async def test_reset_for_next_lift_clears_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "yellow", reason="Buttocks up")
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["judges"]["left"]["current_reason"] is None
```

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_session.py::test_lock_vote_stores_reason tests/test_session.py::test_lock_vote_reason_defaults_to_none tests/test_session.py::test_session_judges_have_current_reason_field tests/test_session.py::test_reset_for_next_lift_clears_reason -v
```

Expected: FAIL — `lock_vote` doesn't accept `reason`, judges don't have `current_reason`.

**Step 3: Implement changes in `session.py`**

In `create_session()` (lines 29–46), add `"current_reason": None` to each judge dict:

```python
"left": {
    "connected": False,
    "is_head": False,
    "current_vote": None,
    "current_reason": None,   # add this
    "locked": False,
},
# repeat for "center" and "right"
```

Update `lock_vote()` signature (line 97):

```python
async def lock_vote(self, code: str, position: str, color: str, reason: str | None = None) -> Dict[str, Any]:
```

After `judge["current_vote"] = color` (line 116), add:

```python
judge["current_reason"] = reason
```

In `reset_for_next_lift()` (lines 138–140), add inside the loop:

```python
judge["current_reason"] = None
```

**Step 4: Run to verify tests pass**

```bash
python -m pytest tests/test_session.py::test_lock_vote_stores_reason tests/test_session.py::test_lock_vote_reason_defaults_to_none tests/test_session.py::test_session_judges_have_current_reason_field tests/test_session.py::test_reset_for_next_lift_clears_reason -v
```

Expected: PASS

**Step 5: Run full suite for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add src/iron_verdict/session.py tests/test_session.py
git commit -m "feat: add current_reason to judge state and lock_vote"
```

---

### Task 2: Backend — Add `require_reasons` setting

**Files:**
- Modify: `src/iron_verdict/session.py`
- Test: `tests/test_session.py`

**Step 1: Write failing tests**

```python
async def test_session_settings_has_require_reasons():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert "require_reasons" in manager.sessions[code]["settings"]
    assert manager.sessions[code]["settings"]["require_reasons"] is False


async def test_update_settings_stores_require_reasons():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, True, "bench", require_reasons=True)
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["require_reasons"] is True
```

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_session.py::test_session_settings_has_require_reasons tests/test_session.py::test_update_settings_stores_require_reasons -v
```

**Step 3: Implement in `session.py`**

In `create_session()` settings dict (lines 51–54), add:

```python
"settings": {
    "show_explanations": False,
    "lift_type": "squat",
    "require_reasons": False,   # add this
},
```

Update `update_settings()` signature (line 148):

```python
def update_settings(self, code: str, show_explanations: bool, lift_type: str, require_reasons: bool = False) -> Dict[str, Any]:
```

After `session["settings"]["lift_type"] = lift_type` (line 156), add:

```python
session["settings"]["require_reasons"] = require_reasons
```

**Step 4: Run to verify tests pass**

```bash
python -m pytest tests/test_session.py::test_session_settings_has_require_reasons tests/test_session.py::test_update_settings_stores_require_reasons -v
```

**Step 5: Run full suite**

```bash
python -m pytest tests/ -v
```

**Step 6: Commit**

```bash
git add src/iron_verdict/session.py tests/test_session.py
git commit -m "feat: add require_reasons to session settings"
```

---

### Task 3: Backend — Update `vote_lock` handler and `show_results` broadcast

**Files:**
- Modify: `src/iron_verdict/main.py`
- Test: `tests/test_main.py`

**Step 1: Read `tests/test_main.py`** to understand the WebSocket test helper pattern before writing tests.

**Step 2: Write failing tests** (follow existing WebSocket test patterns in `tests/test_main.py`):

```python
async def test_vote_lock_with_reason_stored(client):
    # Create session, join as left judge, send vote_lock with reason
    # Verify session stores the reason
    # (follow existing websocket test setup)
    ...

async def test_vote_lock_without_reason_rejected_when_mandatory(client):
    # Create session, set require_reasons=True in session settings directly
    # Join as left judge, send vote_lock yellow with no reason
    # Expect error response
    ...

async def test_vote_lock_white_no_reason_ok_when_mandatory(client):
    # Create session, set require_reasons=True
    # Join as left judge, send vote_lock white with no reason
    # Expect success (no error)
    ...

async def test_show_results_includes_reasons(client):
    # All three judges vote and lock with reasons
    # Verify show_results broadcast contains reasons dict
    ...
```

**Step 3: Run to verify they fail**

```bash
python -m pytest tests/test_main.py -k "reason" -v
```

**Step 4: Update `vote_lock` handler in `main.py` (lines 230–275)**

After extracting `color` (line 235), add:

```python
reason = message.get("reason")
session = session_manager.sessions.get(session_code)
require_reasons = session["settings"].get("require_reasons", False) if session else False

if require_reasons and color != "white" and not reason:
    await websocket.send_json({
        "type": "error",
        "message": "Reason required before locking in"
    })
    continue
```

Update the `lock_vote()` call (line 244):

```python
result = await session_manager.lock_vote(session_code, position, color, reason=reason)
```

**Step 5: Update `show_results` broadcast (lines 260–275)**

Add a `reasons` dict to the broadcast payload:

```python
if result.get("all_locked"):
    judges = session_manager.sessions[session_code]["judges"]
    votes = {
        pos: judge["current_vote"]
        for pos, judge in judges.items()
        if judge["connected"]
    }
    reasons = {
        pos: judge["current_reason"]
        for pos, judge in judges.items()
        if judge["connected"]
    }
    session_settings = session_manager.sessions[session_code]["settings"]
    await connection_manager.broadcast_to_session(
        session_code,
        {
            "type": "show_results",
            "votes": votes,
            "reasons": reasons,
            "showExplanations": session_settings["show_explanations"],
            "liftType": session_settings["lift_type"],
        }
    )
```

**Step 6: Run tests**

```bash
python -m pytest tests/test_main.py -k "reason" -v
python -m pytest tests/ -v
```

**Step 7: Commit**

```bash
git add src/iron_verdict/main.py tests/test_main.py
git commit -m "feat: validate reason in vote_lock, include reasons in show_results broadcast"
```

---

### Task 4: Backend — Pass `require_reasons` through `settings_update` handler

**Files:**
- Modify: `src/iron_verdict/main.py`

No new tests needed — covered by Task 2 unit tests.

**Step 1: Update `settings_update` handler (lines 368–386)**

Change the `update_settings` call:

```python
result = session_manager.update_settings(
    session_code,
    message.get("showExplanations", False),
    message.get("liftType", "squat"),
    require_reasons=message.get("requireReasons", False),
)
```

**Step 2: Run full suite**

```bash
python -m pytest tests/ -v
```

**Step 3: Commit**

```bash
git add src/iron_verdict/main.py
git commit -m "feat: pass requireReasons through settings_update handler"
```

---

### Task 5: Frontend — Head judge "Require reasons" toggle

**Files:**
- Modify: `src/iron_verdict/static/index.html`

No automated tests — verify manually.

**Step 1: Add `requireReasons` to Alpine.js data object**

Find the `ironVerdictApp()` function data object. Add:

```javascript
requireReasons: false,
```

**Step 2: Initialize `requireReasons` from `join_success`**

Find where `join_success` session state is applied. Add:

```javascript
this.requireReasons = message.session_state?.settings?.require_reasons ?? false;
```

**Step 3: Handle incoming `settings_update` message**

Find where incoming `settings_update` messages update local state (judges receive settings broadcasts). Add:

```javascript
if (message.requireReasons !== undefined) {
    this.requireReasons = message.requireReasons;
}
```

**Step 4: Add toggle to head judge settings bar (after line 800)**

After the "Show rule explanations" label in the `.settings-bar` div:

```html
<label>
    <input type="checkbox" x-model="requireReasons" @change="saveSettings()">
    Require reasons
</label>
```

**Step 5: Include `requireReasons` in `saveSettings()` (line 1088–1093)**

Add to the WebSocket send payload:

```javascript
this.ws.send(JSON.stringify({
    type: 'settings_update',
    showExplanations: this.showExplanations,
    liftType: this.liftType,
    requireReasons: this.requireReasons,
}));
```

Also add to localStorage persistence:

```javascript
localStorage.setItem('requireReasons', this.requireReasons);
```

**Step 6: Manual test**

- Open session as center judge
- Verify "Require reasons" toggle appears in Head Judge Controls
- Toggle on/off — no errors
- Open DevTools Network tab, verify `settings_update` WS message includes `requireReasons`

**Step 7: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "feat: add Require reasons toggle to head judge settings"
```

---

### Task 6: Frontend — Two-step judge voting flow

**Files:**
- Modify: `src/iron_verdict/static/index.html`

**Step 1: Add state to Alpine.js data object**

```javascript
selectedReason: null,
showingReasonStep: false,
```

**Step 2: Add helper methods**

After the existing `selectVote()` method (line 1067):

```javascript
selectVote(color) {
    if (!this.voteLocked) {
        this.selectedVote = color;
        this.selectedReason = null;
        this.showingReasonStep = (color !== 'white');
    }
},

goBackToColorStep() {
    this.showingReasonStep = false;
    this.selectedReason = null;
},

selectReason(reason) {
    this.selectedReason = reason;
},

getJudgeReasons() {
    const liftType = this.liftType || 'squat';
    return CARD_REASONS[liftType]?.[this.selectedVote] || [];
},

canLockIn() {
    if (!this.selectedVote || this.voteLocked) return false;
    if (this.selectedVote === 'white') return true;
    if (this.requireReasons) return !!this.selectedReason;
    return true;
},
```

**Step 3: Update `lockVote()` to send reason (line 1073–1081)**

```javascript
lockVote() {
    if (this.canLockIn()) {
        this.voteLocked = true;
        this.ws.send(JSON.stringify({
            type: 'vote_lock',
            color: this.selectedVote,
            reason: this.selectedVote !== 'white' ? this.selectedReason : null,
        }));
    }
},
```

**Step 4: Update `resetVoting()` (line 1096)**

Add after existing resets:

```javascript
this.selectedReason = null;
this.showingReasonStep = false;
```

**Step 5: Update Lock In button condition (line 774)**

Change `x-show="selectedVote && !voteLocked"` to:

```html
x-show="canLockIn() && !voteLocked"
```

**Step 6: Wrap vote grid with `x-show` (line 751)**

Add `x-show="!showingReasonStep"` to the `.vote-grid` div:

```html
<div class="vote-grid" x-show="!showingReasonStep" :style="voteLocked ? 'opacity:0.35;pointer-events:none' : ''">
```

**Step 7: Add reason selection HTML** after the closing `</div>` of `.vote-grid` (after line 772):

```html
<div class="reason-step" x-show="showingReasonStep && !voteLocked">
    <div class="reason-step-header">
        <button class="back-btn" @click="goBackToColorStep()">&#8592; back</button>
        <span class="reason-step-color" :class="selectedVote" x-text="selectedVote?.toUpperCase()"></span>
    </div>
    <div class="reason-list">
        <template x-for="reason in getJudgeReasons()" :key="reason">
            <div class="reason-item"
                 :class="{ selected: selectedReason === reason }"
                 @click="selectReason(reason)"
                 x-text="reason">
            </div>
        </template>
    </div>
</div>
```

**Step 8: Add CSS** in the `<style>` block:

```css
.reason-step { display: flex; flex-direction: column; gap: 0.5rem; width: 100%; }
.reason-step-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.25rem; }
.back-btn { background: transparent; border: 1px solid rgba(255,255,255,0.3); color: white; padding: 0.4rem 0.9rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.back-btn:active { background: rgba(255,255,255,0.1); }
.reason-step-color { font-weight: 700; font-size: 1.1rem; letter-spacing: 0.05em; }
.reason-step-color.yellow { color: #fbbf24; }
.reason-step-color.red { color: #ef4444; }
.reason-step-color.blue { color: #60a5fa; }
.reason-list { display: flex; flex-direction: column; overflow-y: auto; max-height: 55vh; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }
.reason-item { padding: 1rem 1.2rem; background: rgba(255,255,255,0.07); border-bottom: 1px solid rgba(255,255,255,0.08); cursor: pointer; font-size: 1rem; color: white; transition: background 0.15s; }
.reason-item:last-child { border-bottom: none; }
.reason-item:active, .reason-item:hover { background: rgba(255,255,255,0.15); }
.reason-item.selected { background: rgba(255,255,255,0.18); border-left: 3px solid white; padding-left: calc(1.2rem - 3px); }
```

**Step 9: Manual test**

- Select white → Lock In appears immediately, no reason step
- Select yellow → reason list appears with correct reasons for current lift type
- Tap a reason → it highlights, Lock In appears
- Tap back → returns to color grid with yellow still selected
- With "Require reasons" off: Lock In visible without selecting a reason
- With "Require reasons" on: Lock In hidden until reason selected
- Lock in → vote locked confirmation shows selected color

**Step 10: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "feat: two-step judge voting flow with reason selection"
```

---

### Task 7: Frontend — Display screen: reasons beneath orbs, remove explanation phase

**Files:**
- Modify: `src/iron_verdict/static/index.html`

**Step 1: Add `displayReasons` to Alpine.js data**

```javascript
displayReasons: { left: null, center: null, right: null },
```

**Step 2: Populate from `show_results` (line 1029)**

In the `show_results` handler, after `this.displayVotes = message.votes`:

```javascript
this.displayReasons = message.reasons || { left: null, center: null, right: null };
```

**Step 3: Clear on reset (line 1051)**

In `reset_for_next_lift` handler, add:

```javascript
this.displayReasons = { left: null, center: null, right: null };
```

**Step 4: Simplify phase timer (lines 1035–1043)**

Replace the entire timer block with:

```javascript
this._phaseTimer1 = setTimeout(() => {
    this.displayPhase = 'idle';
}, 3000);
```

**Step 5: Replace display HTML (lines 819–844)**

Replace the entire `<!-- Phase 1 & idle -->` and `<!-- Phase 2: Explanation panel -->` blocks with:

```html
<!-- Vote orbs with reasons -->
<div class="display-lights" x-show="displayPhase === 'votes' || displayPhase === 'idle'">
    <div class="display-orb-wrap">
        <div class="display-orb" :class="displayVotes.left"></div>
        <div class="display-orb-reason"
             x-show="displayShowExplanations && displayVotes.left && displayVotes.left !== 'white' && displayReasons.left"
             x-text="displayReasons.left"></div>
    </div>
    <div class="display-orb-wrap">
        <div class="display-orb" :class="displayVotes.center"></div>
        <div class="display-orb-reason"
             x-show="displayShowExplanations && displayVotes.center && displayVotes.center !== 'white' && displayReasons.center"
             x-text="displayReasons.center"></div>
    </div>
    <div class="display-orb-wrap">
        <div class="display-orb" :class="displayVotes.right"></div>
        <div class="display-orb-reason"
             x-show="displayShowExplanations && displayVotes.right && displayVotes.right !== 'white' && displayReasons.right"
             x-text="displayReasons.right"></div>
    </div>
</div>

<!-- Verdict shown alongside orbs during votes phase -->
<div class="display-verdict-inline" x-show="displayPhase === 'votes'">
    <div class="verdict-stamp"
         :class="isValidLift() ? 'valid' : 'invalid'"
         x-text="isValidLift() ? 'Good Lift' : 'No Lift'"></div>
</div>
```

**Step 6: Add/update CSS for orb wrappers and reason labels**

Find the display lights CSS. Update the orb container to space items wider and add wrapper styles:

```css
.display-lights {
    display: flex;
    justify-content: center;
    align-items: flex-start;
    gap: 5rem;          /* was tighter — increase for reason label room */
}
.display-orb-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
}
.display-orb-reason {
    font-size: 1.2rem;
    color: rgba(255, 255, 255, 0.85);
    text-align: center;
    max-width: 160px;
    line-height: 1.3;
    font-weight: 500;
}
.display-verdict-inline {
    margin-top: 1.5rem;
}
```

**Step 7: Manual end-to-end test**

Full flow test:
1. Head judge enables "Show rule explanations" + "Require reasons", lift type = bench
2. Left judge selects yellow → picks "Buttocks up" → locks in
3. Center judge selects white → locks in
4. Right judge selects yellow → picks "Incomplete lift" → locks in
5. Display shows three orbs: yellow/white/yellow with "Buttocks up" under left, nothing under center, "Incomplete lift" under right; verdict ("No Lift") appears below orbs
6. After ~3 seconds, display returns to idle, reasons cleared
7. Repeat with "Show rule explanations" off — verify no reason text shown

**Step 8: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "feat: show chosen reason beneath orb on display, remove explanation phase"
```

---

## Final Verification

```bash
python -m pytest tests/ -v
```

All tests must pass.
