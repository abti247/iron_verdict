# Navigation & Timer Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add timer reset on next lift, browser back button navigation, and clickable session code for role switching.

**Architecture:** All changes are frontend-only (index.html). Add `intentionalNavigation` flag to distinguish user-initiated navigation from unintended disconnects. Timer stops when "Next Lift" is clicked. Session code becomes clickable on judge/display screens.

**Tech Stack:** Alpine.js, WebSockets, vanilla JavaScript

---

## Task 1: Stop Timer on Next Lift

**Files:**
- Modify: `src/judgeme/static/index.html:208-213`

**Step 1: Verify current timer reset behavior**

In `src/judgeme/static/index.html`, find the `reset_for_next_lift` message handler (around line 208):

```javascript
} else if (message.type === 'reset_for_next_lift') {
    this.resetVoting();
    if (this.role === 'display') {
        this.displayVotes = { left: null, center: null, right: null };
        this.displayStatus = 'Waiting for judges...';
    }
}
```

**Step 2: Add stopTimer() call**

Replace the handler with:

```javascript
} else if (message.type === 'reset_for_next_lift') {
    this.resetVoting();
    this.stopTimer();
    if (this.role === 'display') {
        this.displayVotes = { left: null, center: null, right: null };
        this.displayStatus = 'Waiting for judges...';
    }
}
```

**Step 3: Commit**

```bash
cd .worktrees/feature/navigation-timer
git add src/judgeme/static/index.html
git commit -m "feat: stop timer when next lift is clicked"
```

---

## Task 2: Add intentionalNavigation Flag

**Files:**
- Modify: `src/judgeme/static/index.html:126-140`

**Step 1: Add flag to app state**

In the `judgemeApp()` function, find the initial state object (around line 126). Add the flag after `displayStatus`:

```javascript
function judgemeApp() {
    return {
        screen: 'landing',
        sessionCode: '',
        joinCode: '',
        role: '',
        isHead: false,
        ws: null,
        selectedVote: null,
        voteLocked: false,
        resultsShown: false,
        timerDisplay: '60',
        timerExpired: false,
        timerInterval: null,
        displayVotes: { left: null, center: null, right: null },
        displayStatus: 'Waiting for judges...',
        intentionalNavigation: false,
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add intentionalNavigation flag to app state"
```

---

## Task 3: Update WebSocket onclose Handler

**Files:**
- Modify: `src/judgeme/static/index.html:184-189`

**Step 1: Find and update onclose handler**

Find the `ws.onclose` handler (around line 184):

```javascript
this.ws.onclose = (event) => {
    if (!event.wasClean) {
        console.error('WebSocket closed unexpectedly:', event);
        alert('Connection lost. Please refresh and try again.');
    }
};
```

Replace with:

```javascript
this.ws.onclose = (event) => {
    if (!event.wasClean && !this.intentionalNavigation) {
        console.error('WebSocket closed unexpectedly:', event);
        alert('Connection lost. Please refresh and try again.');
    }
};
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: skip error alert on intentional navigation"
```

---

## Task 4: Add Browser Back Button Handler

**Files:**
- Modify: `src/judgeme/static/index.html:125-301` (add to judgemeApp after all methods)

**Step 1: Add returnToRoleSelection method**

Add this method to the return object in `judgemeApp()`, before the closing brace:

```javascript
                returnToRoleSelection() {
                    this.intentionalNavigation = true;
                    if (this.ws) {
                        this.ws.close();
                    }
                    this.screen = 'role-select';
                    this.selectedVote = null;
                    this.voteLocked = false;
                    this.resultsShown = false;
                    this.timerDisplay = '60';
                    this.timerExpired = false;
                    if (this.timerInterval) {
                        clearInterval(this.timerInterval);
                    }
                },
```

Add this after the closing brace of `judgemeApp()` function:

```javascript
        // Handle browser back button
        window.addEventListener('popstate', () => {
            const appElement = document.querySelector('[x-data]');
            if (appElement && appElement.__x_data) {
                const app = appElement.__x_data;
                if ((app.screen === 'judge' || app.screen === 'display') && app.sessionCode) {
                    app.returnToRoleSelection();
                    // Prevent default back navigation
                    history.pushState(null, null, location.href);
                }
            }
        });
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add browser back button handler for role selection navigation"
```

