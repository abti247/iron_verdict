# Modern & Minimal Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Redesign the JudgeMe frontend from basic inline styles to a modern, minimal aesthetic with clean CSS architecture, zero scrolling constraint, and responsive layouts for phones, demo mode, and TV/projector displays.

**Architecture:** Rebuild `src/judgeme/static/index.html` with:
1. Comprehensive CSS framework in `<style>` block covering responsive grid, color system, typography, and component library
2. Semantic HTML structure with clear screen sections (landing, role-select, judge, display)
3. Flexbox/CSS Grid for responsive layouts that scale without scrolling
4. Alpine.js data binding preserved for all interactivity
5. Mobile-first responsive design with breakpoints for demo mode (4 screens on 1 display)

**Tech Stack:** HTML5 + CSS3 (Flexbox, Grid, media queries) + Alpine.js 3.x

**Design Reference:** `docs/plans/2026-02-05-frontend-redesign-design.md`

---

## Phase 1: CSS Framework & Design System

### Task 1: Establish Base Styles & Color Palette

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Create comprehensive CSS custom properties (CSS variables) for the color system, typography scales, and spacing units. This serves as the single source of truth for all design tokens.

**Step 1: Add CSS variables and reset styles**

In the `<style>` block, replace the current minimal styles with:

```css
:root {
  /* Colors - Neutrals */
  --bg-primary: #F9FAFB;
  --bg-secondary: #FFFFFF;
  --text-primary: #1F2937;
  --text-secondary: #6B7280;
  --border-color: #E5E7EB;

  /* Colors - Vote Colors (IPF Standard) */
  --vote-white: #FFFFFF;
  --vote-red: #EF4444;
  --vote-blue: #3B82F6;
  --vote-yellow: #FBBF24;

  /* Colors - Functional */
  --success-color: #10B981;
  --disabled-color: #9CA3AF;
  --timer-expired: #EF4444;

  /* Typography */
  --font-family: system-ui, -apple-system, sans-serif;
  --font-size-base: 16px;
  --font-size-sm: 14px;
  --font-size-lg: 20px;
  --font-size-xl: 32px;
  --font-size-2xl: 48px;
  --font-size-timer-display: 120px;
  --font-size-timer-judge: 32px;

  --font-weight-normal: 400;
  --font-weight-bold: 700;

  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-base: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  /* Layout */
  --touch-target-min: 48px;
  --border-radius: 4px;
  --transition-duration: 150ms;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden; /* Prevent scrolling */
}

body {
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  background-color: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
```

**Step 2: Run tests to ensure nothing broke**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests still pass (CSS changes don't affect backend)

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add CSS variables and design system foundation"
```

---

### Task 2: Create Responsive Container & Layout System

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Build CSS Grid/Flexbox layouts that ensure all screens fit in viewport with no scrolling. Use media queries to adapt for phone, tablet, desktop, and demo mode (4 screens on 1 display).

**Step 1: Add container and screen base styles**

Add to CSS:

```css
/* Main Container & Screen Layout */
.app-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  overflow: hidden;
}

.screen {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--spacing-base);
  overflow: hidden;
}

/* Landing & Role Selection Screens - Center Content */
.screen.centered {
  align-items: center;
  justify-content: center;
  text-align: center;
}

/* Judge Screen - Vertical Stack */
.screen.judge {
  justify-content: flex-start;
}

/* Display Screen - Center Content */
.screen.display {
  align-items: center;
  justify-content: center;
}

