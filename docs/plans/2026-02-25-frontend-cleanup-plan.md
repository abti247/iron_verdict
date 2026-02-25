# Frontend Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all AGENTS.md violations in the static frontend: remove 23 static inline styles from index.html into CSS, and split app.js (395 lines) into app.js + demo.js + handlers.js, all under 300 lines.

**Architecture:** New CSS classes land in layout.css (screen-specific) and components.css (reusable). Two new JS modules export a mixin object (demo.js) and named handler functions (handlers.js); app.js imports and uses them. No HTML script tag changes needed — handlers.js and demo.js are internal imports.

**Tech Stack:** Vanilla CSS custom properties, ES modules, Alpine.js component pattern.

---

> **Note:** components.css is already 413 lines (a pre-existing violation). We add only 4 small utility classes there; splitting components.css is a separate task.

---

### Task 1: Add screen-specific CSS classes to layout.css

**Files:**
- Modify: `src/iron_verdict/static/css/layout.css` (append at end)

**Step 1: Append the following CSS block to layout.css**

```css
/* ===== DEMO INTRO SCREEN ===== */
.landing-panel--demo {
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
}

.demo-guide-text {
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-dim);
    margin: 20px 0 0;
    line-height: 1.6;
}

.demo-guide-heading {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 18px;
    letter-spacing: 3px;
    color: var(--blood-bright);
    margin: 24px 0 8px;
}

.demo-guide-list {
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-dim);
    line-height: 1.8;
    padding-left: 18px;
    margin: 0;
}

.demo-popup-note {
    margin-top: 24px;
    border-left: 2px solid var(--blood);
    padding: 8px 12px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 14px;
    color: var(--text-dim);
    letter-spacing: 0.5px;
}

.demo-launch-wrap {
    margin-top: 20px;
}

.demo-running-msg {
    margin-top: 24px;
    text-align: center;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 16px;
    letter-spacing: 3px;
    color: var(--blood-bright);
}

/* ===== LANDING SCREEN ===== */
.app-version {
    margin-top: 24px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 12px;
    color: var(--text-dim);
    letter-spacing: 1px;
    opacity: 0.4;
}

/* ===== CONTACT SCREEN ===== */
.contact-error {
    text-align: center;
    color: var(--blood-bright);
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    letter-spacing: 1px;
}

.contact-success {
    text-align: center;
    padding: 24px 0;
    color: var(--success);
    font-family: 'Bebas Neue', sans-serif;
    font-size: 22px;
    letter-spacing: 4px;
    border: 1px solid var(--success);
    background: rgba(34, 197, 94, 0.05);
}

.contact-success-sub {
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    letter-spacing: 1px;
    margin-top: 6px;
    color: var(--text-dim);
}
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/css/layout.css
git commit -m "style: add demo-intro, landing, and contact CSS classes to layout.css"
```

---

### Task 2: Add reusable utility classes to components.css

**Files:**
- Modify: `src/iron_verdict/static/css/components.css` (append at end)

**Step 1: Append the following CSS block to components.css**

```css
/* ===== BUTTON ROW SPACING ===== */
.btn-row { margin-top: 16px; }
.btn-row--sm { margin-top: 8px; }

/* ===== EMPHASIS TEXT ===== */
.text-em {
    color: var(--text-main);
    font-weight: 700;
}

/* ===== FORM STACK MODIFIER ===== */
.form-stack--no-top { margin-top: 0; }
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "style: add btn-row, text-em, form-stack--no-top utility classes"
```

---

### Task 3: Replace inline styles in index.html — demo-intro section

**Files:**
- Modify: `src/iron_verdict/static/index.html`

**Step 1: Replace the entire demo-intro `<div>` block (lines 23–90) with the version below**

Exact replacement — the `<!-- Demo Intro Screen -->` comment through the closing `</div>`:

