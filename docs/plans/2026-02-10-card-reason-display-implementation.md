# Card Reason Display Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After judges vote, automatically display rule explanations on the display screen (3s vote result → 6s explanation → idle), controlled by a head judge settings panel.

**Architecture:** Head judge settings (show_explanations, lift_type) are stored in localStorage and synced to the server via a new `settings_update` WebSocket message. The server persists settings in session state and injects them into the `show_results` broadcast. The display client drives the 3-phase timing sequence entirely client-side.

**Tech Stack:** FastAPI + WebSockets (backend), Alpine.js + vanilla CSS (frontend), pytest (tests).

---

### Task 1: Add settings to session state

**Files:**
- Modify: `src/judgeme/session.py:21-46` (create_session)
- Modify: `src/judgeme/session.py:120-134` (after reset_for_next_lift)
- Test: `tests/test_session.py`

**Step 1: Write failing tests**

Add to `tests/test_session.py`:
```python
def test_create_session_initializes_settings():
    manager = SessionManager()
    code = manager.create_session()
    session = manager.sessions[code]
    assert "settings" in session
    assert session["settings"]["show_explanations"] is False
    assert session["settings"]["lift_type"] == "squat"


def test_update_settings_stores_values():
    manager = SessionManager()
    code = manager.create_session()
    result = manager.update_settings(code, True, "bench")
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["show_explanations"] is True
    assert manager.sessions[code]["settings"]["lift_type"] == "bench"


def test_update_settings_invalid_session_fails():
    manager = SessionManager()
    result = manager.update_settings("INVALID", True, "squat")
    assert result["success"] is False
```

**Step 2: Run to verify they fail**

```
pytest tests/test_session.py::test_create_session_initializes_settings tests/test_session.py::test_update_settings_stores_values tests/test_session.py::test_update_settings_invalid_session_fails -v
```
Expected: FAIL (AttributeError or AssertionError)

**Step 3: Implement**

In `session.py`, inside `create_session()`, add `"settings"` key after `"timer_state"` line:
```python
"timer_state": "idle",
"settings": {
    "show_explanations": False,
    "lift_type": "squat",
},
"last_activity": datetime.now(),
```

Add new method after `reset_for_next_lift()`:
```python
def update_settings(self, code: str, show_explanations: bool, lift_type: str) -> Dict[str, Any]:
    """Update head judge display settings."""
    if code not in self.sessions:
        return {"success": False, "error": "Session not found"}
    session = self.sessions[code]
    session["settings"]["show_explanations"] = show_explanations
    session["settings"]["lift_type"] = lift_type
    session["last_activity"] = datetime.now()
    return {"success": True}
```

**Step 4: Run tests to verify they pass**

```
pytest tests/test_session.py -v
```
Expected: All pass (including existing tests)

**Step 5: Commit**

```bash
git add src/judgeme/session.py tests/test_session.py
git commit -m "feat: add settings to session state for card reason display"
```

---

### Task 2: Handle settings_update message + inject into show_results

**Files:**
- Modify: `src/judgeme/main.py:111-121` (show_results broadcast)
- Modify: `src/judgeme/main.py:206-211` (before else: pass)
- Test: `tests/test_main.py`

**Step 1: Write failing tests**

Read `tests/test_main.py` first to understand the existing test patterns, then add:

```python
@pytest.mark.asyncio
async def test_settings_update_stored_in_session(client, session_code):
    """Head judge can update settings via settings_update message."""
    async with client.websocket_connect("/ws") as ws:
        await ws.send_json({"type": "join", "session_code": session_code, "role": "center_judge"})
        await ws.receive_json()  # join_success

        await ws.send_json({
            "type": "settings_update",
            "showExplanations": True,
            "liftType": "deadlift"
        })
        # No broadcast expected, just check session state
        session = session_manager.sessions[session_code]
        assert session["settings"]["show_explanations"] is True
        assert session["settings"]["lift_type"] == "deadlift"


@pytest.mark.asyncio
async def test_show_results_includes_settings(client, session_code):
    """show_results broadcast includes current settings."""
    # Connect all 3 judges
    # Lock all votes
    # Verify show_results message contains showExplanations and liftType keys
    ...  # follow existing all-votes-locked test pattern
```

Note: Check the existing test fixtures in `tests/test_main.py` — use the same `client` and `session_code` fixtures already defined there.

**Step 2: Run to verify they fail**

```
pytest tests/test_main.py -k "settings" -v
```
Expected: FAIL

**Step 3: Implement in main.py**

Change 1 — `show_results` broadcast (around line 112-121), inject settings:
```python
if result.get("all_locked"):
    votes = {
        pos: judge["current_vote"]
        for pos, judge in session_manager.sessions[session_code]["judges"].items()
        if judge["connected"]
    }
    settings = session_manager.sessions[session_code]["settings"]
    await connection_manager.broadcast_to_session(
        session_code,
        {
            "type": "show_results",
            "votes": votes,
            "showExplanations": settings["show_explanations"],
            "liftType": settings["lift_type"],
        }
    )
```