---

## Task 5: Make Session Code Clickable on Judge Screen

**Files:**
- Modify: `src/judgeme/static/index.html:42-46`

**Step 1: Update judge screen session code display**

Find the judge screen session code display (around line 42-46):

```html
<div style="background: #f5f5f5; padding: 10px; margin-bottom: 20px;">
    <strong>Session:</strong> <span x-text="sessionCode"></span> |
    <strong>Timer:</strong> <span x-text="timerDisplay" :style="timerExpired ? 'color: red;' : ''"></span>
</div>
```

Replace with:

```html
<div style="background: #f5f5f5; padding: 10px; margin-bottom: 20px;">
    <strong>Session:</strong> <span x-text="sessionCode" @click="returnToRoleSelection()" style="cursor: pointer; text-decoration: underline;"></span> |
    <strong>Timer:</strong> <span x-text="timerDisplay" :style="timerExpired ? 'color: red;' : ''"></span>
</div>
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: make session code clickable on judge screen"
```

---

## Task 6: Make Session Code Clickable on Display Screen

**Files:**
- Modify: `src/judgeme/static/index.html:97-121`

**Step 1: Update display screen to show clickable session code**

Find the display screen section (around line 97-121). Add session code display before the timer:

```html
<div x-show="screen === 'display'">
    <div style="padding: 10px; text-align: center;">
        <strong>Session:</strong> <span x-text="sessionCode" @click="returnToRoleSelection()" style="cursor: pointer; text-decoration: underline;"></span>
    </div>
    <div style="text-align: center; padding: 40px;">
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: make session code clickable on display screen"
```

---

## Task 7: Manual Testing

**Files:**
- Test: Manual browser testing

**Step 1: Start the application**

```bash
cd .worktrees/feature/navigation-timer
python run.py
```

Application should be available at `http://localhost:8000`

**Step 2: Test timer reset on next lift**

1. Create a new session
2. Join as center judge
3. Click "Start Timer"
4. Verify timer counts down
5. Lock in a vote (as center judge)
6. Have a test judge open in another tab and lock their vote
7. When results show, click "Next Lift"
8. Verify timer immediately resets to 60 and stops counting

**Step 3: Test browser back button**

1. Create session and join as judge
2. Press browser back button
3. Verify you return to role selection screen
4. Verify session code is preserved (you can immediately rejoin)

**Step 4: Test clickable session code on judge screen**

1. Create session and join as judge
2. Click on the session code
3. Verify you return to role selection screen
4. Verify session code is still visible

**Step 5: Test clickable session code on display screen**

1. Create session and join as display
2. Click on the session code
3. Verify you return to role selection screen
4. Verify session code is still visible

**Step 6: Test no error alerts on intentional navigation**

1. Join as judge or display
2. Click back button or session code
3. Verify no "Connection lost" alert appears
4. Verify smooth navigation back to role selection

**Step 7: Commit successful testing**

```bash
git add -A
git commit -m "test: manual verification of all features complete"
```

---

## Task 8: Automated Testing (Optional)

**Files:**
- Modify: `tests/test_main.py`

**Note:** Since these are frontend-only changes, traditional backend tests don't apply. Manual browser testing (Task 7) is the primary verification method. No new automated tests are required.

---

## Summary

- **Task 1:** Timer stops when "Next Lift" clicked (1 line change)
- **Task 2:** Add `intentionalNavigation` flag to app state
- **Task 3:** Skip error alert when flag is set
- **Task 4:** Add back button handler and `returnToRoleSelection()` method
- **Task 5:** Make session code clickable on judge screen
- **Task 6:** Make session code clickable on display screen
- **Task 7:** Manual testing verification
- **Task 8:** No automated tests needed (frontend-only)

**Total Changes:** ~50 lines of JavaScript/HTML modifications across one file.

All changes are isolated to `src/judgeme/static/index.html` with clear commit points between each feature.
