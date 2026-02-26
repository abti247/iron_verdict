# Navigation, Reload & QR Code UX — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix accidental role-select exits, add auto-rejoin on page reload, and add a QR code to the role-select screen so judges can scan-to-join.

**Architecture:** Pure frontend changes — no backend modifications. Reload persistence uses `sessionStorage`. QR code uses QRCode.js from CDN. URL param `?session=XXXX` handled in `init()` provides the QR scan entry point; code is immediately stripped from URL via `history.replaceState`.

**Tech Stack:** Alpine.js v3, QRCode.js (qrcodejs@1.0.0 via jsdelivr CDN), sessionStorage API

---

## Task 1: Role-select back navigation

Remove the clickable session code on role-select. Add an explicit back button.

**Files:**
- Modify: `src/iron_verdict/static/index.html`

**Step 1: Remove `@click` from session code span**

In `index.html`, find:
```html
Session: <span class="code" @click="returnToLanding()" x-text="sessionCode"></span>
```
Change to:
```html
Session: <span class="code" x-text="sessionCode"></span>
```

**Step 2: Add back button inside the role panel**

After the closing `</div>` of `role-grid` and before the closing `</div>` of `role-panel`, add:
```html
        <div class="btn-row">
            <button class="btn-blood btn-blood-ghost" @click="returnToLanding()">
                &larr; Back to Start
            </button>
        </div>
```

**Step 3: Manual verify**

Run the app. Navigate to role-select:
- Confirm session code text is no longer clickable (cursor: default, no nav on click)
- Confirm "← Back to Start" button appears at bottom
- Confirm clicking it returns to landing and clears session code

**Step 4: Run existing backend tests**

```bash
pytest tests/ -v
```
Expected: all pass (no backend changes made)

**Step 5: Commit**

```bash
git add src/iron_verdict/static/index.html
git commit -m "feat: add back button to role-select, remove clickable session code"
```

---

## Task 2: QR code — CDN, HTML container, CSS

Add QRCode.js library and a placeholder div. Style the container.

**Files:**
- Modify: `src/iron_verdict/static/index.html`
- Modify: `src/iron_verdict/static/css/components.css`

**Step 1: Add QRCode.js CDN script to `<head>`**

In `index.html`, after the Alpine.js `<script>` block (around line 19), add:
```html
    <script
        src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"
        crossorigin="anonymous">
    </script>
```
Note: `qrcodejs@1.0.0` exposes a global `QRCode` constructor.

**Step 2: Add QR code div to role-select section**

In the role-select panel, after the `session-tag` div and before the `role-grid` div, add:
```html
        <div class="role-qr-wrap">
            <div id="qrcode"></div>
        </div>
```

The final role-select panel layout should be (top to bottom):
```
role-heading
session-tag
role-qr-wrap      <- new
role-grid
btn-row (back)    <- from task 1
```

**Step 3: Add CSS for QR container**

At the end of `src/iron_verdict/static/css/components.css`, add:
```css
/* ===== QR CODE ===== */
.role-qr-wrap {
    display: flex;
    justify-content: center;
    margin: 1rem 0;
}

.role-qr-wrap #qrcode {
    background: #fff;
    padding: 8px;
    line-height: 0;
}
```

The white background and padding ensure the QR code has a quiet zone on the dark app background.

**Step 4: Manual verify**

Navigate to role-select. An empty white box should appear above the role buttons (no QR yet — generation comes in Task 3).

**Step 5: Commit**

```bash
git add src/iron_verdict/static/index.html src/iron_verdict/static/css/components.css
git commit -m "feat: add QR code container to role-select screen"
```

---

## Task 3: QR code generation in app.js

Add the `generateQrCode()` method and trigger it whenever the screen transitions to `role-select`.

**Files:**
- Modify: `src/iron_verdict/static/js/app.js`

**Step 1: Add `generateQrCode()` method**

In `app.js`, add this method after `returnToRoleSelection()` (around line 253):
```javascript
        generateQrCode() {
            const el = document.getElementById('qrcode');
            if (!el || !this.sessionCode) return;
            while (el.firstChild) el.removeChild(el.firstChild);
            const url = window.location.origin + '/?session=' + this.sessionCode;
            new QRCode(el, {
                text: url,
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
            });
        },
```

Note: `while (el.firstChild) el.removeChild(el.firstChild)` safely clears the element without using innerHTML.

**Step 2: Add a screen watcher in `init()` to auto-generate QR**

In `init()`, before the `const params = window._demoParams;` line, add:
```javascript
            this.$watch('screen', (value) => {
                if (value === 'role-select' && this.sessionCode) {
                    setTimeout(() => this.generateQrCode(), 50);
                }
            });
```

This handles all navigation paths to role-select: create session, join by code, return from judge screen.

**Step 3: Manual verify**