```html
    <!-- Demo Intro Screen -->
    <div class="landing-wrap" x-show="screen === 'demo-intro'">
        <div class="landing-panel cut-corner landing-panel--demo">

            <div class="brand-iron chrome-text">Iron Verdict</div>
            <div class="brand-verdict-sub">Demo Guide</div>

            <p class="demo-guide-text">
                Iron Verdict allows judges to pick the reason for an invalid lift,
                shared instantly with athletes, audience, jury, and fellow judges.
            </p>

            <div class="demo-guide-heading">Why Iron Verdict?</div>
            <ul class="demo-guide-list">
                <li><span class="text-em">Athletes</span> — Know your mistake immediately, no time wasted.</li>
                <li><span class="text-em">Audience</span> — No more guessing why a lift was ruled invalid.</li>
                <li><span class="text-em">Judges</span> — Understand your colleagues' calls and know what to focus on next attempt.</li>
                <li><span class="text-em">Jury</span> — Know exactly which part of the lift to review before overruling.</li>
            </ul>

            <div class="demo-guide-heading">Setup</div>
            <ol class="demo-guide-list">
                <li>Enter a session name → click <span class="text-em">Create New Session</span></li>
                <li>Send the session code to other judges</li>
                <li>Use the session code to set up a <span class="text-em">Display Screen</span></li>
            </ol>

            <div class="demo-guide-heading">Head Judge Controls</div>
            <ul class="demo-guide-list">
                <li><span class="text-em">Show reasons on display</span> — ruling reasons appear on the display screen</li>
                <li><span class="text-em">Require reasons</span> — judges must choose a reason before locking in (optional by default)</li>
                <li><span class="text-em">Lift category dropdown</span> — changes the reason catalogue (Squat / Bench / Deadlift)</li>
            </ul>

            <div class="demo-guide-heading">During Competition</div>
            <ol class="demo-guide-list">
                <li>Head judge announces "The bar is loaded" and presses <span class="text-em">Start Timer</span></li>
                <li>After the lift, judges press their color, optionally pick a reason, then press <span class="text-em">Lock In</span></li>
                <li>When all 3 judges lock in, the result appears on the <span class="text-em">Display Screen</span></li>
                <li>Head judge presses <span class="text-em">Next Lift</span> to reset for the next lifter</li>
                <li>If needed, head judge presses <span class="text-em">Reset Timer</span></li>
                <li>After the event: <span class="text-em">End Session</span> → confirm with <span class="text-em">OK</span></li>
            </ol>

            <div x-show="!demoRunning" class="demo-popup-note">
                This demo opens 4 pop-up windows — please allow pop-ups if prompted.
            </div>

            <div x-show="!demoRunning" class="demo-launch-wrap">
                <button class="btn-blood btn-blood-primary cut-corner-sm" @click="launchDemo()">
                    Launch Demo
                </button>
            </div>

            <div x-show="demoRunning" class="demo-running-msg">
                Demo running — interact with the 4 open windows
            </div>

            <div class="btn-row">
                <button class="btn-blood btn-blood-ghost" @click="returnToLandingFromDemo()">
                    &larr; Back to Start
                </button>
            </div>

        </div>
    </div>
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "style: extract demo-intro inline styles to CSS classes"
```

---

### Task 4: Replace inline styles in index.html — landing and contact sections

**Files:**
- Modify: `src/iron_verdict/static/index.html`

**Step 1: Replace the landing screen button rows and version string**

Find and replace these three fragments inside the `<!-- Landing Screen -->` section:

Fragment 1 — replace:
```html
            <div style="margin-top: 16px;">
                <button class="btn-blood btn-blood-ghost" @click="startDemo()">
                    Start Demo
                </button>
            </div>

            <div style="margin-top: 8px;">
                <button class="btn-blood btn-blood-ghost" @click="goToContact()">
                    Contact
                </button>
            </div>

            <div style="margin-top: 24px; font-family: 'Rajdhani', sans-serif; font-size: 12px; color: var(--text-dim); letter-spacing: 1px; opacity: 0.4;">
                __APP_VERSION__
            </div>
```

With:
```html
            <div class="btn-row">
                <button class="btn-blood btn-blood-ghost" @click="startDemo()">
                    Start Demo
                </button>
            </div>

            <div class="btn-row--sm">
                <button class="btn-blood btn-blood-ghost" @click="goToContact()">
                    Contact
                </button>
            </div>

            <div class="app-version">
                __APP_VERSION__
            </div>
```