/* Ensure no scrollbars appear */
::-webkit-scrollbar {
  display: none;
}
html, body {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
```

**Step 2: Add demo mode responsive styles**

Add to CSS:

```css
/* Demo Mode: 4 screens on 1 display */
/* Default: 3 judges on top (1/3 width each), display full-width below */
@media (min-width: 1200px) {
  /* When judge windows are shown side-by-side in demo mode */
  .screen.judge:nth-child(1),
  .screen.judge:nth-child(2),
  .screen.judge:nth-child(3) {
    width: calc(100% / 3);
    height: 50vh;
    padding: 8px;
  }

  .screen.display {
    width: 100%;
    height: 50vh;
    padding: 8px;
  }
}
```

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add responsive container and layout system with demo mode support"
```

---

## Phase 2: Component Styles (Buttons, Inputs, Cards)

### Task 3: Build Button Component System

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Define button styles for all use cases: primary actions, voting buttons, secondary actions. Ensure consistent sizing with min 48px touch targets, proper states (normal, hover, active, disabled).

**Step 1: Add button base styles**

Add to CSS:

```css
/* Button Base Styles */
button {
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  padding: var(--spacing-sm) var(--spacing-base);
  min-height: var(--touch-target-min);
  border: 2px solid transparent;
  border-radius: var(--border-radius);
  cursor: pointer;
  transition: all var(--transition-duration) ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Primary Action Button */
.btn-primary {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  border-color: var(--border-color);
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--border-color);
  border-color: var(--text-primary);
}

.btn-primary:active:not(:disabled) {
  background-color: var(--text-primary);
  color: var(--bg-secondary);
}

/* Secondary/Muted Button */
.btn-secondary {
  background-color: transparent;
  color: var(--text-secondary);
  border-color: var(--border-color);
  font-size: var(--font-size-sm);
}

.btn-secondary:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--text-primary);
}

/* Disabled State */
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

**Step 2: Add voting button styles**

Add to CSS:

```css
/* Voting Buttons - Large, Color-Coded */
.voting-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-base);
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
}

.btn-vote {
  min-height: 80px;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  border: 3px solid transparent;
  border-radius: var(--border-radius);
  transition: all var(--transition-duration) ease;
}

.btn-vote-white {
  background-color: var(--vote-white);
  color: var(--text-primary);
  border: 3px solid var(--text-primary);
}

.btn-vote-white:not(:disabled):hover {
  opacity: 0.8;
  box-shadow: inset 0 0 0 3px var(--text-primary);
}

.btn-vote-white.selected {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 4px var(--text-primary);
}

.btn-vote-red {
  background-color: var(--vote-red);
  color: white;
  border: 3px solid var(--vote-red);
}

.btn-vote-red:not(:disabled):hover {
  opacity: 0.9;
  box-shadow: inset 0 0 0 3px rgba(0, 0, 0, 0.2);
}

.btn-vote-red.selected {
  box-shadow: 0 0 0 4px var(--vote-red);
}

.btn-vote-blue {
  background-color: var(--vote-blue);
  color: white;
  border: 3px solid var(--vote-blue);
}

.btn-vote-blue:not(:disabled):hover {
  opacity: 0.9;
  box-shadow: inset 0 0 0 3px rgba(0, 0, 0, 0.2);
}

.btn-vote-blue.selected {
  box-shadow: 0 0 0 4px var(--vote-blue);
}

.btn-vote-yellow {
  background-color: var(--vote-yellow);
  color: var(--text-primary);
  border: 3px solid var(--text-primary);
}

.btn-vote-yellow:not(:disabled):hover {
  opacity: 0.9;
  box-shadow: inset 0 0 0 3px rgba(0, 0, 0, 0.2);
}

.btn-vote-yellow.selected {
  box-shadow: 0 0 0 4px var(--text-primary);
}

.btn-vote:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

**Step 3: Add full-width action button style**

Add to CSS:

```css
.btn-full-width {
  width: 100%;
  padding: var(--spacing-base) var(--spacing-lg);
  min-height: 56px;
  font-size: var(--font-size-lg);
}

.btn-full-width.lock-in {
  background-color: var(--success-color);
  color: white;
  font-weight: var(--font-weight-bold);
}

.btn-full-width.lock-in:hover:not(:disabled) {
  background-color: #059669;
}
```

**Step 4: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 5: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add comprehensive button component system with voting button styles"
```

---

### Task 4: Build Input & Card Component Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Style input fields and card containers for consistent UI across screens.

**Step 1: Add input styles**

Add to CSS:

```css
/* Input Fields */
input[type="text"] {
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  padding: var(--spacing-sm) var(--spacing-base);
  min-height: var(--touch-target-min);
  border: 2px solid var(--border-color);
  border-radius: var(--border-radius);
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  transition: border-color var(--transition-duration) ease;
}

