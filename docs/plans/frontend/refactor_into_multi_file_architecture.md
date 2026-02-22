# Plan: Refactor frontend into multi-file architecture

## Context
`src/iron_verdict/static/index.html` is a 1388-line monolith mixing HTML, CSS, and JS.
Goal: split into focused files for caching, maintainability, and future frontend testing.
No functional changes.

## Target file tree
```
src/iron_verdict/static/
├── index.html              (markup only)
├── css/
│   ├── variables.css
│   ├── base.css
│   ├── components.css
│   ├── layout.css
│   └── animations.css
└── js/
    ├── constants.js
    ├── timer.js
    ├── websocket.js
    ├── app.js
    └── init.js
```

## Steps

### 1. Create css/ and js/ directories + files

**variables.css** — `:root { ... }` block only

**base.css** — `* { reset }`, `body`, `.chrome-text`, `.hidden`

**animations.css** — `@keyframes pulse-red`, `.judge-timer.expired`, `.display-timer-big.expired`

**components.css** — everything component-scoped:
`.cut-corner`, `.cut-corner-sm`, `.btn-blood*`, `button:disabled`, `.slash-divider`, `.form-stack`,
`.chrome-input`, `.vote-btn*`, `.lock-btn`, `.locked-status`,
`.reason-step*`, `.back-btn`, `.reason-list`, `.reason-item`,
`.head-section`, `.head-title`, `.head-grid`, `.settings-bar`,
`.display-orb*`, `.judge-results-orbs`, `.judge-result-orb-wrap`,
`.display-status`, `.display-verdict`, `.verdict-stamp*`, `.display-verdict-inline`

**layout.css** — screen-level wrappers and their direct children:
`.landing-wrap`, `.landing-panel`, `.brand-iron`, `.brand-verdict-sub`,
`.role-wrap`, `.role-panel`, `.role-heading`, `.session-tag`, `.role-grid`, `.role-btn`, `.role-display-btn`,
`.judge-wrap`, `.judge-bar`, `.judge-role-label`, `.judge-timer`, `.judge-code`, `.vote-grid`,
`.display-full`, `.display-tag`, `.display-timer-big`, `.display-lights`,
`@media (max-width: 600px)`

---

### 2. Create js/ modules

**constants.js**
```js
export const CARD_REASONS = { squat: {...}, bench: {...}, deadlift: {...} };
export const ROLE_DISPLAY_NAMES = { left_judge: '...', center_judge: '...', right_judge: '...' };
```

**timer.js** — module-level `let timerInterval = null`
```js
export function startTimerCountdown(ms, onTick) { ... }  // onTick(seconds, expired)
export function stopTimer() { clearInterval; timerInterval = null; }
```

**websocket.js**
```js
export function createWebSocket(url, onMessage, onError, onClose) {
    const ws = new WebSocket(url);
    // wire handlers
    return { ws, send: (data) => ws.send(JSON.stringify(data)) };
}
```

**app.js** — imports constants/timer/websocket, exports `ironVerdictApp()`
- `stopTimer()` calls must be followed by manual `this.timerDisplay = '60'; this.timerExpired = false`
  (timer.js is pure, doesn't touch Alpine state)
- `getRoleDisplayName()` uses imported `ROLE_DISPLAY_NAMES`
- Remove `document.body.classList.add/remove('display-mode')` — handled by `:class` on `<body>`

**init.js**
```js
import { ironVerdictApp } from './app.js';
// demo params IIFE (moved from <head>)
(function() { /* set window._demoParams */ })();
document.addEventListener('alpine:init', () => {
    Alpine.data('ironVerdictApp', ironVerdictApp);
});
window.addEventListener('popstate', () => { /* unchanged __x_data handler */ });
```

---

### 3. Rewrite index.html

- `<head>`: meta, title, Google Fonts link, 5 CSS `<link>` tags (variables→base→components→layout→animations), Alpine CDN `<script defer>`
- `<body x-data="ironVerdictApp()" :class="{ 'display-mode': role === 'display' && screen === 'display' }">`: all existing markup unchanged
- Bottom of body: `<script type="module" src="/static/js/init.js"></script>`
- No `<style>` block, no inline `<script>` block

CSS link order in head:
```html
<link rel="stylesheet" href="/static/css/variables.css">
<link rel="stylesheet" href="/static/css/base.css">
<link rel="stylesheet" href="/static/css/components.css">
<link rel="stylesheet" href="/static/css/layout.css">
<link rel="stylesheet" href="/static/css/animations.css">
```

---

### 4. Run tests + smoke test

```
<root>/.venv/Scripts/python.exe -m pytest <worktree>/tests/ -q --tb=short
```

Then manually verify Alpine + ES module load ordering works (risk #1):
open the app and confirm the landing screen renders (not blank).

## Files modified
- `src/iron_verdict/static/index.html` — rewritten
- `src/iron_verdict/static/css/` — 5 new files
- `src/iron_verdict/static/js/` — 5 new files
- No Python files modified
- No tests modified