**Step 2: Replace the contact screen inline styles**

Find and replace in the `<!-- Contact Screen -->` section:

Fragment 1 — replace the inner form-stack div opening:
```html
                <div class="form-stack" style="margin-top: 0;">
```
With:
```html
                <div class="form-stack form-stack--no-top">
```

Fragment 2 — replace the error div:
```html
                        <div x-show="contactStatus === 'error'"
                             style="text-align:center; color: var(--blood-bright); font-family: 'Rajdhani', sans-serif; font-size: 15px; letter-spacing: 1px;">
                            Something went wrong. Please try again.
                        </div>
```
With:
```html
                        <div x-show="contactStatus === 'error'" class="contact-error">
                            Something went wrong. Please try again.
                        </div>
```

Fragment 3 — replace the success div:
```html
                <div x-show="contactStatus === 'success'"
                     style="text-align:center; padding: 24px 0; color: var(--success); font-family: 'Bebas Neue', sans-serif; font-size: 22px; letter-spacing: 4px; border: 1px solid var(--success); background: rgba(34,197,94,0.05);">
                    Message Sent
                    <div style="font-family: 'Rajdhani', sans-serif; font-size: 15px; letter-spacing: 1px; margin-top: 6px; color: var(--text-dim);">
                        We'll get back to you if you left an email.
                    </div>
                </div>
```
With:
```html
                <div x-show="contactStatus === 'success'" class="contact-success">
                    Message Sent
                    <div class="contact-success-sub">
                        We'll get back to you if you left an email.
                    </div>
                </div>
```

Fragment 4 — replace the contact back button wrapper:
```html
            <div style="margin-top: 16px;">
                <button class="btn-blood btn-blood-ghost" @click="screen = 'landing'">
                    &larr; Back
                </button>
            </div>
```
With:
```html
            <div class="btn-row">
                <button class="btn-blood btn-blood-ghost" @click="screen = 'landing'">
                    &larr; Back
                </button>
            </div>
```

**Step 3: Verify no remaining static `style=""` attributes**

Run: `grep -n ' style="' src/iron_verdict/static/index.html`

Expected output — only these two lines (both are allowed: one is the botcheck trap, the other is not present in the current file):
```
142:            <input type="checkbox" name="botcheck" style="display:none" tabindex="-1" autocomplete="off">
```
No other matches. (Dynamic `:style=` bindings are fine — grep for `style="` not `:style=`.)

**Step 4: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "style: extract landing and contact inline styles to CSS classes"
```

---

### Task 5: Create js/demo.js

**Files:**
- Create: `src/iron_verdict/static/js/demo.js`

**Step 1: Create the file with this exact content**

```js
export const demoMethods = {
    startDemo() {
        this.demoRunning = false;
        this.screen = 'demo-intro';
    },

    async launchDemo() {
        try {
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: 'Demo' })
            });
            if (!response.ok) {
                alert('Failed to create session. Please try again.');
                return;
            }
            const data = await response.json();
            const sessionCode = data.session_code;

            const specs = this.getWindowSpecs(sessionCode);
            const timestamp = Date.now();
            window.open(specs.leftJudge.url,   `leftJudge_${timestamp}`,   specs.leftJudge.params);
            window.open(specs.centerJudge.url, `centerJudge_${timestamp}`, specs.centerJudge.params);
            window.open(specs.rightJudge.url,  `rightJudge_${timestamp}`,  specs.rightJudge.params);
            window.open(specs.display.url,     `display_${timestamp}`,     specs.display.params);

            this.demoRunning = true;
        } catch (error) {
            alert('Failed to start demo. Please try again.');
            console.error('Demo mode error:', error);
        }
    },

    getWindowSpecs(sessionCode) {
        const sw = window.screen.width;
        const sh = window.screen.height;
        const jw = Math.floor(sw / 3);
        const jh = Math.floor(sh / 2);
        const dw = sw;
        const dh = Math.floor(sh / 2);
        const sl = window.screen.availLeft ?? 0;
        const st = window.screen.availTop ?? 0;

        const baseUrl = `${window.location.origin}/?code=${sessionCode}`;

        return {
            leftJudge:   { url: `${baseUrl}&demo=left_judge`,   params: `width=${jw},height=${jh},left=${sl},top=${st}` },
            centerJudge: { url: `${baseUrl}&demo=center_judge`, params: `width=${jw},height=${jh},left=${sl+jw},top=${st}` },
            rightJudge:  { url: `${baseUrl}&demo=right_judge`,  params: `width=${jw},height=${jh},left=${sl+2*jw},top=${st}` },
            display:     { url: `${baseUrl}&demo=display`,      params: `width=${dw},height=${dh},left=${sl},top=${st+jh}` }
        };
    },

    returnToLandingFromDemo() {
        this.demoRunning = false;
        this.screen = 'landing';
    },
};
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/js/demo.js
git commit -m "refactor: extract demo methods to demo.js mixin"
```

---

### Task 6: Create js/handlers.js

**Files:**
- Create: `src/iron_verdict/static/js/handlers.js`

**Step 1: Create the file with this exact content**

```js
import { stopTimer } from './timer.js';

