# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the entire frontend (index.html) from basic styling to a comprehensive Dark Premium design system with consistent components across all screens (landing, judge interface, display).

**Architecture:** Single-file HTML + CSS + Alpine.js refactor. All styling defined in `<style>` block. Component system uses CSS classes (buttons, cards, inputs) and Alpine.js for interactivity. No JavaScript framework changes, no backend modifications.

**Tech Stack:** HTML5, CSS3 (custom properties), Alpine.js 3.x, FastAPI backend (unchanged)

**Result:** Completely redesigned `src/judgeme/static/index.html` with dark premium aesthetic, IPF-compliant vote colors, mobile-responsive layouts.

---

## Task 1: Design System - CSS Variables & Base Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (style block)

**Step 1: Define CSS custom properties for color palette**

Replace the existing minimal `<style>` section with a comprehensive design system. Add to `<style>`:

```css
:root {
    /* Primary Colors */
    --bg-primary: #0f1419;
    --bg-surface: #1a202c;
    --text-primary: #ffffff;
    --text-secondary: #a0aec0;
    --accent-gold: #d4af37;

    /* Status Colors */
    --status-success: #48bb78;
    --status-pending: #d4af37;
    --status-error: #f56565;

    /* Vote Colors (IPF Standard) */
    --vote-white: #ffffff;
    --vote-red: #ff4444;
    --vote-blue: #4444ff;
    --vote-yellow: #ffff44;

    /* Spacing */
    --spacing-xs: 8px;
    --spacing-sm: 12px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    --spacing-2xl: 40px;

    /* Transitions */
    --transition-fast: 200ms ease-in-out;
    --transition-normal: 300ms ease-in-out;
}
```

**Step 2: Reset and base styles**

Add after custom properties:

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    font-size: 16px;
}

main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
```

**Step 3: Commit**

```bash
cd .worktrees/feature-frontend-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add design system CSS variables and base styles"
```

---

## Task 2: Button Component System

**Files:**
- Modify: `src/judgeme/static/index.html` (style block)

**Step 1: Define button base styles**

Add to `<style>`:

```css
/* Button Base */
button {
    padding: var(--spacing-md) var(--spacing-lg);
    font-size: 16px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all var(--transition-normal);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-height: 48px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
}

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Primary Button (Gold) */
.btn-primary {
    background-color: var(--accent-gold);
    color: var(--bg-primary);
    font-weight: bold;
}

.btn-primary:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(212, 175, 55, 0.6);
    transform: translateY(-2px);
}

.btn-primary:active:not(:disabled) {
    border: 2px solid var(--accent-gold);
    box-shadow: 0 0 30px rgba(212, 175, 55, 0.8);
}

/* Secondary Button (Charcoal with Gold Border) */
.btn-secondary {
    background-color: var(--bg-surface);
    color: var(--text-primary);
    border: 2px solid var(--accent-gold);
}

.btn-secondary:hover:not(:disabled) {
    background-color: var(--accent-gold);
    color: var(--bg-primary);
}

.btn-secondary:active:not(:disabled) {
    box-shadow: inset 0 0 15px rgba(212, 175, 55, 0.4);
}

/* Danger Button (Red) */
.btn-danger {
    background-color: var(--status-error);
    color: var(--text-primary);
    font-weight: bold;
}

.btn-danger:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(245, 101, 101, 0.6);
    transform: translateY(-2px);
}

.btn-danger:active:not(:disabled) {
    border: 2px solid var(--status-error);
    box-shadow: 0 0 30px rgba(245, 101, 101, 0.8);
}

/* Full Width Button */
.btn-full {
    width: 100%;
}

/* Button Grid */
.btn-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
}

@media (max-width: 600px) {
    .btn-grid {
        gap: var(--spacing-sm);
    }

    button {
        min-height: 44px;
        padding: var(--spacing-sm) var(--spacing-md);
    }
}
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add comprehensive button component system"
```

---

## Task 3: Input & Card Component Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (style block)

**Step 1: Add input and card styles**

Add to `<style>`:

```css
/* Input Fields */
input[type="text"],
input[type="password"] {
    width: 100%;
    padding: var(--spacing-md);
    font-size: 16px;
    background-color: var(--bg-surface);
    color: var(--text-primary);
    border: 2px solid transparent;
    border-radius: 8px;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    margin-bottom: var(--spacing-md);
}