input[type="text"]::placeholder {
  color: var(--text-secondary);
}

input[type="text"]:focus {
  outline: none;
  border-color: var(--text-primary);
  box-shadow: 0 0 0 3px rgba(31, 41, 55, 0.1);
}
```

**Step 2: Add card & status styles**

Add to CSS:

```css
/* Cards & Panels */
.card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: var(--spacing-base);
}

.card.status-locked {
  background-color: #D1FAE5;
  border-color: var(--success-color);
  color: var(--text-primary);
  text-align: center;
  padding: var(--spacing-lg);
  font-weight: var(--font-weight-bold);
}

/* Top Bar / Header Card */
.header-bar {
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: var(--spacing-base);
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 60px;
  width: 100%;
}

.header-bar-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.header-bar-item.center {
  align-items: center;
  flex: 1;
}

.header-bar-item.right {
  align-items: flex-end;
}

.session-code {
  font-family: monospace;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  text-decoration: underline;
  transition: color var(--transition-duration) ease;
}

.session-code:hover {
  color: var(--text-primary);
}
```

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add input and card component styles"
```

---

## Phase 3: Screen-Specific Styles

### Task 5: Landing Page Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Style the landing page with centered layout, heading, tagline, and two prominent CTA buttons with demo button secondary.

**Step 1: Add landing page styles**

Add to CSS:

```css
/* Landing Page */
.screen.landing {
  padding: var(--spacing-lg);
}

.landing-content {
  max-width: 500px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  align-items: center;
  text-align: center;
}

.landing-logo {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-base);
}

.landing-tagline {
  font-size: var(--font-size-lg);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-lg);
}

.landing-actions {
  display: flex;
  gap: var(--spacing-base);
  width: 100%;
  flex-wrap: wrap;
  justify-content: center;
}

.landing-actions .btn-primary {
  flex: 1;
  min-width: 150px;
}

.landing-join {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.landing-join input {
  width: 100%;
}

.landing-demo {
  margin-top: var(--spacing-base);
  width: 100%;
}

/* Mobile: Stack buttons vertically */
@media (max-width: 600px) {
  .landing-actions {
    flex-direction: column;
  }

  .landing-actions .btn-primary {
    width: 100%;
  }
}
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add landing page styles with centered layout"
```

---

### Task 6: Role Selection Page Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Style the role selection screen with clear heading, session code display, and role buttons organized in two rows (judges top, display bottom).

**Step 1: Add role selection styles**

Add to CSS:

```css
/* Role Selection Page */
.screen.role-select {
  padding: var(--spacing-lg);
  gap: var(--spacing-lg);
}

.role-select-content {
  max-width: 600px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  align-items: center;
}

.role-select-header {
  text-align: center;
}

.role-select-header h2 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  margin-bottom: var(--spacing-base);
}

.session-display {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
}

.role-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--spacing-base);
  width: 100%;
  margin-bottom: var(--spacing-lg);
}

.role-buttons .btn-primary {
  width: 100%;
  min-height: 80px;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
}

.role-buttons-display {
  display: flex;
  width: 100%;
  gap: var(--spacing-base);
}

.role-buttons-display .btn-primary {
  flex: 1;
  min-height: 80px;
  font-size: var(--font-size-lg);
}

/* Mobile: Stack judge buttons */
@media (max-width: 800px) {
  .role-buttons {
    grid-template-columns: 1fr;
  }
}
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add role selection page styles"
```

---

### Task 7: Judge Screen Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Style the judge screen with compact header bar, large voting buttons as primary focus, lock button, status card, and head judge controls section.

**Step 1: Add judge screen styles**

Add to CSS:

