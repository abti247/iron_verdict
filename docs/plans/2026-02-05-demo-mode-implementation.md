# Demo Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-click "Start Demo" button that creates a fresh session and opens 4 pre-positioned browser windows (judges and display) with automatic role joining.

**Architecture:** Single-file frontend enhancement using Alpine.js. No backend changes needed. Adds three new functions to the Alpine app: `startDemo()` (orchestrates session creation and window opening), `getWindowSpecs()` (calculates screen-aware window positioning), and initialization logic to detect demo parameters and auto-join. Existing WebSocket/session logic handles all connection management.

**Tech Stack:** Alpine.js, HTML, window.open() API

---

## Task 1: Add "Start Demo" Button to Landing Screen

**Files:**
- Modify: `src/judgeme/static/index.html:23-29`

**What:** Add a "Start Demo" button next to "Create New Session" on the landing page.

**Step 1: Locate the landing screen section**

The landing screen is in the HTML at lines 23-29. It currently has:
- "Create New Session" button
- "or" separator
- Input field for joining
- "Join Session" button

**Step 2: Add Start Demo button**

Add a new button after line 25 (after "Create New Session" button):

```html
<button @click="startDemo()" style="background: #17a2b8; color: white;">Start Demo</button>
```

Insert it between line 25 and line 26. The updated landing screen should look like:

```html
<!-- Landing screen -->
<div x-show="screen === 'landing'">
    <h2>Welcome</h2>
    <button @click="createSession()">Create New Session</button>
    <button @click="startDemo()" style="background: #17a2b8; color: white;">Start Demo</button>
    <p>or</p>
    <input type="text" x-model="joinCode" placeholder="Enter session code">
    <button @click="screen = 'role-select'">Join Session</button>
</div>
```

**Step 3: Visual verification in browser**

Once the Alpine.js functions are added (Task 2 & 3), you'll see the button rendered on the landing page with a teal color to distinguish it from other buttons.

---

## Task 2: Add Window Positioning Utility Function

**Files:**
- Modify: `src/judgeme/static/index.html:128-321` (inside the `judgemeApp()` function, before the closing brace)

**What:** Add the `getWindowSpecs()` function that calculates screen-aware window dimensions and positions.

**Step 1: Locate insertion point**

Find the `judgemeApp()` function that starts around line 128. At the end of the function (before line 321 where the function closes), add the `getWindowSpecs()` method.

**Step 2: Add getWindowSpecs() method**

Insert this method into the `judgemeApp()` return object (add it after the `returnToRoleSelection()` method, before the closing `};`):

```javascript
getWindowSpecs(sessionCode) {
    const sw = window.screen.width;
    const sh = window.screen.height;
    const jw = Math.floor(sw / 3);  // judge width
    const jh = Math.floor(sh / 2);  // judge height
    const dw = sw;                  // display width (full)
    const dh = Math.floor(sh / 2);  // display height

    const baseUrl = `${window.location.origin}/?code=${sessionCode}`;

    return {
        leftJudge: {
            url: `${baseUrl}&demo=left_judge`,
            params: `width=${jw},height=${jh},left=0,top=0`
        },
        centerJudge: {
            url: `${baseUrl}&demo=center_judge`,
            params: `width=${jw},height=${jh},left=${jw},top=0`
        },
        rightJudge: {
            url: `${baseUrl}&demo=right_judge`,
            params: `width=${jw},height=${jh},left=${2*jw},top=0`
        },
        display: {
            url: `${baseUrl}&demo=display`,
            params: `width=${dw},height=${dh},left=0,top=${jh}`
        }
    };
}
```

**Step 3: Understand the function**

This function:
- Gets screen dimensions from `window.screen.width/height`
- Calculates judge width as 1/3 of screen, height as 1/2
- Calculates display width as full screen, height as 1/2
- Returns an object with URL and window.open() parameters for each window
- URLs include the session code and demo role as URL parameters

**Step 4: Verify structure**

The function should be syntactically valid JavaScript object method notation. It should have the same indentation as other methods like `returnToRoleSelection()`.

---

## Task 3: Add Demo Mode Orchestration Function

**Files:**
- Modify: `src/judgeme/static/index.html:128-321` (inside the `judgemeApp()` function)

**What:** Add the `startDemo()` async function that creates a session and opens 4 windows.

**Step 1: Locate insertion point**

In the `judgemeApp()` return object, add the `startDemo()` method after `getWindowSpecs()` (before the closing `};`):