input[type="text"]::placeholder,
input[type="password"]::placeholder {
    color: var(--text-secondary);
}

input[type="text"]:focus,
input[type="password"]:focus {
    outline: none;
    border-color: var(--accent-gold);
    box-shadow: 0 0 15px rgba(212, 175, 55, 0.3);
}

/* Card Component */
.card {
    background-color: var(--bg-surface);
    border-radius: 8px;
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
    border: 1px solid rgba(212, 175, 55, 0.1);
    transition: all var(--transition-normal);
}

.card:hover {
    border-color: rgba(212, 175, 55, 0.3);
}

.card-sm {
    padding: var(--spacing-md);
}

.card-lg {
    padding: var(--spacing-2xl);
}

/* Vote Button Cards */
.vote-card {
    background-color: var(--bg-surface);
    border-radius: 8px;
    padding: var(--spacing-md);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100px;
    cursor: pointer;
    border: 3px solid transparent;
    transition: all var(--transition-fast);
}

.vote-card:hover:not(:disabled) {
    transform: scale(1.05);
}

.vote-card.selected {
    border-color: var(--accent-gold);
    box-shadow: 0 0 20px rgba(212, 175, 55, 0.5);
}

.vote-card button {
    width: 100%;
    height: 100%;
    min-height: 100px;
}

/* Divider */
.divider {
    height: 2px;
    background-color: var(--accent-gold);
    margin: var(--spacing-lg) 0;
    opacity: 0.3;
}

/* Status Message */
.status-msg {
    padding: var(--spacing-md);
    border-radius: 8px;
    text-align: center;
    font-weight: 600;
    margin: var(--spacing-md) 0;
}

.status-success {
    background-color: rgba(72, 187, 120, 0.15);
    color: var(--status-success);
    border: 1px solid var(--status-success);
}

.status-error {
    background-color: rgba(245, 101, 101, 0.15);
    color: var(--status-error);
    border: 1px solid var(--status-error);
}

.status-pending {
    background-color: rgba(212, 175, 55, 0.15);
    color: var(--accent-gold);
    border: 1px solid var(--accent-gold);
}
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add input, card, and status message component styles"
```

---

## Task 4: Layout & Container Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (style block)

**Step 1: Add layout and container styles**

Add to `<style>`:

```css
/* Containers */
.container {
    max-width: 600px;
    margin: 0 auto;
    padding: var(--spacing-md);
    width: 100%;
}

.container-lg {
    max-width: 1000px;
}

.container-full {
    max-width: 100%;
    padding: 0;
}

/* Flex & Grid Utilities */
.flex {
    display: flex;
}

.flex-center {
    display: flex;
    align-items: center;
    justify-content: center;
}

.flex-col {
    flex-direction: column;
}

.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.gap-sm {
    gap: var(--spacing-sm);
}

.gap-md {
    gap: var(--spacing-md);
}

.gap-lg {
    gap: var(--spacing-lg);
}

/* Spacing Utilities */
.mt-md { margin-top: var(--spacing-md); }
.mt-lg { margin-top: var(--spacing-lg); }
.mt-xl { margin-top: var(--spacing-xl); }
.mb-md { margin-bottom: var(--spacing-md); }
.mb-lg { margin-bottom: var(--spacing-lg); }
.mb-xl { margin-bottom: var(--spacing-xl); }
.p-md { padding: var(--spacing-md); }
.p-lg { padding: var(--spacing-lg); }

/* Text Utilities */
.text-center {
    text-align: center;
}

.text-uppercase {
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.text-secondary {
    color: var(--text-secondary);
}

.text-gold {
    color: var(--accent-gold);
}

.text-lg {
    font-size: 18px;
}

.text-xl {
    font-size: 24px;
}

.text-2xl {
    font-size: 32px;
}

.text-3xl {
    font-size: 48px;
}

.text-4xl {
    font-size: 64px;
}

.text-5xl {
    font-size: 120px;
}

/* Header Bar */
.header-bar {
    background-color: var(--bg-surface);
    padding: var(--spacing-md);
    border-bottom: 2px solid var(--accent-gold);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--spacing-md);
}

.header-info {
    display: flex;
    gap: var(--spacing-lg);
    align-items: center;
    flex-wrap: wrap;
}

.header-info strong {
    color: var(--accent-gold);
}