```css
/* Judge Screen */
.screen.judge {
  padding: 0;
  gap: 0;
}

.judge-header {
  flex-shrink: 0;
  background-color: var(--bg-secondary);
  border-bottom: 2px solid var(--border-color);
  padding: var(--spacing-base);
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 70px;
}

.judge-header-left {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.judge-position {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: var(--font-weight-bold);
}

.judge-header-center {
  flex: 1;
  text-align: center;
}

.judge-header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--spacing-xs);
}

.judge-timer {
  font-size: var(--font-size-timer-judge);
  font-weight: var(--font-weight-bold);
  font-family: monospace;
  color: var(--text-primary);
  transition: color var(--transition-duration) ease;
}

.judge-timer.expired {
  color: var(--timer-expired);
}

.judge-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
  gap: var(--spacing-lg);
  overflow: hidden;
}

.judge-voting-area {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  width: 100%;
  max-width: 400px;
}

.judge-controls {
  flex-shrink: 0;
  border-top: 2px solid var(--border-color);
  padding: var(--spacing-lg) var(--spacing-base);
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-base);
}

.judge-controls h3 {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  margin-bottom: var(--spacing-sm);
}

.judge-controls-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
  width: 100%;
}

.judge-controls-buttons .btn-primary {
  width: 100%;
  min-height: 56px;
  font-size: var(--font-size-sm);
}
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add judge screen styles with header and voting layout"
```

---

### Task 8: Display Screen Styles

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section)

**Description:** Style the display screen with minimal header, enormous timer, and three judge lights in horizontal row for visibility from distance.

**Step 1: Add display screen styles**

Add to CSS:

```css
/* Display Screen */
.screen.display {
  padding: var(--spacing-lg);
  gap: var(--spacing-lg);
}

.display-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xl);
  width: 100%;
  height: 100%;
}

.display-timer {
  font-size: var(--font-size-timer-display);
  font-weight: var(--font-weight-bold);
  font-family: monospace;
  color: var(--text-primary);
  transition: color var(--transition-duration) ease;
  line-height: 1;
}

.display-timer.expired {
  color: var(--timer-expired);
}

.display-lights {
  display: flex;
  justify-content: center;
  gap: var(--spacing-xl);
  width: 100%;
}

.light {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 3px solid var(--border-color);
  background-color: #F3F4F6;
  transition: all var(--transition-duration) ease;
  flex-shrink: 0;
}

.light.voted-white {
  background-color: var(--vote-white);
  border-color: var(--text-primary);
}

.light.voted-red {
  background-color: var(--vote-red);
  border-color: var(--vote-red);
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
}

.light.voted-blue {
  background-color: var(--vote-blue);
  border-color: var(--vote-blue);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
}

.light.voted-yellow {
  background-color: var(--vote-yellow);
  border-color: var(--text-primary);
  box-shadow: 0 0 20px rgba(251, 191, 36, 0.3);
}

.display-status {
  font-size: var(--font-size-lg);
  color: var(--text-secondary);
  text-align: center;
  font-weight: var(--font-weight-bold);
}

/* Large screens: bigger lights */
@media (min-width: 1200px) {
  .light {
    width: 150px;
    height: 150px;
  }

  .display-timer {
    font-size: 150px;
  }
}

/* Very large screens: even bigger */
@media (min-width: 1920px) {
  .light {
    width: 180px;
    height: 180px;
  }

  .display-timer {
    font-size: 180px;
  }
}
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: add display screen styles with massive timer and judge lights"
```

---

## Phase 4: HTML Structure Refactoring

### Task 9: Refactor HTML with Semantic Structure & Classes

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML content)

**Description:** Update HTML to use the new CSS classes instead of inline styles. Maintain all Alpine.js bindings and functionality.

**Step 1: Refactor landing page HTML**

Replace the landing screen div with:

```html
<!-- Landing screen -->
<div class="screen centered landing" x-show="screen === 'landing'">
  <div class="landing-content">
    <div class="landing-logo">JudgeMe</div>
    <div class="landing-tagline">Real-time powerlifting competition judging</div>

    <div class="landing-actions">
      <button class="btn-primary" @click="createSession()">Create New Session</button>
      <button class="btn-primary" @click="screen = 'role-select'">Join Session</button>
    </div>

    <div class="landing-join">
      <input type="text" x-model="joinCode" placeholder="Enter session code">
      <button class="btn-primary" @click="joinSessionFromCode()">Join</button>
    </div>

    <button class="btn-secondary landing-demo" @click="startDemo()">Start Demo</button>
  </div>
</div>
```

