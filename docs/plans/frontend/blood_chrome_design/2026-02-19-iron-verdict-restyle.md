# Iron Verdict Restyle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename JudgeMe → Iron Verdict and apply the Blood & Chrome dark industrial design, preserving all Alpine.js/WebSocket logic unchanged.

**Architecture:** Pure frontend + CSP change. Full CSS replacement; HTML restructured with per-screen viewport wrappers. All JS, Alpine bindings, and WebSocket logic are untouched. CSP updated for Google Fonts CDN.

**Tech Stack:** FastAPI CSP middleware (`src/judgeme/main.py`), Alpine.js 3.14.1 (CDN), Bebas Neue + Rajdhani via Google Fonts CDN, single-file SPA (`src/judgeme/static/index.html`).

---

### Task 1: Set up worktree

**Files:**
- Run from: `c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme`

**Step 1: Create the feature worktree**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme" worktree add "../judgeme-iron-verdict" -b feature/iron-verdict-restyle
```

**Step 2: Reinstall editable package in worktree**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/pip.exe" install -e "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict"
```

All remaining tasks work in worktree at:
`c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict`

**Step 3: Verify tests pass in worktree (baseline)**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m pytest "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict/tests/" -q --tb=short
```
Expected: all pass.

---

### Task 2: Update CSP for Google Fonts

**Files:**
- Modify: `src/judgeme/main.py` (lines 48–55)
- Modify: `tests/test_main.py` (function `test_security_headers_on_root`)

**Step 1: Update `_CSP` in `main.py`**

Old:
```python
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' 'unsafe-eval'; "
    "connect-src 'self' ws: wss:; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'"
)
```

New:
```python
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' 'unsafe-eval'; "
    "connect-src 'self' ws: wss:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src 'self' https://fonts.gstatic.com"
)
```

**Step 2: Add assertions to `test_security_headers_on_root` in `tests/test_main.py`**

After the existing assertions (after line `assert "'unsafe-eval'" in csp`), add:
```python
assert "fonts.googleapis.com" in csp
assert "fonts.gstatic.com" in csp
```

**Step 3: Run the test**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m pytest "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict/tests/test_main.py::test_security_headers_on_root" -v
```
Expected: PASS.