```javascript
async startDemo() {
    try {
        // Create session
        const response = await fetch('/api/sessions', { method: 'POST' });
        if (!response.ok) {
            alert('Failed to create session. Please try again.');
            return;
        }
        const data = await response.json();
        const sessionCode = data.session_code;

        // Calculate window positions
        const specs = this.getWindowSpecs(sessionCode);

        // Open all 4 windows
        window.open(specs.leftJudge.url, 'leftJudge', specs.leftJudge.params);
        window.open(specs.centerJudge.url, 'centerJudge', specs.centerJudge.params);
        window.open(specs.rightJudge.url, 'rightJudge', specs.rightJudge.params);
        window.open(specs.display.url, 'display', specs.display.params);

        // Return to landing
        this.screen = 'landing';
    } catch (error) {
        alert('Failed to start demo. Please try again.');
        console.error('Demo mode error:', error);
    }
}
```

**Step 2: Understand the function**

This function:
- Uses `async` because it fetches from the API
- POSTs to `/api/sessions` to create a new session
- Extracts the session code from the response
- Calls `getWindowSpecs()` to get window positioning
- Opens 4 windows with `window.open()` using the specs
- Returns the original window to the landing screen
- Shows user-friendly error messages if session creation fails

**Step 3: Verify error handling**

The function handles:
- Network errors (fetch fails)
- API errors (response not ok)
- General exceptions (catch block)

---

## Task 4: Add URL Parameter Detection & Auto-Join Logic

**Files:**
- Modify: `src/judgeme/static/index.html:128-146` (inside `judgemeApp()` function, before the return statement)

**What:** Detect `?demo=` and `?code=` URL parameters and auto-join the session if present.

**Step 1: Locate initialization code**

Find the start of the `judgemeApp()` function's return object. The function starts with property definitions like:
```javascript
screen: 'landing',
sessionCode: '',
joinCode: '',
```

**Step 2: Add initialization logic**

Right before the closing of the return statement (but still inside the return object), after all the method definitions but before the final `};`, add an initialization immediately-invoked function:

```javascript
init() {
    // Check URL parameters on load
    const urlParams = new URLSearchParams(window.location.search);
    const demoRole = urlParams.get('demo');
    const sessionCode = urlParams.get('code');

    if (demoRole && sessionCode) {
        // Skip to role selection and auto-join
        this.sessionCode = sessionCode;
        this.joinCode = sessionCode;
        // Defer the join to allow Alpine to finish initialization
        setTimeout(() => this.joinSession(demoRole), 100);
    } else {
        // Normal landing screen
        this.screen = 'landing';
    }
}
```

Then, immediately after the closing `};` of the `judgemeApp()` function definition, add a call to initialize:

```javascript
// Get the app object
const app = judgemeApp();
// Run initialization
app.init();
// Return the app for Alpine
return app;
```

**IMPORTANT:** The `judgemeApp()` function currently has `return { ... };` wrapping all the properties and methods. You need to refactor it so that:
1. It creates the object with all properties/methods
2. Calls the `init()` method
3. Returns that object to Alpine

**Current structure:**
```javascript
function judgemeApp() {
    return {
        screen: 'landing',
        // ... more properties
        // ... methods
    };
}
```

**New structure:**
```javascript
function judgemeApp() {
    return {
        screen: 'landing',
        // ... more properties
        // ... methods
        init() {
            // initialization code here
        }
    };
}
```

Then add the initialization call to the `init()` method itself, OR use Alpine's `x-init` directive in the HTML.

**Alternative (simpler):** Add `x-init="init()"` to the container div:

```html
<div class="container" x-data="judgemeApp()" x-init="init()">
```

This triggers the `init()` method when Alpine loads the component.

**Step 3: Understand the logic**

- `URLSearchParams` parses query string parameters
- If both `demo` and `code` parameters exist, it sets up for auto-join
- Uses `setTimeout` to defer the join (gives Alpine time to fully initialize)
- Otherwise, shows the normal landing screen
- The `init()` method runs automatically when the page loads

---

## Task 5: Test Auto-Join Parameter Detection

**Files:**
- Test in browser (manual testing)

**What:** Verify that URL parameters trigger auto-joining without manual role selection.

**Step 1: Start the application**

Run the application:
```bash
cd /c/Users/alexa/Documents/00_projects/judgeme/.worktrees/feature-demo-mode
source ../../.venv/Scripts/activate
python run.py
```

Application runs at `http://localhost:8000`

**Step 2: Test auto-join with manual URL**

1. Open browser and navigate to: `http://localhost:8000/?code=TEST123&demo=left_judge`
2. You should NOT see the landing page or role selection
3. You should see an attempt to join the session as left_judge
4. You should see an error message because the session code doesn't exist (expected)

**Step 3: Verify error handling**

The error message should be: "Failed to join session: Session does not exist"

This confirms the auto-join logic is working. The error is expected because we're using a fake session code.

---

## Task 6: Test "Start Demo" Button End-to-End

**Files:**
- Test in browser (manual testing)
- `src/judgeme/static/index.html` (no changes)

**What:** Test the complete demo mode flow from landing page.

**Prerequisites:**
- Application running at `http://localhost:8000`
- Pop-up blocker disabled (or allowed for localhost)

**Step 1: Open the landing page**