**Step 2: Update the Alpine app to handle joinSessionFromCode**

In the Alpine script, add this method to the judgemeApp function (after joinSession):

```javascript
joinSessionFromCode() {
  this.sessionCode = this.joinCode;
  this.screen = 'role-select';
}
```

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: refactor landing page HTML with semantic classes"
```

---

### Task 10: Refactor Role Selection HTML

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML content)

**Description:** Update role selection screen with new class structure and layout.

**Step 1: Replace role selection div**

Replace the role selection screen div with:

```html
<!-- Role selection screen -->
<div class="screen centered role-select" x-show="screen === 'role-select'">
  <div class="role-select-content">
    <div class="role-select-header">
      <h2>Select Your Role</h2>
      <div class="session-display">
        Session: <span class="session-code" @click="returnToRoleSelection()" tabindex="0" role="button" x-text="sessionCode"></span>
      </div>
    </div>

    <div class="role-buttons">
      <button class="btn-primary" @click="joinSession('left_judge')">Left Judge</button>
      <button class="btn-primary" @click="joinSession('center_judge')">Center Judge (Head)</button>
      <button class="btn-primary" @click="joinSession('right_judge')">Right Judge</button>
    </div>

    <div class="role-buttons-display">
      <button class="btn-primary" @click="joinSession('display')">Display</button>
    </div>
  </div>
</div>
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: refactor role selection HTML with new layout classes"
```

---

### Task 11: Refactor Judge Screen HTML

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML content)

**Description:** Restructure judge screen with header bar, voting area, and controls section.

**Step 1: Replace judge screen div**

Replace the judge screen div with:

```html
<!-- Judge screen -->
<div class="screen judge" x-show="screen === 'judge'">
  <!-- Header Bar -->
  <div class="judge-header">
    <div class="judge-header-left">
      <span class="judge-position" x-text="getJudgePositionLabel()"></span>
    </div>
    <div class="judge-header-center">
      <span class="session-code" @click="returnToRoleSelection()" tabindex="0" role="button" x-text="sessionCode"></span>
    </div>
    <div class="judge-header-right">
      <span class="judge-timer" :class="{ expired: timerExpired }" x-text="timerDisplay"></span>
    </div>
  </div>

  <!-- Voting Content Area -->
  <div class="judge-content">
    <div class="judge-voting-area">
      <!-- Voting Buttons Grid -->
      <div class="voting-buttons">
        <button
          class="btn-vote btn-vote-white"
          :class="{ selected: selectedVote === 'white' }"
          @click="selectVote('white')"
          :disabled="voteLocked">
          White
        </button>
        <button
          class="btn-vote btn-vote-red"
          :class="{ selected: selectedVote === 'red' }"
          @click="selectVote('red')"
          :disabled="voteLocked">
          Red
        </button>
        <button
          class="btn-vote btn-vote-blue"
          :class="{ selected: selectedVote === 'blue' }"
          @click="selectVote('blue')"
          :disabled="voteLocked">
          Blue
        </button>
        <button
          class="btn-vote btn-vote-yellow"
          :class="{ selected: selectedVote === 'yellow' }"
          @click="selectVote('yellow')"
          :disabled="voteLocked">
          Yellow
        </button>
      </div>

      <!-- Lock In Button -->
      <button
        class="btn-full-width lock-in"
        x-show="selectedVote && !voteLocked"
        @click="lockVote()">
        Lock In
      </button>

      <!-- Vote Status -->
      <div class="card status-locked" x-show="voteLocked">
        Your vote: <strong x-text="selectedVote"></strong> (locked)
      </div>
    </div>
  </div>

  <!-- Head Judge Controls -->
  <div class="judge-controls" x-show="isHead">
    <h3>Head Judge Controls</h3>
    <div class="judge-controls-buttons">
      <button class="btn-primary" @click="startTimer()">Start Timer</button>
      <button class="btn-primary" @click="resetTimer()">Reset Timer</button>
      <button class="btn-primary" @click="nextLift()" :disabled="!resultsShown">Next Lift</button>
      <button class="btn-primary" @click="confirmEndSession()">End Session</button>
    </div>
  </div>
