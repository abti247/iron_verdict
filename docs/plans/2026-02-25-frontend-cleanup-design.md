# Frontend Cleanup Design
2026-02-25

Fix AGENTS.md violations in the static frontend: extract all static inline styles from index.html into CSS files, and split app.js (395 lines) into focused modules under the 300-line hard limit.

## Violations Found

| File | Violation |
|---|---|
| `index.html` | 23 static `style=""` attributes |
| `app.js` | 395 lines (hard limit: 300) |
| `app.js` | `handleMessage` is a single long if/else chain |

Not violated: the two dynamic `:style` Alpine bindings in index.html (allowed by AGENTS.md). The botcheck `style="display:none"` is intentionally left inline (anti-bot trap that must survive CSS failure).

## CSS Changes — `index.html`

All 23 static inline styles replaced with named CSS classes. No new files; classes added to existing files.

### New classes in `layout.css`

| Class | Element | Style |
|---|---|---|
| `.landing-panel--demo` | demo-intro `.landing-panel` | `max-width:600px; max-height:90vh; overflow-y:auto` |
| `.demo-guide-text` | intro `<p>` | Rajdhani 15px/600, text-dim, line-height 1.6, margin 20px 0 0 |
| `.demo-guide-heading` | section heading `<div>` | Bebas Neue 18px, letter-spacing 3px, blood-bright, margin 24px 0 8px |
| `.demo-guide-list` | `<ul>` / `<ol>` | Rajdhani 15px/600, text-dim, line-height 1.8, padding-left 18px, margin 0 |
| `.demo-popup-note` | popup warning box | margin-top 24px, border-left 2px solid blood, padding 8px 12px, Rajdhani 14px, text-dim, letter-spacing 0.5px |
| `.demo-running-msg` | "Demo running" div | margin-top 24px, text-align center, Bebas Neue 16px, letter-spacing 3px, blood-bright |
| `.app-version` | version string | margin-top 24px, Rajdhani 12px, text-dim, letter-spacing 1px, opacity 0.4 |

### New classes in `components.css`

| Class | Element | Style |
|---|---|---|
| `.btn-row` | spacing wrapper divs around buttons | `margin-top: 16px` |
| `.btn-row--sm` | smaller gap variant | `margin-top: 8px` |
| `.form-stack--no-top` | inner `.form-stack` in contact | `margin-top: 0` |
| `.contact-error` | error message div | text-align center, blood-bright, Rajdhani 15px, letter-spacing 1px |
| `.contact-success` | success panel div | text-align center, padding 24px 0, success color, Bebas Neue 22px, letter-spacing 4px, border 1px solid success, background success tint |
| `.contact-success-sub` | subtitle inside success | Rajdhani 15px, letter-spacing 1px, margin-top 6px, text-dim |

## JS Changes

### New file: `js/demo.js`

Exports `demoMethods` — a plain object mixin spread into the Alpine component. Contains the 4 demo-related methods extracted from `app.js`:

- `startDemo()`
- `async launchDemo()`
- `getWindowSpecs(sessionCode)`
- `returnToLandingFromDemo()`

`this` context is preserved naturally when Alpine merges the spread object into the component.

### New file: `js/handlers.js`

Exports one named function per WebSocket message type, each with signature `(app, message)`:

- `handleJoinSuccess(app, message)`
- `handleJoinError(app, message)`
- `handleError(app, message)`
- `handleShowResults(app, message)`
- `handleResetForNextLift(app, message)`
- `handleTimerStart(app, message)`
- `handleTimerReset(app, message)`
- `handleSessionEnded(app, message)`
- `handleSettingsUpdate(app, message)`

Imports `stopTimer` from `./timer.js` directly (removes that dependency from `app.js`).

Each handler is a pure function testable without a browser by passing a mock app object.

### Modified: `js/app.js`

- Imports `demoMethods` from `./demo.js` and spreads into returned component object
- Imports all named handlers from `./handlers.js`
- `handleMessage` becomes a thin dispatch table (~10 lines):

```js
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
```

### No changes to `index.html` script tags

`handlers.js` and `demo.js` are imported by `app.js` — they are not loaded directly by HTML.

## Result

| File | Before | After |
|---|---|---|
| `index.html` | 23 inline styles | 0 inline styles |
| `app.js` | 395 lines | ~230 lines |
| `handlers.js` | — | ~80 lines (new) |
| `demo.js` | — | ~55 lines (new) |

## Tests

No existing tests are affected (all tests are Python backend). The extracted handler functions will be testable in isolation by design (named functions, `app` passed as parameter) but no JS test infrastructure exists yet — writing JS tests is out of scope for this task.