Change 2 — add `settings_update` handler before `else: pass` (around line 208):
```python
elif message_type == "settings_update":
    if not session_code or not role:
        continue
    if role != "center_judge":
        await websocket.send_json({
            "type": "error",
            "message": "Only head judge can update settings"
        })
        continue
    session_manager.update_settings(
        session_code,
        message.get("showExplanations", False),
        message.get("liftType", "squat")
    )
```

**Step 4: Run tests**

```
pytest tests/test_main.py -v
```
Expected: All pass

**Step 5: Commit**

```bash
git add src/judgeme/main.py tests/test_main.py
git commit -m "feat: handle settings_update message and include settings in show_results"
```

---

### Task 3: Head judge settings panel (frontend)

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Add card reasons data**

Before `function judgemeApp()` at line 644, insert:
```javascript
const CARD_REASONS = {
    squat: {
        red: ["Not deep enough", "No upright position"],
        blue: ["Double bounce", "Movement during ascent"],
        yellow: ["Foot movement", "Didn't wait for signal", "Elbow touching thighs", "Dropped the bar", "Incomplete attempt"]
    },
    bench: {
        red: ["Bar didn't touch chest", "Elbows not low enough"],
        blue: ["Downward movement during press", "Arms not fully locked"],
        yellow: ["Bar bounced on chest", "Didn't wait for signal", "Position changed", "Feet moved or lifted", "Bar touched uprights", "Incomplete attempt"]
    },
    deadlift: {
        red: ["Knees not locked", "Shoulders not back"],
        blue: ["Downward movement", "Supported on thighs"],
        yellow: ["Lowered before signal", "Dropped the bar", "Foot movement", "Incomplete attempt"]
    }
};
```

**Step 2: Add state variables**

After `intentionalNavigation: false,` (line 660), add:
```javascript
showExplanations: false,
liftType: 'squat',
displayPhase: 'idle',
displayShowExplanations: false,
displayLiftType: 'squat',
```

**Step 3: Add saveSettings() method**

After `lockVote()` method (around line 772), add:
```javascript
saveSettings() {
    localStorage.setItem('showExplanations', this.showExplanations);
    localStorage.setItem('liftType', this.liftType);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
            type: 'settings_update',
            showExplanations: this.showExplanations,
            liftType: this.liftType
        }));
    }
},
```

**Step 4: Load from localStorage in init() and sync on join**

In `init()` (line 916), before the URL param check, add:
```javascript
this.showExplanations = localStorage.getItem('showExplanations') === 'true';
this.liftType = localStorage.getItem('liftType') || 'squat';
```

In `handleMessage`, inside the `join_success` block (line 725-727), add:
```javascript
if (message.type === 'join_success') {
    this.isHead = message.is_head;
    this.screen = this.role === 'display' ? 'display' : 'judge';
    if (this.isHead) {
        this.saveSettings();  // sync localStorage settings to server
    }
}
```

**Step 5: Add settings panel HTML**

Inside the `.head-controls` div (after line 619, before closing `</div>`), add:
```html
<div class="settings-panel">
    <label class="settings-label">
        <input type="checkbox" x-model="showExplanations" @change="saveSettings()">
        Show rule explanations
    </label>
    <select x-model="liftType" @change="saveSettings()" class="lift-select">
        <option value="squat">Squat</option>
        <option value="bench">Bench Press</option>
        <option value="deadlift">Deadlift</option>
    </select>
</div>
```

**Step 6: Add CSS**

In the `<style>` block, add:
```css
.settings-panel {
    margin-top: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    background: var(--color-surface);
    border-radius: var(--radius-md);
    border: 2px solid var(--color-border);
    display: flex;
    align-items: center;
    gap: var(--space-md);
    flex-wrap: wrap;
}

.settings-label {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-weight: 600;
    cursor: pointer;
}

.lift-select {
    padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-sm);
    border: 2px solid var(--color-border);
    background: var(--color-background);
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    min-width: 160px;
}
```

**Step 7: Manual smoke test**

Start the server (`python run.py`), open demo mode, verify:
- Center judge screen shows settings panel below head controls
- Toggle persists after page reload
- Dropdown persists after page reload