</div>
```

**Step 2: Add helper method to Alpine app**

Add this method to the judgemeApp function:

```javascript
getJudgePositionLabel() {
  if (this.role === 'left_judge') return 'Left Judge';
  if (this.role === 'center_judge') return 'Center Judge (Head)';
  if (this.role === 'right_judge') return 'Right Judge';
  return '';
}
```

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: refactor judge screen HTML with header bar and styled controls"
```

---

### Task 12: Refactor Display Screen HTML

**Files:**
- Modify: `src/judgeme/static/index.html` (HTML content)

**Description:** Restructure display screen with minimal header and large timer + judge lights.

**Step 1: Replace display screen div**

Replace the display screen div with:

```html
<!-- Display screen -->
<div class="screen display" x-show="screen === 'display'">
  <!-- Minimal Header -->
  <div class="header-bar" style="position: absolute; top: 0; left: 0; right: 0; width: 100%; padding: var(--spacing-base); border: none; background-color: transparent;">
    <span class="session-code" @click="returnToRoleSelection()" tabindex="0" role="button" x-text="sessionCode"></span>
  </div>

  <!-- Display Content -->
  <div class="display-content">
    <!-- Massive Timer -->
    <div class="display-timer" :class="{ expired: timerExpired }" x-text="timerDisplay"></div>

    <!-- Judge Lights -->
    <div class="display-lights">
      <div class="light" :class="getDisplayLightClass('left')"></div>
      <div class="light" :class="getDisplayLightClass('center')"></div>
      <div class="light" :class="getDisplayLightClass('right')"></div>
    </div>

    <!-- Status -->
    <div class="display-status" x-text="displayStatus"></div>
  </div>
</div>
```

**Step 2: Add helper method to Alpine app**

Add this method to the judgemeApp function:

```javascript
getDisplayLightClass(position) {
  const vote = this.displayVotes[position];
  if (!vote) return '';
  return `voted-${vote}`;
}
```

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "feat: refactor display screen HTML with massive timer and judge lights"
```

---

## Phase 5: Fine-Tuning & Responsive Testing

### Task 13: Test Responsiveness at Multiple Breakpoints

**Files:**
- Test: Manual browser testing at different viewport sizes

**Description:** Verify all screens render correctly and fit within viewport without scrolling at common breakpoints: 375px (phone), 768px (tablet), 1024px (desktop), and 1920px (large display).

**Step 1: Manual testing checklist**

Test each screen at each breakpoint:

**Landing Page:**
- ✓ All text readable
- ✓ Buttons properly sized and spaced
- ✓ No horizontal scroll
- ✓ No vertical scroll
- ✓ Elements centered

**Role Selection:**
- ✓ Three judge buttons visible and properly spaced
- ✓ Display button below in full row
- ✓ Session code visible and clickable
- ✓ No scroll at any breakpoint

**Judge Screen:**
- ✓ Header bar compact with position, session code, timer
- ✓ Voting buttons large enough (minimum 80px)
- ✓ Timer visible but doesn't compete with voting
- ✓ Lock button full-width below voting grid
- ✓ Head judge controls below status (when visible)
- ✓ No scroll at any breakpoint

**Display Screen:**
- ✓ Timer enormous and centered
- ✓ Three judge lights visible in horizontal row
- ✓ Lights scale with screen size
- ✓ Lights visible from distance (large sizes at 1920px)
- ✓ No scroll at any breakpoint

**Step 2: Check for scrollbars**

Open DevTools, go to Console and run:

```javascript
// Check if scrollbars are present
const hasScroll = () => {
  const html = document.documentElement;
  const body = document.body;
  return (html.scrollHeight > html.clientHeight) || (body.scrollHeight > body.clientHeight);
};
console.log("Has scroll:", hasScroll());
```

Expected: `false` on all screens at all sizes

**Step 3: Document findings**

If any issues found, make minor CSS adjustments (gaps, padding, font sizes) and re-test. If all pass:

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add -A
git commit -m "test: verify responsive layout across breakpoints - no scrolling on any screen"
```

