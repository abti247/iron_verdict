# Frontend Architecture Rules (src/iron_verdict/static/)

## File Structure

The frontend lives in `src/iron_verdict/static/` and MUST follow this structure:

```
src/iron_verdict/static/
├── index.html          # HTML structure only — no <style> blocks, no <script> logic
├── css/
│   ├── variables.css   # CSS custom properties (:root vars, theme tokens)
│   ├── base.css        # Resets, typography, body, global element styles
│   ├── components.css  # Reusable UI components (.btn-blood, .cut-corner, .chrome-input, etc.)
│   ├── layout.css      # Screen-level layouts (landing, role-select, judge, display)
│   ├── animations.css  # Keyframes and transition classes
│   ├── display-contrast.css # Display contrast mode (scoped under .display-contrast)
│   ├── display-layout.css   # Saved display layout and its editor (.display-layout-custom/-editing)
│   └── display-overlay.css  # Transparent stream overlay for OBS (scoped under html.display-overlay)
├── js/
│   ├── init.js         # Entry point: demo params, boot (i18n, fonts, Alpine), popstate → connection
│   ├── app.js          # Bootstrap: registers stores and screen components with Alpine, starts the app
│   ├── connection.js   # The one WebSocket owner: join/leave flows, reload recovery start, message dispatch
│   ├── handlers.js     # One handler per incoming WS message type — writes the stores
│   ├── navigation.js   # Alpine.store('nav') — current screen and browser history
│   ├── sessionStore.js # Alpine.store('session') — code, role, connection, landing form
│   ├── judgeStore.js   # Alpine.store('judge') — vote and result of the judge screen
│   ├── displayStore.js # Alpine.store('display') — lights, reasons, verdict of the display
│   ├── settingsStore.js# Alpine.store('settings') — lift type, show/require reasons
│   ├── timer.js        # Countdown interval and Alpine.store('timer')
│   ├── vportalStore.js # Alpine.store('vportal') — connect dialog and display overlay
│   ├── displayLayout.js# Display layout model (pure: validate, store, snap, export code)
│   ├── websocket.js    # WebSocket connection, send/receive, reconnection
│   ├── constants.js    # Static data (CARD_REASONS, role name mappings)
│   ├── …               # Helpers: voteDelivery, reloadRecovery, roleTakeover, i18n, vportal*
│   └── screens/        # One Alpine component per screen (landing, contact, demoIntro,
│                       # reconnecting, roleSelect, judge, display; displayLayoutEditor
│                       # is mixed into the display component)
```

## Rules

### Separation of Concerns
- **HTML files contain ONLY markup.** No `<style>` blocks. No inline `style=""` attributes except for dynamic Alpine bindings (`:style`). No `<script>` blocks with application logic.
- **CSS files contain ONLY styles.** One responsibility per file.
- **JS files contain ONLY one module/concern.** Each file should have a single, clear purpose.

### CSS
- All colors, spacing tokens, and theme values MUST be defined as CSS custom properties in `variables.css` — never as magic numbers in component styles.
- Use the existing naming convention: `--bg-*`, `--text-*`, `--vote-*`, `--blood*`, `--chrome-*`.
- Media queries for responsive breakpoints live in the same file as the component they modify.
- Never use `!important` unless overriding a third-party library.

### JavaScript
- Use ES modules (`export`/`import`) for all JS files. The entry point (`init.js`) is loaded with `<script type="module">`.
- One Alpine component per screen in `js/screens/`, registered in `app.js` and placed on the screen's root element in `index.html`. A component holds only UI state of its screen (zoom, open panel, scroll hint, a form shown only there).
- State the server drives or several screens read lives in a store (`session`, `nav`, `judge`, `display`, `timer`, `settings`, `vportal`) — never in a screen component. Incoming messages reach it through `handlers.js`, never through browser events: a screen that is not in the DOM (`x-if`) would miss them.
- The WebSocket and the join/leave flows belong to `connection.js` only. Screens call its functions; they never open a socket or start/stop the VPortal overlay themselves.
- `<template x-if>` for screens without state that must survive (landing, contact, privacy, demo intro, reconnecting); `x-show` for role-select, judge and display. `data-testid` goes on the element inside the template.
- WebSocket message handling (`handleMessage`) should dispatch to named handler functions, not be a single long if/else chain.
- All static data (card reasons, role mappings, display names) belongs in `constants.js`, not inline in component logic.
- Never manipulate DOM directly (`document.body.classList`, `document.querySelector`) inside Alpine components — use Alpine's reactive bindings (`:class`, `x-bind`) instead.

### File Size and Splitting
- **Split by concern, not by line count.** A file is too big when it mixes responsibilities (e.g. VPortal state, timer and vote handling in one component) or when you can no longer name its single purpose in one sentence — not when it crosses a number.
- **~200 lines is a review signal, not a limit.** When a file grows past it, check whether it still has one concern. If yes, leave it; if no, split along the concern boundary. Never trim or squash code just to get under a number.
- Prefer many small, focused files over few large ones when the split follows a real boundary; a split that scatters one concern across files is worse than a long file.

### Adding New Features
- New UI components get their own CSS class in `components.css` (or a new CSS file if the component is complex).
- New screens/views get layout rules in `layout.css`.
- New JS behaviors get their own module file if they represent a distinct concern (e.g., audio, notifications).
- Always update `index.html` `<link>`/`<script>` tags when adding new files.

### Testing
- JS modules should export pure functions where possible so they can be unit tested without a browser.
- WebSocket logic should be testable by injecting a mock WebSocket object.
- Timer logic should be testable by injecting a mock clock (avoid direct `Date.now()` calls — pass a time source).