.session-code {
    cursor: pointer;
    text-decoration: underline;
    transition: color var(--transition-fast);
}

.session-code:hover {
    color: var(--accent-gold);
}
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add layout, container, and utility styles"
```

---

## Task 5: Typography & Hero Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (style block)

**Step 1: Add typography and hero section styles**

Add to `<style>`:

```css
/* Typography */
h1, h2, h3 {
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: var(--spacing-md);
}

h1 {
    font-size: 48px;
    line-height: 1.2;
}

h2 {
    font-size: 32px;
    line-height: 1.3;
}

h3 {
    font-size: 24px;
    line-height: 1.4;
}

p {
    margin-bottom: var(--spacing-md);
    color: var(--text-secondary);
    line-height: 1.8;
}

/* Hero Section */
.hero {
    background: linear-gradient(135deg, var(--bg-primary) 0%, #0a0e13 100%);
    padding: var(--spacing-2xl) var(--spacing-lg);
    text-align: center;
    position: relative;
    overflow: hidden;
    min-height: 400px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="rgba(212,175,55,0.05)"/><stop offset="1" stop-color="rgba(212,175,55,0)"/></linearGradient></defs><line x1="50" y1="50" x2="50" y2="150" stroke="url(%23g)" stroke-width="4"/><circle cx="50" cy="50" r="15" stroke="url(%23g)" stroke-width="2" fill="none"/><circle cx="50" cy="150" r="15" stroke="url(%23g)" stroke-width="2" fill="none"/></svg>') center/cover;
    opacity: 0.3;
    pointer-events: none;
}

.hero-content {
    position: relative;
    z-index: 1;
    max-width: 600px;
}

.hero h1 {
    color: var(--text-primary);
    margin-bottom: var(--spacing-sm);
}

.hero h1 .gold {
    color: var(--accent-gold);
}

.hero-subtitle {
    font-size: 18px;
    color: var(--text-secondary);
    margin-bottom: var(--spacing-lg);
}

.hero-value-prop {
    list-style: none;
    margin: var(--spacing-xl) 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
}

.hero-value-prop li {
    padding: var(--spacing-md);
    background-color: rgba(212, 175, 55, 0.05);
    border-left: 3px solid var(--accent-gold);
    text-align: left;
    color: var(--text-secondary);
}

.hero-cta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
    margin-top: var(--spacing-xl);
}

@media (max-width: 600px) {
    h1 {
        font-size: 32px;
    }

    h2 {
        font-size: 24px;
    }

    .hero {
        min-height: 300px;
        padding: var(--spacing-xl) var(--spacing-md);
    }

    .hero-cta {
        grid-template-columns: 1fr;
    }
}
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add typography and hero section styles"
```

---

## Task 6: Landing Page Structure & Styling

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML and style)

**Step 1: Update landing page HTML**

Replace the existing landing screen `<div>` with:

```html
<!-- Landing screen -->
<div x-show="screen === 'landing'" class="container-full">
    <div class="hero">
        <div class="hero-content">
            <h1>JUDGE<span class="gold">ME</span></h1>
            <p class="hero-subtitle">Professional Powerlifting Competition Judging</p>

            <ul class="hero-value-prop">
                <li>Real-time judging for sanctioned competitions</li>
                <li>Three independent judges, instant results</li>
                <li>No accounts. No setup. Just a 6-character code.</li>
            </ul>

            <div class="hero-cta">
                <button class="btn-primary btn-full" @click="createSession()">
                    Create Session
                </button>
                <button class="btn-secondary btn-full" @click="screen = 'role-select'">
                    Join Session
                </button>
            </div>

            <div style="margin-top: var(--spacing-xl); border-top: 1px solid rgba(212, 175, 55, 0.2); padding-top: var(--spacing-lg);">
                <p class="text-secondary" style="font-size: 14px; margin-bottom: var(--spacing-md);">Enter session code to join an existing competition:</p>
                <input type="text" x-model="joinCode" placeholder="Enter 6-character session code" style="margin-bottom: var(--spacing-md);">
                <button class="btn-secondary btn-full" @click="screen = 'role-select'" :disabled="joinCode.length === 0">
                    Join with Code
                </button>
            </div>

            <button class="btn-secondary btn-full mt-xl" @click="startDemo()" style="background: rgba(23, 162, 184, 0.2); border-color: #17a2b8;">
                Try Demo Mode
            </button>
        </div>
    </div>

    <div style="background-color: var(--bg-surface); padding: var(--spacing-xl); text-align: center; color: var(--text-secondary); font-size: 14px;">
        <p><strong style="color: var(--accent-gold);">Built for IPF-standard competitions</strong></p>
        <p style="margin-top: var(--spacing-sm);">No database. Sessions expire after 4 hours of inactivity.</p>
    </div>