---

### Task 14: Fix Judge Screen Layout (Flex-Grow for Centering)

**Files:**
- Modify: `src/judgeme/static/index.html` (CSS section - judge-content)

**Description:** Ensure voting area is properly centered vertically on judge screens, especially on larger displays.

**Step 1: Update judge-content CSS**

Find the `.judge-content` rule and update it:

```css
.judge-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
  gap: var(--spacing-lg);
  overflow: hidden;
  min-height: 0; /* Important for Firefox */
}
```

**Step 2: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 3: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "fix: ensure judge content is properly centered vertically"
```

---

### Task 15: Remove Old Inline Styles (Cleanup)

**Files:**
- Modify: `src/judgeme/static/index.html`

**Description:** Remove any remaining inline `style` attributes that were part of the old design.

**Step 1: Check for remaining inline styles in HTML**

Search for `style="` in the HTML body (not the CSS section). The refactored HTML should not have inline styles except where absolutely necessary.

**Step 2: Remove or clean up any remaining**

All styling should now be in the CSS section via classes. If you find any `style=` attributes in the refactored HTML sections, they can be removed.

**Step 3: Run tests**

Run: `cd .worktrees/feature/modern-minimal-redesign && pytest tests/ -v --tb=short`
Expected: All 30 tests pass

**Step 4: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add src/judgeme/static/index.html
git commit -m "refactor: remove inline styles, use CSS classes exclusively"
```

---

## Phase 6: Final Verification

### Task 16: Full Browser Testing - All Features

**Files:**
- Test: Manual full-flow testing

**Description:** Test the complete user journey on the redesigned frontend: create session, join, select role, vote, lock, timer, results, display screen.

**Step 1: Start the application**

```bash
cd .worktrees/feature/modern-minimal-redesign
python run.py
```

Access at: `http://localhost:8000`

**Step 2: Test Landing Page**

- ✓ Click "Create New Session" → see role selection
- ✓ Click "Join Session", enter code, click Join → see role selection
- ✓ Click "Start Demo" → opens 4 windows (3 judges, 1 display)

**Step 3: Test Role Selection**

- ✓ Click each judge button → joins as that role
- ✓ Click Display button → joins as display
- ✓ Session code visible and clickable

**Step 4: Test Judge Screen**

- ✓ Header shows judge position, session code, timer
- ✓ Session code clickable → returns to role select
- ✓ Vote buttons large and color-coded
- ✓ Select vote → button gets selected state
- ✓ Click "Lock In" → vote locked, status shown
- ✓ Timer visible and updates

**Step 5: Test Display Screen**

- ✓ Timer large and centered
- ✓ Three judge lights visible
- ✓ When judges vote, lights show colors
- ✓ Session code visible at top

**Step 6: Test Head Judge Controls**

- ✓ "Start Timer" → timer counts down
- ✓ "Reset Timer" → timer resets to 60
- ✓ When all judges vote → "Next Lift" becomes enabled
- ✓ "Next Lift" → resets votes, shows new voting screen
- ✓ "End Session" → asks for confirmation, ends session

**Step 7: Commit**

```bash
cd .worktrees/feature/modern-minimal-redesign
git add -A
git commit -m "test: full browser testing - all features working with new design"
```

---

## Summary

**Total Tasks:** 16
- Phase 1 (CSS Foundation): Tasks 1-2
- Phase 2 (Components): Tasks 3-4
- Phase 3 (Screen Styles): Tasks 5-8
- Phase 4 (HTML Refactoring): Tasks 9-12
- Phase 5 (Testing): Tasks 13-15
- Phase 6 (Verification): Task 16

**Commits Expected:** ~16 commits (one per task)

**Testing Strategy:**
- Unit tests (backend) pass throughout
- Manual browser testing at breakpoints
- Full feature testing at end
- No scrolling verification on all screens

---

## Unresolved Questions

None at this time. Design and architecture fully specified.
