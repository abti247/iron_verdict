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
│   └── animations.css  # Keyframes and transition classes
├── js/
│   ├── constants.js    # Static data (CARD_REASONS, role name mappings)
│   ├── websocket.js    # WebSocket connection, send/receive, reconnection
│   ├── timer.js        # Timer countdown logic (startTimerCountdown, stopTimer)
│   ├── app.js          # Alpine.js component (ironVerdictApp) — imports from above modules
│   └── init.js         # Demo param detection, popstate handler, Alpine bootstrap
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
- Alpine.js component data (`ironVerdictApp`) lives in `app.js` and imports helpers from other modules.
- WebSocket message handling (`handleMessage`) should dispatch to named handler functions, not be a single long if/else chain.
- All static data (card reasons, role mappings, display names) belongs in `constants.js`, not inline in component logic.
- Never manipulate DOM directly (`document.body.classList`, `document.querySelector`) inside Alpine components — use Alpine's reactive bindings (`:class`, `x-bind`) instead.

### File Size and Splitting
- **Split by concern, not by line count.** A file is too big when it mixes responsibilities (e.g. VPortal state, timer and vote handling in one component) or when you can no longer name its single purpose in one sentence — not when it crosses a number.
- **~200 lines is a review signal, not a limit.** When a file grows past it, check whether it still has one concern. If yes, leave it; if no, split along the concern boundary. Never trim or squash code just to get under a number.
- Prefer many small, focused files over few large ones when the split follows a real boundary; a split that scatters one concern across files is worse than a long file.
- **Known exception:** `js/app.js` mixes several concerns (all screens, VPortal, shared state) in one Alpine component. It is being split by the refactoring issues [#65](https://github.com/abti247/iron_verdict/issues/65) (VPortal state into its own Alpine component), [#66](https://github.com/abti247/iron_verdict/issues/66) (shared state into `Alpine.store`) and [#67](https://github.com/abti247/iron_verdict/issues/67) (one component per screen). Until then: do not grow `app.js` further — put new logic in a new module and import it.

### Adding New Features
- New UI components get their own CSS class in `components.css` (or a new CSS file if the component is complex).
- New screens/views get layout rules in `layout.css`.
- New JS behaviors get their own module file if they represent a distinct concern (e.g., audio, notifications).
- Always update `index.html` `<link>`/`<script>` tags when adding new files.

### Testing
- JS modules should export pure functions where possible so they can be unit tested without a browser.
- WebSocket logic should be testable by injecting a mock WebSocket object.
- Timer logic should be testable by injecting a mock clock (avoid direct `Date.now()` calls — pass a time source).