</div>
```

**Step 2: Add landing page specific styles to `<style>`**

```css
/* Landing Page */
.landing-footer {
    background-color: var(--bg-surface);
    padding: var(--spacing-xl);
    text-align: center;
    color: var(--text-secondary);
}

.landing-footer p {
    margin: var(--spacing-sm) 0;
}

.landing-footer strong {
    color: var(--accent-gold);
}
```

**Step 3: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: redesign landing page with hero section and CTAs"
```

---

## Task 7: Role Selection Screen Redesign

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML)

**Step 1: Update role selection screen**

Replace the existing role-select `<div>` with:

```html
<!-- Role selection screen -->
<div x-show="screen === 'role-select'" class="container">
    <div class="card card-lg mt-xl">
        <h2 class="text-center mb-lg">Select Your Role</h2>
        <p class="text-center text-secondary mb-xl">Session: <span class="text-gold text-xl" style="cursor: pointer;" @click="screen = 'landing'">{{ sessionCode || joinCode }}</span></p>

        <div class="btn-grid">
            <button class="btn-primary" @click="joinSession('left_judge')">
                Left Judge
            </button>
            <button class="btn-primary" @click="joinSession('center_judge')">
                Center Judge
            </button>
            <button class="btn-primary" @click="joinSession('right_judge')">
                Right Judge
            </button>
            <button class="btn-secondary" @click="joinSession('display')">
                Display
            </button>
        </div>

        <button class="btn-secondary btn-full mt-lg" @click="screen = 'landing'">
            Back to Landing
        </button>
    </div>
</div>
```

**Step 2: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: redesign role selection screen with dark premium styling"
```

---

## Task 8: Judge Interface - Header & Voting Area

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML and style)

**Step 1: Add judge-specific styles to `<style>`**

```css
/* Judge Interface */
.judge-screen {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background-color: var(--bg-primary);
}

.judge-content {
    flex: 1;
    padding: var(--spacing-lg);
    display: flex;
    flex-direction: column;
}

.voting-area {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
    flex: 1;
    justify-content: center;
}

.vote-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-lg);
    margin: var(--spacing-lg) auto;
    width: 100%;
    max-width: 400px;
}

.vote-btn-white {
    background-color: var(--vote-white);
    color: var(--bg-primary);
    font-weight: bold;
}

.vote-btn-white:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
}

.vote-btn-white.selected {
    border: 3px solid var(--accent-gold);
    box-shadow: 0 0 30px rgba(212, 175, 55, 0.8);
}

.vote-btn-red {
    background-color: var(--vote-red);
    color: var(--text-primary);
    font-weight: bold;
}

.vote-btn-red:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(255, 68, 68, 0.6);
}

.vote-btn-red.selected {
    border: 3px solid var(--accent-gold);
    box-shadow: 0 0 30px rgba(212, 175, 55, 0.8);
}

.vote-btn-blue {
    background-color: var(--vote-blue);
    color: var(--text-primary);
    font-weight: bold;
}

.vote-btn-blue:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(68, 68, 255, 0.6);
}

.vote-btn-blue.selected {
    border: 3px solid var(--accent-gold);
    box-shadow: 0 0 30px rgba(212, 175, 55, 0.8);
}

.vote-btn-yellow {
    background-color: var(--vote-yellow);
    color: var(--bg-primary);
    font-weight: bold;
}

.vote-btn-yellow:hover:not(:disabled) {
    box-shadow: 0 0 20px rgba(255, 255, 68, 0.6);
}

.vote-btn-yellow.selected {
    border: 3px solid var(--accent-gold);
    box-shadow: 0 0 30px rgba(212, 175, 55, 0.8);
}

.lock-in-section {
    text-align: center;
    margin: var(--spacing-lg) 0;
}

.head-judge-section {
    border-top: 2px solid var(--accent-gold);
    padding-top: var(--spacing-lg);
    margin-top: var(--spacing-2xl);
}

.head-judge-controls {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
    margin-top: var(--spacing-lg);
}