Navigate to `http://localhost:8000` in a browser

**Step 2: Click "Start Demo" button**

You should see:
- The "Start Demo" button on the landing page (teal color)
- 4 new browser windows open (may open as tabs or windows depending on browser settings)
- Each window positioned according to the layout (judges top, display bottom)
- All windows show the same session code

**Step 3: Verify window layout**

- Judge windows should be narrower (1/3 width each)
- Display window should be full width
- Judge windows at top, display window at bottom
- Exact positioning depends on screen size

**Step 4: Verify all windows connected**

In each window:
- Window shows session code at top
- Judges show voting buttons
- Center judge shows timer controls
- Display shows large circles for judge lights

**Step 5: Verify auto-join worked**

Click the session code in any window - it should NOT navigate or show role selection (you're already in a role).

**Step 6: Verify original window returned to landing**

The original window (where you clicked "Start Demo") should now show the landing page again, ready for another demo.

**Step 7: Test demo functionality**

- Try voting on one judge window
- Verify vote is locked
- Check that display window shows the light
- Test timer start/reset in center judge window
- Verify all functionality works as expected

---

## Task 7: Test Pop-up Blocker Scenarios

**Files:**
- Browser settings (no code changes)

**What:** Verify behavior when pop-up blocker prevents windows from opening.

**Step 1: Enable pop-up blocker**

In your browser settings, enable pop-up blocking for localhost.

**Step 2: Click "Start Demo"**

When pop-up blocker is active:
- Some or all 4 windows may fail to open
- Browser shows pop-up blocker notification
- Original window returns to landing (code still executes)

**Step 3: Allow pop-ups**

- Click the browser's pop-up blocker notification
- Allow pop-ups for localhost
- Click "Start Demo" again
- All 4 windows should open

**Step 4: Verify user feedback**

The browser's native pop-up blocker UI is the only feedback. Consider if you need to add an explicit message (not required by design, but could be nice-to-have).

---

## Task 8: Test Edge Cases

**Files:**
- Browser (manual testing)

**What:** Verify edge cases don't break the feature.

**Step 1: Very small screen**

If you can simulate a small screen (browser dev tools), click "Start Demo":
- Windows should still calculate positioning correctly
- They may overlap (expected with very small screens)
- No JavaScript errors should occur

Run in browser console:
```javascript
// Verify window specs are calculated
const app = Alpine.$data(document.querySelector('[x-data]'));
app.getWindowSpecs('TEST123');
```

You should see an object with all 4 window specs.

**Step 2: Very large screen**

On a large monitor:
- Windows should be properly sized (1/3 width for judges, full width for display)
- Positioning should be accurate

**Step 3: Close one demo window**

- Click "Start Demo" to open 4 windows
- Close one judge window
- Other 3 windows should continue working normally
- Session doesn't require all 4 windows to be open

**Step 4: Create second demo while first is running**

- Click "Start Demo" (opens 4 windows, creates session ABC123)
- In original window, click "Start Demo" again
- New 4 windows should open with a NEW session code (e.g., ABC124)
- Verify the codes are different between the two demos

---

## Task 9: Commit Changes

**Files:**
- Modified: `src/judgeme/static/index.html`

**Step 1: Review changes**

In the worktree, check what changed:
```bash
cd /c/Users/alexa/Documents/00_projects/judgeme/.worktrees/feature-demo-mode
git diff src/judgeme/static/index.html
```

You should see:
- Added "Start Demo" button in landing screen (~2 lines)
- Added `getWindowSpecs()` method (~25 lines)
- Added `startDemo()` method (~20 lines)
- Added `init()` method (~15 lines)
- Added `x-init="init()"` to container div (1 line)

Total: ~60-65 lines of additions

**Step 2: Run tests to verify nothing broke**

```bash
source ../../.venv/Scripts/activate
pytest
```

All 30 tests should pass.

**Step 3: Create commit**

```bash
git add src/judgeme/static/index.html
git commit -m "feat: add one-click demo mode

- Add 'Start Demo' button to landing page
- Create session and open 4 pre-positioned windows
- Judges positioned at top (1/3 width each), display at bottom (full width)
- Windows auto-join with correct roles via URL parameters
- Original window returns to landing for additional demos

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

**Step 4: Verify commit**

```bash
git log -1
```

You should see the new commit with the message.

---

## Summary

This plan adds demo mode in a single file with 4 new Alpine.js functions:

1. **`getWindowSpecs(sessionCode)`** - Calculates screen-aware window positioning
2. **`startDemo()`** - Creates session and opens 4 windows
3. **`init()`** - Detects demo parameters and auto-joins
4. **Landing screen button** - Triggers `startDemo()`

Total changes: ~65 lines in `src/judgeme/static/index.html`, zero backend changes.

The feature leverages existing session creation and WebSocket joining logic, making it low-risk and straightforward to implement.