**Step 4: Commit**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict" add src/judgeme/main.py tests/test_main.py
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict" commit -m "feat: allow Google Fonts in CSP for Iron Verdict restyle"
```

---

### Task 3: Replace `<head>` metadata and fonts link

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Update title and add Google Fonts link**

In `index.html`, replace:
```html
<title>JudgeMe - Powerlifting Judging</title>
```
With:
```html
<title>Iron Verdict — Powerlifting Judging</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
```

(Insert after `<meta name="viewport" ...>` and before the inline `<script>` block.)

No commit yet — continue to Task 4.

---

### Task 4: Replace the entire `<style>` block

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Remove old CSS**

Delete everything from `<style>` through `</style>` (the entire CSS block, approximately lines 25–638 in the original file).

**Step 2: Insert new CSS**

Insert the following `<style>` block in its place (between the Google Fonts `<link>` and the closing `</head>`):

```html
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
        --bg-void: #0A0A0A;
        --bg-surface: #141414;
        --bg-raised: #1E1E1E;
        --chrome-dark: #404040;
        --blood: #B91C1C;
        --blood-bright: #EF4444;
        --blood-glow: rgba(185,28,28,0.3);
        --text-chrome: #D4D4D4;
        --text-dim: #6B6B6B;
        --vote-red: #DC2626;
        --vote-blue: #2563EB;
        --vote-yellow: #EAB308;
        --success: #22C55E;
    }

    body {
        font-family: 'Rajdhani', sans-serif;
        background: var(--bg-void);
        color: var(--text-chrome);
        min-height: 100vh;
    }

    /* ===== CHROME GRADIENT TEXT ===== */
    .chrome-text {
        background: linear-gradient(180deg, #FFFFFF 0%, #C0C0C0 40%, #808080 60%, #A0A0A0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* ===== ANGULAR CUT CORNERS ===== */
    .cut-corner {
        clip-path: polygon(
            12px 0%, 100% 0%,
            100% calc(100% - 12px),
            calc(100% - 12px) 100%,
            0% 100%,
            0% 12px
        );
    }

    .cut-corner-sm {
        clip-path: polygon(
            8px 0%, 100% 0%,
            100% calc(100% - 8px),
            calc(100% - 8px) 100%,
            0% 100%,
            0% 8px
        );
    }

    /* ===== LANDING ===== */
    .landing-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        padding: 20px;
        background: linear-gradient(135deg, var(--bg-void) 60%, rgba(185,28,28,0.05) 100%);
        position: relative;
    }

    .landing-wrap::before {
        content: '';
        position: absolute;
        top: 0; right: 0;
        width: 200px; height: 100%;
        background: linear-gradient(135deg, transparent 48%, rgba(185,28,28,0.03) 49%,
                    rgba(185,28,28,0.03) 51%, transparent 52%);
    }

    .landing-panel {
        width: 100%;
        max-width: 440px;
        background: var(--bg-surface);
        border: 1px solid var(--chrome-dark);
        padding: 40px 32px;
        position: relative;
    }

    .landing-panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--blood), var(--blood-bright), var(--blood));
    }

    .brand-iron {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 64px;
        letter-spacing: 10px;
        line-height: 1;
        text-align: center;
    }

    .brand-verdict-sub {
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 10px;
        text-transform: uppercase;
        color: var(--blood-bright);
        text-align: center;
        margin-top: -2px;
    }

    .chrome-input {
        width: 100%;
        padding: 14px 16px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 17px;
        font-weight: 600;
        letter-spacing: 1px;
        background: var(--bg-void);
        border: 1px solid var(--chrome-dark);
        border-left: 3px solid var(--blood);
        color: var(--text-chrome);
        transition: all 0.2s;
    }

    .chrome-input::placeholder { color: var(--text-dim); }
    .chrome-input:focus {
        outline: none;
        border-color: var(--blood);
        box-shadow: 0 0 0 1px var(--blood-glow);
    }

    .btn-blood {
        width: 100%;
        padding: 16px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 20px;
        letter-spacing: 4px;
        border: none;
        cursor: pointer;
        transition: all 0.15s;
        text-transform: uppercase;
    }

    .btn-blood:active:not(:disabled) { transform: scale(0.98); }

    .btn-blood-primary {
        background: linear-gradient(180deg, #DC2626 0%, #991B1B 100%);
        color: #fff;
        box-shadow: 0 4px 20px var(--blood-glow);
    }

    .btn-blood-primary:hover:not(:disabled) {
        box-shadow: 0 6px 30px rgba(185,28,28,0.5);
    }

    .btn-blood-secondary {
        background: var(--bg-raised);
        color: var(--text-chrome);
        border: 1px solid var(--chrome-dark);
    }

    .btn-blood-secondary:hover:not(:disabled) {
        border-color: var(--blood);
    }

    .btn-blood-ghost {
        background: transparent;
        color: var(--text-dim);
        border: 1px solid #2a2a2a;
        font-size: 16px;
        letter-spacing: 3px;
    }

    .btn-blood-ghost:hover:not(:disabled) {
        color: var(--text-chrome);
        border-color: var(--chrome-dark);
    }

    button:disabled { opacity: 0.4; cursor: not-allowed; }

    .slash-divider {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 12px 0;
        color: var(--text-dim);
        font-size: 13px;
        letter-spacing: 4px;
        text-transform: uppercase;
    }

    .slash-divider::before, .slash-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--chrome-dark), transparent);
    }

    .form-stack { display: flex; flex-direction: column; gap: 12px; margin-top: 32px; }

    /* ===== ROLE SELECTION ===== */
    .role-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        padding: 20px;
        background: var(--bg-void);
    }

    .role-panel {
        width: 100%;
        max-width: 500px;
        background: var(--bg-surface);
        border: 1px solid var(--chrome-dark);
        padding: 32px;
        position: relative;
    }

    .role-panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--blood), var(--blood-bright), var(--blood));
    }

    .role-heading {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 32px;
        letter-spacing: 4px;
        text-align: center;
    }

    .session-tag {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 18px;
        letter-spacing: 3px;
        text-align: center;
        margin: 16px 0 24px;
        color: var(--text-dim);
    }

    .session-tag .code {
        color: var(--blood-bright);
        font-size: 22px;
        cursor: pointer;
        text-decoration: underline;
    }

    .role-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
    }

    .role-btn {
        padding: 24px 8px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 18px;
        letter-spacing: 2px;
        text-align: center;
        background: var(--bg-raised);
        border: 1px solid var(--chrome-dark);
        color: var(--text-chrome);
        cursor: pointer;
        transition: all 0.2s;
        line-height: 1.3;
        width: 100%;
    }

    .role-btn:hover {
        border-color: var(--blood);
        box-shadow: inset 0 0 20px rgba(185,28,28,0.1);
    }

    .role-btn .sub {
        font-family: 'Rajdhani', sans-serif;
        font-size: 12px;
        color: var(--text-dim);
        display: block;
        margin-top: 2px;
        letter-spacing: 1px;
    }

    .role-display-btn {
        grid-column: 1 / -1;
        margin-top: 6px;
        background: linear-gradient(180deg, #DC2626 0%, #991B1B 100%);
        color: #fff;
        border-color: var(--blood);
    }

    /* ===== JUDGE SCREEN ===== */
    .judge-wrap {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        padding: 10px;
        gap: 10px;
        background: var(--bg-void);
    }

    .judge-bar {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        padding: 10px 16px;
        background: var(--bg-surface);
        border-bottom: 2px solid var(--blood);
    }

    .judge-role-label {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 18px;
        letter-spacing: 3px;
        color: var(--blood-bright);
    }

    .judge-timer {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 60px;
        color: var(--text-chrome);
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }

    .judge-timer.expired {
        color: var(--vote-red);
        text-shadow: 0 0 20px var(--blood-glow);
        animation: pulse-red 1s ease infinite;
    }

    @keyframes pulse-red {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    .judge-code {
        text-align: right;
        font-size: 14px;
        color: var(--text-dim);
        letter-spacing: 1px;
    }

    .judge-code .code-link {
        color: var(--blood-bright);
        cursor: pointer;
        text-decoration: underline;
    }

    .vote-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        flex: 1;
        max-height: 420px;
    }

    .vote-btn {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 32px;
        letter-spacing: 5px;
        border: 2px solid transparent;
        cursor: pointer;
        transition: all 0.12s;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 110px;
        position: relative;
        overflow: hidden;
        width: 100%;
    }

    .vote-btn::before {
        content: '';
        position: absolute;
        top: -50%; right: -50%;
        width: 100%; height: 200%;
        background: linear-gradient(135deg, transparent 48%, rgba(255,255,255,0.04) 49%, transparent 51%);
        pointer-events: none;
    }

    .vote-btn.selected {
        transform: scale(0.96);
        border-color: #fff !important;
        box-shadow: inset 0 0 30px rgba(255,255,255,0.1);
    }

    .vote-white {
        background: linear-gradient(180deg, #F0F0F0 0%, #C8C8C8 100%);
        color: #0A0A0A;
        border-color: #888;
    }

    .vote-red {
        background: linear-gradient(180deg, #EF4444 0%, #991B1B 100%);
        color: #fff;
    }

    .vote-blue {
        background: linear-gradient(180deg, #3B82F6 0%, #1E40AF 100%);
        color: #fff;
    }

    .vote-yellow {
        background: linear-gradient(180deg, #FBBF24 0%, #B45309 100%);
        color: #0A0A0A;
    }

    .lock-btn {
        width: 100%;
        padding: 20px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 26px;
        letter-spacing: 6px;
        background: linear-gradient(180deg, var(--success) 0%, #15803D 100%);
        color: #fff;
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 20px rgba(34,197,94,0.3);
    }

    .locked-status {
        text-align: center;
        padding: 16px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: 20px;
        letter-spacing: 4px;
        color: var(--success);
        border: 1px solid var(--success);
        background: rgba(34,197,94,0.05);
    }

    .head-section {
        border-top: 2px solid var(--chrome-dark);
        padding-top: 14px;
    }

    .head-title {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 16px;
        letter-spacing: 4px;
        color: var(--text-dim);
        margin-bottom: 10px;
    }

    .head-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .head-grid .btn-blood { font-size: 16px; padding: 12px; letter-spacing: 2px; }

    .settings-bar {
        display: flex;
        align-items: center;
        gap: 14px;
        flex-wrap: wrap;
        margin-top: 10px;
        padding: 8px 12px;
        border: 1px solid #2a2a2a;
        background: var(--bg-surface);
    }

    .settings-bar label {
        font-size: 14px;
        color: var(--text-dim);
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
    }

    .settings-bar select {
        padding: 5px 8px;
        background: var(--bg-void);
        border: 1px solid #2a2a2a;
        color: var(--text-chrome);
        font-family: 'Rajdhani', sans-serif;
        font-size: 14px;
        font-weight: 600;
    }

    /* ===== DISPLAY SCREEN ===== */
    .display-full {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        background:
            radial-gradient(circle at 50% 80%, rgba(185,28,28,0.06) 0%, transparent 50%),
            var(--bg-void);
        padding: 40px;
        gap: 36px;
        position: relative;
        overflow: hidden;
    }

    .display-full::before, .display-full::after {
        content: '';
        position: absolute;
        width: 2px;
        height: 120%;
        background: rgba(185,28,28,0.08);
        transform: rotate(15deg);
    }
    .display-full::before { left: 10%; }
    .display-full::after { right: 10%; }

    .display-tag {
        position: absolute;
        top: 16px;
        right: 20px;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        font-size: 18px;
        letter-spacing: 2px;
        color: var(--text-dim);
    }

    .display-timer-big {
        font-family: 'Bebas Neue', sans-serif;
        font-size: min(30vw, 300px);
        color: var(--text-chrome);
        line-height: 1;
        font-variant-numeric: tabular-nums;
        text-shadow: 0 0 60px rgba(255,255,255,0.03);
    }

    .display-timer-big.expired {
        color: var(--vote-red);
        text-shadow: 0 0 80px var(--blood-glow);
    }

    .display-lights {
        display: flex;
        gap: 40px;
    }

    .display-orb {
        width: min(20vw, 200px);
        height: min(20vw, 200px);
        border-radius: 50%;
        background: radial-gradient(circle at 40% 40%, #2a2a2a, #141414);
        border: 3px solid var(--chrome-dark);
        transition: all 0.3s;
        box-shadow: inset 0 4px 12px rgba(0,0,0,0.5);
    }

    .display-orb.white {
        background: radial-gradient(circle at 35% 35%, #FFFFFF, #B8B8B8);
        border-color: #999;
        box-shadow: 0 0 50px rgba(255,255,255,0.3), 0 0 100px rgba(255,255,255,0.1);
    }
    .display-orb.red {
        background: radial-gradient(circle at 35% 35%, #EF4444, #7F1D1D);
        border-color: #DC2626;
        box-shadow: 0 0 50px rgba(220,38,38,0.4), 0 0 100px rgba(220,38,38,0.15);
    }
    .display-orb.blue {
        background: radial-gradient(circle at 35% 35%, #3B82F6, #1E3A8A);
        border-color: #2563EB;
        box-shadow: 0 0 50px rgba(59,130,246,0.4), 0 0 100px rgba(59,130,246,0.15);
    }
    .display-orb.yellow {
        background: radial-gradient(circle at 35% 35%, #FBBF24, #78350F);
        border-color: #EAB308;
        box-shadow: 0 0 50px rgba(251,191,36,0.4), 0 0 100px rgba(251,191,36,0.15);
    }

    .display-status {
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        font-size: 22px;
        letter-spacing: 6px;
        text-transform: uppercase;
        color: var(--text-dim);
    }

    .display-verdict {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 20px;
        width: 100%;
        max-width: 800px;
    }

    .verdict-stamp {
        font-family: 'Bebas Neue', sans-serif;
        font-size: min(7vw, 60px);
        letter-spacing: 8px;
        padding: 10px 48px;
    }

    .verdict-stamp.valid {
        color: var(--success);
        border: 3px solid var(--success);
        box-shadow: 0 0 30px rgba(34,197,94,0.15);
    }

    .verdict-stamp.invalid {
        color: var(--blood-bright);
        border: 3px solid var(--blood);
        box-shadow: 0 0 30px var(--blood-glow);
    }

    .reason-card {
        width: 100%;
        overflow: hidden;
        border: 1px solid var(--chrome-dark);
    }

    .reason-card-header {
        padding: 8px 20px;
        font-family: 'Bebas Neue', sans-serif;
        font-size: min(3.5vw, 28px);
        letter-spacing: 4px;
        color: #fff;
    }

    .reason-card-header.red   { background: var(--vote-red); }
    .reason-card-header.blue  { background: var(--vote-blue); }
    .reason-card-header.yellow { background: var(--vote-yellow); color: #0A0A0A; }

    .reason-card-body {
        padding: 12px 20px 12px 44px;
        background: var(--bg-surface);
        list-style: disc;
    }

    .reason-card-body li {
        padding: 3px 0;
        font-family: 'Rajdhani', sans-serif;
        font-size: min(2.8vw, 26px);
        font-weight: 600;
        color: var(--text-chrome);
        line-height: 1.4;
    }

    .hidden { display: none !important; }

    @media (max-width: 600px) {
        .judge-timer { font-size: 48px; }
        .vote-btn { font-size: 24px; min-height: 90px; }
        .role-grid { grid-template-columns: 1fr; }
    }
</style>
```

No commit yet — continue to Task 5.

---

### Task 5: Replace `<body>` HTML

**Files:**
- Modify: `src/judgeme/static/index.html`

**Step 1: Replace body HTML**

Remove everything from `<body>` up to (but NOT including) the `<script>` tag. Replace with:

```html
<body>
<div x-data="judgemeApp()">

    <!-- Landing Screen -->
    <div class="landing-wrap" x-show="screen === 'landing'">
        <div class="landing-panel cut-corner">
            <div class="brand-iron chrome-text">Iron Verdict</div>
            <div class="brand-verdict-sub">Powerlifting Judging</div>

            <div class="form-stack">
                <input class="chrome-input" placeholder="Session name (e.g. Platform A)"
                       x-model="newSessionName" @keyup.enter="createSession()">
                <button class="btn-blood btn-blood-primary cut-corner-sm"
                        @click="createSession()" :disabled="!newSessionName.trim()">
                    Create New Session
                </button>

                <div class="slash-divider">or</div>

                <input class="chrome-input" placeholder="Enter 6-character session code"
                       x-model="joinCode" @keyup.enter="joinExistingSession()">
                <button class="btn-blood btn-blood-secondary cut-corner-sm"
                        @click="joinExistingSession()">
                    Join Session
                </button>
            </div>

            <div style="margin-top: 16px;">
                <button class="btn-blood btn-blood-ghost" @click="startDemo()">
                    Start Demo
                </button>
            </div>
        </div>
    </div>

    <!-- Role Selection Screen -->
    <div class="role-wrap" x-show="screen === 'role-select'">
        <div class="role-panel cut-corner">
            <div class="role-heading chrome-text">Select Role</div>
            <div class="session-tag">
                Session: <span class="code" @click="returnToLanding()" x-text="sessionCode"></span>
            </div>

            <div class="role-grid">
                <button class="role-btn cut-corner-sm" @click="joinSession('left_judge')">
                    Left<br>Judge
                </button>
                <button class="role-btn cut-corner-sm" @click="joinSession('center_judge')">
                    Center<br>Judge<span class="sub">(Head)</span>
                </button>
                <button class="role-btn cut-corner-sm" @click="joinSession('right_judge')">
                    Right<br>Judge
                </button>
                <button class="role-btn role-display-btn cut-corner-sm" @click="joinSession('display')">
                    Display Screen
                </button>
            </div>
        </div>
    </div>

    <!-- Judge Screen -->
    <div class="judge-wrap" x-show="screen === 'judge'">
        <div class="judge-bar">
            <div class="judge-role-label" x-text="getRoleDisplayName()"></div>
            <div class="judge-timer" :class="timerExpired && 'expired'" x-text="timerDisplay"></div>
            <div class="judge-code">
                <span class="code-link" @click="returnToRoleSelection()" x-text="sessionCode"></span>
            </div>
        </div>

        <div class="vote-grid" :style="voteLocked ? 'opacity:0.35;pointer-events:none' : ''">
            <button class="vote-btn vote-white cut-corner-sm"
                    :class="selectedVote === 'white' && 'selected'"
                    @click="selectVote('white')" :disabled="voteLocked">
                WHITE
            </button>
            <button class="vote-btn vote-red cut-corner-sm"
                    :class="selectedVote === 'red' && 'selected'"
                    @click="selectVote('red')" :disabled="voteLocked">
                RED
            </button>
            <button class="vote-btn vote-blue cut-corner-sm"
                    :class="selectedVote === 'blue' && 'selected'"
                    @click="selectVote('blue')" :disabled="voteLocked">
                BLUE
            </button>
            <button class="vote-btn vote-yellow cut-corner-sm"
                    :class="selectedVote === 'yellow' && 'selected'"
                    @click="selectVote('yellow')" :disabled="voteLocked">
                YELLOW
            </button>
        </div>

        <button class="lock-btn cut-corner-sm"
                x-show="selectedVote && !voteLocked"
                @click="lockVote()">
            LOCK IN
        </button>

        <div class="locked-status" x-show="voteLocked">
            &#10003; Vote Locked &#8212; <span x-text="selectedVote?.toUpperCase()"></span>
        </div>

        <div class="head-section" x-show="isHead">
            <div class="head-title">Head Judge Controls</div>
            <div class="head-grid">
                <button class="btn-blood btn-blood-primary cut-corner-sm"
                        @click="startTimer()">Start Timer</button>
                <button class="btn-blood btn-blood-secondary cut-corner-sm"
                        @click="resetTimer()">Reset Timer</button>
                <button class="btn-blood btn-blood-primary cut-corner-sm"
                        @click="nextLift()" :disabled="!resultsShown">Next Lift</button>
                <button class="btn-blood btn-blood-ghost"
                        @click="confirmEndSession()">End Session</button>
            </div>
            <div class="settings-bar">
                <label>
                    <input type="checkbox" x-model="showExplanations" @change="saveSettings()">
                    Show rule explanations
                </label>
                <select x-model="liftType" @change="saveSettings()">
                    <option value="squat">Squat</option>
                    <option value="bench">Bench Press</option>
                    <option value="deadlift">Deadlift</option>
                </select>
            </div>
        </div>
    </div>

    <!-- Display Screen: shows sessionName only — sessionCode intentionally omitted (C3) -->
    <div class="display-full" x-show="screen === 'display'">
        <div class="display-tag">
            <span x-show="!isDemo" x-text="sessionName"></span>
            <span x-show="isDemo">DEMO</span>
        </div>

        <div class="display-timer-big" :class="timerExpired && 'expired'" x-text="timerDisplay"></div>

        <!-- Phase 1 & idle: Vote orbs -->
        <div class="display-lights" x-show="displayPhase === 'votes' || displayPhase === 'idle'">
            <div class="display-orb" :class="displayVotes.left"></div>
            <div class="display-orb" :class="displayVotes.center"></div>
            <div class="display-orb" :class="displayVotes.right"></div>
        </div>

        <!-- Phase 2: Explanation panel -->
        <div class="display-verdict" x-show="displayPhase === 'explanation'">
            <div class="verdict-stamp"
                 :class="isValidLift() ? 'valid' : 'invalid'"
                 x-text="isValidLift() ? 'Good Lift' : 'No Lift'"></div>
            <template x-for="color in getInvalidColors()" :key="color">
                <div class="reason-card">
                    <div class="reason-card-header" :class="color"
                         x-text="color.toUpperCase() + ' CARD'"></div>
                    <ul class="reason-card-body">
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

Keep the existing `<script>` block and closing `</body></html>` unchanged.

**Step 2: Run all tests**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m pytest "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict/tests/" -q --tb=short
```
Expected: all pass.

**Step 3: Commit**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict" add src/judgeme/static/index.html
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict" commit -m "feat: restyle app as Iron Verdict with Blood & Chrome design"
```

---

### Task 6: Final verification and PR

**Step 1: Run full test suite one more time**

```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m pytest "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict/tests/" -q --tb=short
```
Expected: all pass.

**Step 2: Manual smoke-test in browser**

Start the server from the worktree:
```bash
"c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme/.venv/Scripts/python.exe" -m uvicorn judgeme.main:app --reload --app-dir "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict/src"
```

Open `http://localhost:8000` and verify:
- [ ] Black background, "IRON VERDICT" in chrome gradient text, red accent line at top of card
- [ ] Cut-corner shapes on panel and buttons
- [ ] Bebas Neue font loads (tall condensed caps)
- [ ] Create session → role select screen renders correctly
- [ ] Judge screen: vote buttons show correct colors with cut corners
- [ ] Timer shows in large Bebas Neue
- [ ] Vote locked state: grid dims to 35% opacity, green locked-status bar appears
- [ ] Display screen: dark orbs with glow when votes revealed
- [ ] `Good Lift` / `No Lift` verdict stamp appears with correct color border

**Step 3: Create PR**

```bash
git -C "c:/Users/alexa/OneDrive/Dokumente/00_projects/judgeme-iron-verdict" push -u origin feature/iron-verdict-restyle
gh pr create --title "feat: Iron Verdict restyle — Blood & Chrome design" --body "$(cat <<'EOF'
## Summary
- Renames app from JudgeMe to Iron Verdict
- Applies Blood & Chrome dark industrial design (Bebas Neue + Rajdhani fonts, cut-corner shapes, blood red accents)
- Updates CSP to allow Google Fonts CDN
- All Alpine.js logic and WebSocket behaviour unchanged

## Test plan
- [ ] All existing tests pass
- [ ] Manual smoke-test: landing, role select, judge screen, display screen
- [ ] Verify on mobile (iPhone Safari)
EOF
)"
```