1. Create a session → role-select → QR code renders with a URL like `http://localhost:PORT/?session=XXXXXXXX`
2. Use a QR scanner app (phone camera) to scan it — should open the browser at that URL (role-select won't auto-open until Task 4)
3. Join an existing session by code → role-select → QR renders
4. From judge screen, click session code → role-select → QR renders

**Step 4: Commit**

```bash
git add src/iron_verdict/static/js/app.js
git commit -m "feat: generate QR code on role-select screen"
```

---

## Task 4: URL entry point — `?session=XXXX` handling

Handle the URL param produced by QR code scans. Navigate to role-select and strip the code from the URL.

**Files:**
- Modify: `src/iron_verdict/static/js/app.js` (`init()` method)

**Step 1: Add URL param detection to `init()`**

In `init()`, before the `const params = window._demoParams;` line, add:
```javascript
            // QR code entry point: ?session=XXXX navigates to role-select
            const urlParams = new URLSearchParams(window.location.search);
            const urlSession = urlParams.get('session');
            if (urlSession) {
                history.replaceState({}, '', '/');
                this.sessionCode = urlSession.trim().toUpperCase();
                this.joinCode = this.sessionCode;
                this.screen = 'role-select';
                setTimeout(() => this.generateQrCode(), 50);
                return;
            }
```

Place this BEFORE the demo params check (demo URLs use `?code=&demo=`, not `?session=`, so there is no conflict).

**Step 2: Manual verify — QR scan flow**

1. Create a session and note the code (e.g. `ABCD1234`)
2. Open a new browser tab and navigate to `http://localhost:PORT/?session=ABCD1234`
3. Expected: role-select screen shown for that session, URL in address bar is `/` (cleaned)
4. Expected: QR code renders
5. Select a role — should connect and show the judge/display screen

**Step 3: Run backend tests**

```bash
pytest tests/ -v
```
Expected: all pass

**Step 4: Commit**

```bash
git add src/iron_verdict/static/js/app.js
git commit -m "feat: handle ?session= URL param as QR code entry point"
```

---

## Task 5: sessionStorage auto-rejoin

Save session context on join. Auto-rejoin on reload. Clear on exit.

**Files:**
- Modify: `src/iron_verdict/static/js/app.js`
- Modify: `src/iron_verdict/static/js/handlers.js`

**Step 1: Save to sessionStorage in `joinSession()`**

In `app.js`, at the start of `joinSession(role)`, add as the first line:
```javascript
            const code = this.sessionCode || this.joinCode;
            sessionStorage.setItem('iv_session', JSON.stringify({ code, role }));
```

Note: `code` is already computed on the next line in the original — move that line up so the sessionStorage call can reference it. The start of `joinSession` becomes:
```javascript
        joinSession(role) {
            const code = this.sessionCode || this.joinCode;
            sessionStorage.setItem('iv_session', JSON.stringify({ code, role }));
            this.role = role;
            this.sessionCode = code;
            this.connectionStatus = 'reconnecting';
            // ... rest unchanged
```

**Step 2: Clear sessionStorage in `returnToLanding()`**

In `app.js`, in `returnToLanding()`, add as the first line:
```javascript
            sessionStorage.removeItem('iv_session');
```

**Step 3: Clear sessionStorage in `handleSessionEnded()`**

In `handlers.js`, in `handleSessionEnded()`, add before `app.screen = 'landing'`:
```javascript
    sessionStorage.removeItem('iv_session');
```

**Step 4: Add auto-rejoin in `init()`**

In `app.js`, in `init()`, after the URL param block (Task 4) and before `const params = window._demoParams;`, add:
```javascript
            // Reload recovery: auto-rejoin previous session
            const stored = sessionStorage.getItem('iv_session');
            if (stored) {
                try {
                    const { code, role } = JSON.parse(stored);
                    this.sessionCode = code;
                    this.joinCode = code;
                    setTimeout(() => this.joinSession(role), 100);
                    return;
                } catch (_e) {
                    sessionStorage.removeItem('iv_session');
                }
            }
```

**Step 5: Manual verify — reload flow**

1. Create a session, join as Left Judge
2. Reload the page (F5)
3. Expected: auto-rejoins as Left Judge in the same session
4. From judge screen, click session code → role-select → click "← Back to Start"
5. Reload
6. Expected: landing page (sessionStorage cleared by `returnToLanding()`)
7. Create a session, join as display, head judge ends the session
8. Reload
9. Expected: landing page (sessionStorage cleared by `handleSessionEnded()`)

**Step 6: Manual verify — demo mode not affected**

Start demo mode. Confirm demo still opens and works normally.

**Step 7: Run backend tests**

```bash
pytest tests/ -v
```
Expected: all pass

**Step 8: Commit**

```bash
git add src/iron_verdict/static/js/app.js src/iron_verdict/static/js/handlers.js
git commit -m "feat: auto-rejoin session on page reload via sessionStorage"
```