@media (max-width: 600px) {
    .judge-content {
        padding: var(--spacing-md);
    }

    .vote-buttons {
        gap: var(--spacing-md);
    }

    .head-judge-controls {
        gap: var(--spacing-sm);
    }
}
```

**Step 2: Update judge screen HTML**

Replace the existing judge screen `<div>` with:

```html
<!-- Judge screen -->
<div x-show="screen === 'judge'" class="judge-screen">
    <div class="header-bar">
        <div class="header-info">
            <div>
                <strong>Session:</strong>
                <span class="session-code" @click="returnToRoleSelection()" :title="'Click to return'">{{ sessionCode }}</span>
            </div>
        </div>
        <div class="text-3xl" :style="timerExpired ? 'color: var(--status-error);' : 'color: var(--accent-gold);'">
            {{ timerDisplay }}
        </div>
    </div>

    <div class="judge-content">
        <div class="voting-area">
            <h2 class="text-center mb-lg">Make Your Call</h2>

            <div class="vote-buttons">
                <button
                    @click="selectVote('white')"
                    :disabled="voteLocked"
                    :class="['btn-primary', 'vote-btn-white', { selected: selectedVote === 'white' }]">
                    White
                </button>
                <button
                    @click="selectVote('red')"
                    :disabled="voteLocked"
                    :class="['btn-primary', 'vote-btn-red', { selected: selectedVote === 'red' }]">
                    Red
                </button>
                <button
                    @click="selectVote('blue')"
                    :disabled="voteLocked"
                    :class="['btn-primary', 'vote-btn-blue', { selected: selectedVote === 'blue' }]">
                    Blue
                </button>
                <button
                    @click="selectVote('yellow')"
                    :disabled="voteLocked"
                    :class="['btn-primary', 'vote-btn-yellow', { selected: selectedVote === 'yellow' }]">
                    Yellow
                </button>
            </div>

            <div class="lock-in-section" x-show="selectedVote && !voteLocked">
                <button @click="lockVote()" class="btn-primary btn-full">
                    Lock In
                </button>
            </div>

            <div x-show="voteLocked" class="card card-sm status-success text-center">
                <strong>Your Vote:</strong> <span style="text-transform: uppercase;">{{ selectedVote }}</span>
                <br>
                <span style="font-size: 12px; opacity: 0.8;">(Locked)</span>
            </div>
        </div>

        <!-- Head judge controls -->
        <div x-show="isHead" class="head-judge-section">
            <h3>Head Judge Controls</h3>
            <div class="head-judge-controls">
                <button @click="startTimer()" class="btn-primary">Start Timer</button>
                <button @click="resetTimer()" class="btn-secondary">Reset Timer</button>
                <button @click="nextLift()" :disabled="!resultsShown" class="btn-secondary">Next Lift</button>
                <button @click="confirmEndSession()" class="btn-danger">End Session</button>
            </div>
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: redesign judge interface with dark premium styling and vote buttons"
```

---

## Task 9: Display Screen Redesign

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML and style)

**Step 1: Add display screen styles to `<style>`**

```css
/* Display Screen */
.display-screen {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background-color: var(--bg-primary);
}

.display-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: var(--spacing-2xl);
    text-align: center;
}

