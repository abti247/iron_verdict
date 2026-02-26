# Navigation, Reload & QR Code UX — Design

Date: 2026-02-26

## Problem

Three UX pain points:
1. Page reload on judge/display screen drops users back to landing page.
2. Clicking the session code on role-select screen accidentally returns users to landing — losing session context.
3. No easy way for judges to join a session without typing the 8-character code.

## Goals

- Reload on judge or display screen auto-rejoins the user in the same role.
- Role-select screen has a clear, explicit back button; session code is not clickable.
- QR code on role-select lets judges scan-to-join directly.

## Design

### 1. Reload / Auto-Rejoin (sessionStorage)

On `joinSession(role)`: save `{ code, role }` to `sessionStorage['iv_session']`.

In `init()`: after the existing demo-URL check, check `sessionStorage['iv_session']`. If present, auto-rejoin with the stored code and role (calls `joinSession(role)` immediately).

Clear sessionStorage in:
- `returnToLanding()` — explicit user exit
- `handleSessionEnded()` — session ended by head judge

### 2. Role-Select Back Navigation

- Remove `@click="returnToLanding()"` from the session code `<span>` on the role-select screen. Code becomes display-only text.
- Add a `← Back to Start` button at the bottom of the role panel (using `btn-blood btn-blood-ghost` style, consistent with other back buttons in the app).

### 3. QR Code on Role-Select

**URL entry point (for QR scans):**
- `init()` checks for `?session=XXXX` in URL params.
- If found: set `sessionCode`, navigate to `role-select`, call `history.replaceState({}, '', '/')` to strip the code from the URL immediately.
- This keeps the URL clean (`/`) on all active screens including display.

**QR code generation:**
- Add `QRCode.js` from jsdelivr CDN to `index.html`.
- QR encodes: `window.location.origin + '/?session=' + sessionCode`
- A `<div id="qrcode">` rendered on the role-select screen.
- QR generated (or regenerated) whenever `screen` transitions to `role-select`.

**Role-select screen layout (top to bottom):**
```
SELECT ROLE
Session: XXXXXXXX
[QR CODE]
[Left Judge] [Center Judge] [Right Judge]
[Display Screen]
← Back to Start
```

## Files Affected

- `src/iron_verdict/static/index.html` — QR div, back button, remove click from session code, add QRCode.js CDN
- `src/iron_verdict/static/js/app.js` — sessionStorage save on join, URL param detection in `init()`, QR generation method, update `returnToLanding()`
- `src/iron_verdict/static/js/handlers.js` — clear sessionStorage in `handleSessionEnded()`
- `src/iron_verdict/static/css/components.css` — style QR code container