**Step 8: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add head judge settings panel for rule explanation toggle and lift type"
```

---

### Task 4: Display phase logic + explanation UI

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Update show_results handler**

Replace the `show_results` block in `handleMessage` (lines 734-739):
```javascript
} else if (message.type === 'show_results') {
    this.resultsShown = true;
    if (this.role === 'display') {
        this.displayVotes = message.votes;
        this.displayShowExplanations = message.showExplanations;
        this.displayLiftType = message.liftType;
        this.displayPhase = 'votes';

        setTimeout(() => {
            const nonWhite = Object.values(this.displayVotes).filter(c => c && c !== 'white');
            if (this.displayShowExplanations && nonWhite.length > 0) {
                this.displayPhase = 'explanation';
                setTimeout(() => { this.displayPhase = 'idle'; }, 6000);
            } else {
                this.displayPhase = 'idle';
            }
        }, 3000);
    }
}
```

**Step 2: Update reset_for_next_lift handler**

Replace the display portion of the `reset_for_next_lift` block (lines 740-746):
```javascript
} else if (message.type === 'reset_for_next_lift') {
    this.resetVoting();
    this.stopTimer();
    if (this.role === 'display') {
        this.displayVotes = { left: null, center: null, right: null };
        this.displayPhase = 'idle';
        this.displayStatus = 'Waiting for judges...';
    }
}
```

**Step 3: Add helper methods**

After `getReasons()` is a new method — add near the other display-related methods:
```javascript
isValidLift() {
    const whiteCount = Object.values(this.displayVotes).filter(c => c === 'white').length;
    return whiteCount >= 2;
},

getInvalidColors() {
    return [...new Set(Object.values(this.displayVotes).filter(c => c && c !== 'white'))];
},

getReasons(color) {
    const liftData = CARD_REASONS[this.displayLiftType];
    return liftData ? (liftData[color] || []) : [];
},
```

**Step 4: Update display screen HTML**

Replace the entire display screen (lines 624-640) with:
```html
<!-- Display Screen -->
<div class="screen" x-show="screen === 'display'">
    <div class="display-header">
        <span class="session-code" @click="returnToRoleSelection()" x-text="sessionCode">ABC123</span>
    </div>

    <div class="display-container">
        <div class="display-timer" :class="timerExpired && 'expired'" x-text="timerDisplay"></div>

        <!-- Phase 1: Vote circles -->
        <div class="judge-lights" x-show="displayPhase === 'votes' || displayPhase === 'idle'">
            <div class="judge-light" :class="displayVotes.left && 'voted ' + displayVotes.left"></div>
            <div class="judge-light" :class="displayVotes.center && 'voted ' + displayVotes.center"></div>
            <div class="judge-light" :class="displayVotes.right && 'voted ' + displayVotes.right"></div>
        </div>

        <!-- Phase 2: Explanation panel -->
        <div class="explanation-panel" x-show="displayPhase === 'explanation'">
            <div class="result-indicator" :class="isValidLift() ? 'valid' : 'invalid'"
                 x-text="isValidLift() ? '✅ VALID' : '❌ INVALID'"></div>
            <template x-for="color in getInvalidColors()" :key="color">
                <div class="card-reason-group">
                    <div class="card-reason-header" :class="'reason-' + color" x-text="color.toUpperCase() + ' CARD'"></div>
                    <ul class="card-reason-list">
                        <template x-for="reason in getReasons(color)" :key="reason">
                            <li x-text="reason"></li>
                        </template>
                    </ul>
                </div>
            </template>
        </div>

        <div class="display-status" x-text="displayStatus"></div>
    </div>
</div>
```

**Step 5: Add CSS for explanation panel**

In the `<style>` block, add:
```css
.explanation-panel {
    width: 100%;
    max-width: 600px;
    margin: 0 auto;
    padding: var(--space-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    align-items: center;
}

.result-indicator {
    font-size: 2.5rem;
    font-weight: 800;
    padding: var(--space-sm) var(--space-lg);
    border-radius: var(--radius-md);
    letter-spacing: 0.05em;
}

.result-indicator.valid {
    background: #d1fae5;
    color: #065f46;
}

.result-indicator.invalid {
    background: #fee2e2;
    color: #991b1b;
}

.card-reason-group {
    width: 100%;
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

.card-reason-header {
    padding: var(--space-xs) var(--space-md);
    font-weight: 700;
    font-size: 1.1rem;
    color: white;
}

.reason-red    { background: #dc2626; }
.reason-blue   { background: #2563eb; }
.reason-yellow { background: #d97706; }

.card-reason-list {
    margin: 0;
    padding: var(--space-sm) var(--space-md) var(--space-sm) calc(var(--space-md) + 1.5em);
    background: var(--color-surface);
    list-style: disc;
}

.card-reason-list li {
    padding: 2px 0;
    font-size: 1rem;
}
```

**Step 6: Manual smoke test**

Start the server, open demo mode:
1. Enable "Show rule explanations" on center judge
2. Set lift type to "Deadlift"
3. Lock votes where at least one non-white card is given
4. Verify: circles show for 3s → explanation panel with correct reasons for 6s → idle
5. Verify: with only white cards, display goes directly to idle after 3s
6. Click "Next Lift" — verify display resets cleanly

**Step 7: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add display phase sequence with rule explanation panel"
```