.display-timer {
    font-size: var(--text-5xl);
    font-weight: bold;
    margin-bottom: var(--spacing-2xl);
    min-height: 140px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.display-timer.expired {
    color: var(--status-error);
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.judge-lights {
    display: flex;
    justify-content: center;
    gap: var(--spacing-2xl);
    margin-bottom: var(--spacing-2xl);
    flex-wrap: wrap;
}

.judge-light {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    border: 4px solid rgba(212, 175, 55, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: bold;
    color: var(--bg-primary);
    text-transform: uppercase;
    letter-spacing: 1px;
    transition: all var(--transition-normal);
    background-color: #f5f5f5;
}

.judge-light.light-white {
    background-color: var(--vote-white);
    box-shadow: 0 0 40px rgba(255, 255, 255, 0.8);
}

.judge-light.light-red {
    background-color: var(--vote-red);
    color: white;
    box-shadow: 0 0 40px rgba(255, 68, 68, 0.8);
}

.judge-light.light-blue {
    background-color: var(--vote-blue);
    color: white;
    box-shadow: 0 0 40px rgba(68, 68, 255, 0.8);
}

.judge-light.light-yellow {
    background-color: var(--vote-yellow);
    box-shadow: 0 0 40px rgba(255, 255, 68, 0.8);
}

.display-status {
    font-size: var(--text-xl);
    color: var(--accent-gold);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

@media (max-width: 1200px) {
    .judge-light {
        width: 150px;
        height: 150px;
    }
}

@media (max-width: 768px) {
    .judge-light {
        width: 120px;
        height: 120px;
        font-size: 12px;
    }

    .judge-lights {
        gap: var(--spacing-lg);
    }

    .display-timer {
        font-size: 80px;
        margin-bottom: var(--spacing-lg);
    }
}

@media (max-width: 600px) {
    .judge-light {
        width: 100px;
        height: 100px;
        font-size: 10px;
    }

    .judge-lights {
        flex-direction: column;
        gap: var(--spacing-md);
    }

    .display-timer {
        font-size: 64px;
    }
}
```

**Step 2: Update display screen HTML**

Replace the existing display screen `<div>` with:

```html
<!-- Display screen -->
<div x-show="screen === 'display'" class="display-screen">
    <div class="header-bar">
        <div class="header-info">
            <div>
                <strong>Session:</strong>
                <span class="session-code" @click="returnToRoleSelection()" :title="'Click to return'">{{ sessionCode }}</span>
            </div>
        </div>
        <div class="text-2xl" :style="timerExpired ? 'color: var(--status-error);' : 'color: var(--accent-gold);'">
            {{ timerDisplay }}
        </div>
    </div>

    <div class="display-content">
        <div class="display-timer" :class="{ expired: timerExpired }">
            {{ timerDisplay }}
        </div>

        <div class="judge-lights">
            <!-- Left Judge -->
            <div class="judge-light" :class="displayVotes.left ? `light-${displayVotes.left}` : ''">
                <span>Left</span>
            </div>

            <!-- Center Judge -->
            <div class="judge-light" :class="displayVotes.center ? `light-${displayVotes.center}` : ''">
                <span>Center</span>
            </div>

            <!-- Right Judge -->
            <div class="judge-light" :class="displayVotes.right ? `light-${displayVotes.right}` : ''">
                <span>Right</span>
            </div>
        </div>

        <div class="display-status">
            {{ displayStatus }}
        </div>
    </div>
</div>
```

**Step 3: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: redesign display screen with large judge lights and dark premium styling"
```

---

## Task 10: Alpine.js Refactoring for New Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (Alpine.js code)

**Step 1: Update selectVote method**

In the `judgemeApp()` function, update the `selectVote` method:

```javascript
selectVote(color) {
    if (!this.voteLocked) {
        this.selectedVote = color;
    }
},
```

(No change needed - already correct)

**Step 2: Update getVoteColor helper**

Replace the existing `getVoteColor` method with:

```javascript
getVoteColor(vote) {
    const colors = {
        white: '#ffffff',
        red: '#ff4444',
        blue: '#4444ff',
        yellow: '#ffff44'
    };
    return colors[vote] || '#f5f5f5';
},
```

**Step 3: Verify Alpine bindings work with new HTML**

The Alpine.js code should work as-is with the new HTML structure. Key bindings to verify:
- `x-show` for screen transitions
- `x-model` for input binding
- `@click` for button events
- `:class` for conditional styling
- `:style` for dynamic colors

**Step 4: Test in browser**

No code commit needed yet - testing happens in next task.

---

## Task 11: Mobile Responsiveness & Final Polish

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS)

**Step 1: Add mobile-first responsive refinements to `<style>`**

```css
/* Mobile Optimizations */
@media (max-width: 768px) {
    .container {
        padding: var(--spacing-sm);
    }

    .header-bar {
        flex-wrap: wrap;
        padding: var(--spacing-sm);
    }

    .header-info {
        width: 100%;
        gap: var(--spacing-md);
    }

    button {
        font-size: 14px;
    }
}

@media (max-width: 480px) {
    h1 {
        font-size: 28px;
    }

    h2 {
        font-size: 20px;
    }

    .hero {
        min-height: 250px;
        padding: var(--spacing-lg) var(--spacing-sm);
    }

    .hero h1 {
        font-size: 28px;
    }

    button {
        min-height: 40px;
        padding: var(--spacing-sm) var(--spacing-md);
        font-size: 14px;
    }

    .text-3xl {
        font-size: 32px;
    }

    .text-2xl {
        font-size: 24px;
    }
}

/* Landscape Mode */
@media (max-height: 600px) and (orientation: landscape) {
    .hero {
        min-height: auto;
        padding: var(--spacing-lg) var(--spacing-md);
    }

    .judge-content {
        padding: var(--spacing-md);
    }

    .display-content {
        padding: var(--spacing-lg);
    }
}

/* Touch-friendly adjustments */
@media (hover: none) {
    button:active:not(:disabled) {
        opacity: 0.8;
    }
}

/* Dark mode detection */
@media (prefers-color-scheme: dark) {
    body {
        background-color: var(--bg-primary);
        color: var(--text-primary);
    }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
```

**Step 2: Add focus/accessibility improvements**

```css
/* Accessibility */
button:focus,
input:focus {
    outline: 2px solid var(--accent-gold);
    outline-offset: 2px;
}

/* High contrast mode */
@media (prefers-contrast: more) {
    .btn-primary {
        border: 2px solid var(--text-primary);
    }

    .btn-secondary {
        border: 2px solid var(--text-primary);
    }
}
```

**Step 3: Commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add mobile responsiveness and accessibility improvements"
```

---

## Task 12: Manual Testing & Verification

**Files:**
- Test: Browser testing of all screens

**Step 1: Start development server**

```bash
cd .worktrees/feature-frontend-redesign
python run.py
```

Expected output: Server running on http://localhost:8000

**Step 2: Test landing page**

1. Open http://localhost:8000 in browser
2. Verify dark premium design visible
3. Test "Create Session" button
4. Test "Try Demo Mode" button
5. Test session code input field
6. Verify responsive on mobile (use browser dev tools)

**Step 3: Test judge interface**

1. Create a session
2. Join as Left Judge
3. Verify header bar with session code and timer
4. Verify 4 vote buttons are visible and distinct colors
5. Click each vote button - verify selection styling
6. Click "Lock In" - verify confirmation message
7. Verify head judge controls visible and functional

**Step 4: Test display screen**

1. Create a session
2. Join as Left Judge, Center Judge, Right Judge (use multiple tabs)
3. Join as Display
4. Have each judge vote
5. Verify lights illuminate on display screen
6. Verify timer displays correctly
7. Verify status messages update

**Step 5: Test mobile responsiveness**

1. Open in Chrome DevTools mobile emulator
2. Test on iPhone SE, iPhone 12 Pro, iPad
3. Verify buttons remain clickable
4. Verify text is readable
5. Verify no horizontal scrolling

**Step 6: Test accessibility**

1. Use keyboard only to navigate (Tab, Enter, Arrow keys)
2. Verify all buttons are reachable
3. Verify focus indicators visible
4. Test with browser zoom (Ctrl +/-)

**Step 7: Document results**

All tests passing? Document in task 13 commit.

---

## Task 13: Run Tests & Commit Final Changes

**Files:**
- Test: `tests/` (unchanged)

**Step 1: Run all tests**

```bash
cd .worktrees/feature-frontend-redesign
pytest -v
```

Expected: All 30 tests passing

**Step 2: Check for console errors**

Open browser DevTools console while testing app. Verify:
- No JavaScript errors
- No CSS parsing errors
- WebSocket connection successful
- No security warnings

**Step 3: Final commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: complete dark premium frontend redesign

- Comprehensive design system with CSS variables
- Dark navy background with gold accents
- Consistent button components across all screens
- IPF-compliant vote colors with enhanced clarity
- Landing page hero section with value proposition
- Judge interface with clear voting area
- Display screen with large judge lights (180-240px)
- Mobile-responsive design optimized for touch
- Accessibility improvements and focus states
- All 30 tests passing
- Browser testing verified across devices"
```

**Step 4: Verify git status clean**

```bash
git status
```

Expected: Working tree clean, no uncommitted changes

---

## Summary

**Total Tasks:** 13
**Files Modified:** 1 (`src/judgeme/static/index.html`)
**Lines Added:** ~1,200 (CSS + HTML restructure)
**Backend Changes:** None
**Database Changes:** None
**Tests Affected:** None (all 30 passing)

**Deliverable:** Completely redesigned, production-ready frontend with dark premium aesthetic, consistent design system, and mobile responsiveness.