export function handleJoinSuccess(app, message) {
    app.isHead = message.is_head;
    app.sessionName = message.session_state?.name || '';
    app.screen = app.role === 'display' ? 'display' : 'judge';
    if (app.isHead) {
        app.requireReasons = message.session_state?.settings?.require_reasons ?? false;
        app.saveSettings();
    }
    const trms = message.session_state?.time_remaining_ms;
    if (trms > 0) {
        app.startTimerCountdown(trms);
    }
}

export function handleJoinError(app, message) {
    app.ws.close();
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Failed to join session: ${sanitizedMessage}`);
}

export function handleError(app, message) {
    const sanitizedMessage = document.createTextNode(message.message).textContent;
    alert(`Error: ${sanitizedMessage}`);
}

export function handleShowResults(app, message) {
    app.resultsShown = true;
    stopTimer();
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

export function handleResetForNextLift(app, message) {
    clearTimeout(app._phaseTimer1);
    app.resetVoting();
    stopTimer();
    app.timerDisplay = '60';
    app.timerExpired = false;
    if (app.role === 'display') {
        app.displayVotes = { left: null, center: null, right: null };
        app.displayReasons = { left: null, center: null, right: null };
        app.displayPhase = 'idle';
        app.displayStatus = 'Waiting for judges...';
    }
}

export function handleTimerStart(app, message) {
    app.startTimerCountdown(message.time_remaining_ms);
}

export function handleTimerReset(app, message) {
    stopTimer();
    app.timerDisplay = '60';
    app.timerExpired = false;
}

export function handleSessionEnded(app, message) {
    alert('Session ended');
    app.ws.close();
    app.isDemo = false;
    app.screen = 'landing';
}

export function handleSettingsUpdate(app, message) {
    if (message.showExplanations !== undefined) {
        app.showExplanations = message.showExplanations;
    }
    if (message.liftType !== undefined) {
        app.liftType = message.liftType;
    }
    if (message.requireReasons !== undefined) {
        app.requireReasons = message.requireReasons;
    }
}
```

**Step 2: Commit**

```bash
git add src/iron_verdict/static/js/handlers.js
git commit -m "refactor: extract WebSocket message handlers to handlers.js"
```

---

### Task 7: Refactor js/app.js

**Files:**
- Modify: `src/iron_verdict/static/js/app.js`

**Step 1: Replace the entire file with the following**

Key changes from the original:
- Updated imports: add demo.js and handlers.js; drop `stopTimer` from timer import (now only needed in handlers.js)
- Spread `...demoMethods` into the returned object
- Remove the 4 demo methods (startDemo, launchDemo, getWindowSpecs, returnToLandingFromDemo)
- Replace `handleMessage` body with a dispatch table

```js
import { CARD_REASONS, ROLE_DISPLAY_NAMES } from './constants.js';
import { startTimerCountdown } from './timer.js';
import { createWebSocket } from './websocket.js';
import { demoMethods } from './demo.js';
import {
    handleJoinSuccess,
    handleJoinError,
    handleError,
    handleShowResults,
    handleResetForNextLift,
    handleTimerStart,
    handleTimerReset,
    handleSessionEnded,
    handleSettingsUpdate,
} from './handlers.js';

export function ironVerdictApp() {
    return {
        screen: 'landing',
        sessionCode: '',
        sessionName: '',
        newSessionName: '',
        isDemo: false,
        demoRunning: false,
        joinCode: '',
        role: '',
        isHead: false,
        ws: null,
        wsSend: null,
        connectionStatus: 'disconnected',
        selectedVote: null,
        voteLocked: false,
        resultsShown: false,
        timerDisplay: '60',
        timerExpired: false,
        displayVotes: { left: null, center: null, right: null },
        displayReasons: { left: null, center: null, right: null },
        displayStatus: 'Waiting for judges...',
        intentionalNavigation: false,
        showExplanations: false,
        requireReasons: false,
        selectedReason: null,
        showingReasonStep: false,
        liftType: 'squat',
        displayPhase: 'idle',
        displayShowExplanations: false,
        displayLiftType: 'squat',
        _phaseTimer1: null,
        judgeResultVotes: { left: null, center: null, right: null },
        judgeResultReasons: { left: null, center: null, right: null },
        contactName: '',
        contactEmail: '',
        contactMessage: '',
        contactStatus: 'idle',

        ...demoMethods,

        async createSession() {
            try {
                const response = await fetch('/api/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: this.newSessionName.trim() })
                });
                if (!response.ok) {
                    alert('Failed to create session. Please try again.');
                    return;
                }
                const data = await response.json();
                this.sessionCode = data.session_code;
                this.sessionName = this.newSessionName.trim();
                this.screen = 'role-select';
            } catch (error) {
                alert('Error creating session. Please check your connection.');
                console.error('Session creation error:', error);
            }
        },

        joinExistingSession() {
            if (this.joinCode) {
                this.sessionCode = this.joinCode.trim().toUpperCase();
                this.screen = 'role-select';
            }
        },

        joinSession(role) {
            this.role = role;
            const code = this.sessionCode || this.joinCode;
            this.sessionCode = code;
            this.connectionStatus = 'reconnecting';

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws`;

            const wsWrapper = createWebSocket(
                url,
                (message) => this.handleMessage(message),
                (error) => console.error('WebSocket error:', error),
                () => {},
                () => {
                    this.connectionStatus = 'connected';
                    this.wsSend({ type: 'join', session_code: code, role: role });
                },
                () => { this.connectionStatus = 'reconnecting'; }
            );

            this.ws = wsWrapper;
            this.wsSend = (data) => wsWrapper.send(data);
        },

        handleMessage(message) {
            const dispatch = {
                join_success:        handleJoinSuccess,
                join_error:          handleJoinError,
                error:               handleError,
                show_results:        handleShowResults,
                reset_for_next_lift: handleResetForNextLift,
                timer_start:         handleTimerStart,
                timer_reset:         handleTimerReset,
                session_ended:       handleSessionEnded,
                settings_update:     handleSettingsUpdate,
            };
            dispatch[message.type]?.(this, message);
        },

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

        lockVote() {
            if (this.canLockIn()) {
                this.voteLocked = true;
                this.wsSend({
                    type: 'vote_lock',
                    color: this.selectedVote,
                    reason: this.selectedVote !== 'white' ? this.selectedReason : null,
                });
            }
        },

        saveSettings() {
            if (!this.isHead) return;
            localStorage.setItem('showExplanations', this.showExplanations);
            localStorage.setItem('liftType', this.liftType);
            localStorage.setItem('requireReasons', this.requireReasons);
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.wsSend({
                    type: 'settings_update',
                    showExplanations: this.showExplanations,
                    liftType: this.liftType,
                    requireReasons: this.requireReasons
                });
            }
        },

        resetVoting() {
            this.selectedVote = null;
            this.voteLocked = false;
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
            this.judgeResultVotes = { left: null, center: null, right: null };
            this.judgeResultReasons = { left: null, center: null, right: null };
        },

        startTimer() {
            this.wsSend({ type: 'timer_start' });
        },

        resetTimer() {
            this.wsSend({ type: 'timer_reset' });
        },

        startTimerCountdown(timeRemainingMs) {
            startTimerCountdown(timeRemainingMs, (seconds, expired) => {
                this.timerDisplay = seconds;
                this.timerExpired = expired;
            });
        },

        nextLift() {
            this.wsSend({ type: 'next_lift' });
        },

        confirmEndSession() {
            if (confirm('Are you sure? This will disconnect all judges and the display')) {
                this.wsSend({ type: 'end_session_confirmed' });
            }
        },

        getRoleDisplayName() {
            return ROLE_DISPLAY_NAMES[this.role] || this.role;
        },

        isValidLift() {
            const whiteCount = Object.values(this.displayVotes).filter(c => c === 'white').length;
            return whiteCount >= 2;
        },

        returnToLanding() {
            this.intentionalNavigation = true;
            this.screen = 'landing';
            this.sessionCode = '';
            this.joinCode = '';
            this.isDemo = false;
            this.sessionName = '';
            this.newSessionName = '';
        },

        returnToRoleSelection() {
            this.intentionalNavigation = true;
            if (this.ws) {
                this.ws.close();
            }
            this.screen = 'role-select';
            this.selectedVote = null;
            this.voteLocked = false;
            this.resultsShown = false;
            this.selectedReason = null;
            this.showingReasonStep = false;
            startTimerCountdown(0, () => {});  // stop timer via zero-duration countdown
            this.timerDisplay = '60';
            this.timerExpired = false;
        },

        goToContact() {
            this.contactName = '';
            this.contactEmail = '';
            this.contactMessage = '';
            this.contactStatus = 'idle';
            this.screen = 'contact';
        },

        async submitContact() {
            this.contactStatus = 'loading';
            try {
                const res = await fetch('https://api.web3forms.com/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({
                        access_key: '2e92ea27-be19-4996-83c9-0b33fcb63419',
                        name: this.contactName,
                        email: this.contactEmail,
                        message: this.contactMessage,
                    })
                });
                const data = await res.json();
                this.contactStatus = data.success ? 'success' : 'error';
            } catch (_e) {
                this.contactStatus = 'error';
            }
        },

        init() {
            this.showExplanations = localStorage.getItem('showExplanations') === 'true';
            this.liftType = localStorage.getItem('liftType') || 'squat';
            this.requireReasons = localStorage.getItem('requireReasons') === 'true';

            const params = window._demoParams;
            if (params) {
                window._demoParams = null;
                this.sessionCode = params.code;
                this.joinCode = params.code;
                this.isDemo = true;
                setTimeout(() => this.joinSession(params.demo), 100);
            } else {
                this.screen = 'landing';
            }
        }
    };
}
```

> **Important:** `returnToRoleSelection` in the original called `stopTimer()` directly. Since `stopTimer` is no longer imported in app.js, replace with `startTimerCountdown(0, () => {})` which immediately invokes the callback at 0ms and clears any running interval — same effect.

**Step 2: Verify line count**

Run: `wc -l src/iron_verdict/static/js/app.js`

Expected: under 280 lines.

**Step 3: Commit**

```bash
git add src/iron_verdict/static/js/app.js
git commit -m "refactor: split app.js — extract demo and handler modules, dispatch table for handleMessage"
```

---

### Task 8: Final audit

**Step 1: Check all JS file line counts**

```bash
wc -l src/iron_verdict/static/js/*.js
```

Expected — all files under 300 lines:
```
  67  constants.js
  55  demo.js
  80  handlers.js
  34  init.js
 280  app.js     (approx)
  25  timer.js
  44  websocket.js
```

**Step 2: Verify no remaining static inline styles in index.html**

```bash
grep -n ' style="' src/iron_verdict/static/index.html
```

Expected: exactly one match — the botcheck input on line ~142.

**Step 3: Run the Python test suite to confirm no backend breakage**

```bash
pytest tests/ -v
```

Expected: all tests pass (the refactor is frontend-only).

**Step 4: Final commit if any fixups were needed**

```bash
git add -p
git commit -m "fix: frontend cleanup audit fixups"
```
