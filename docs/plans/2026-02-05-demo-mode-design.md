# Demo Mode Feature Design

**Date:** 2026-02-05

## Overview

A one-click demo mode that automatically creates a fresh session and opens 4 browser windows with screen-aware positioning:
- 3 judge windows (left, center, right) positioned in the top half, each taking 1/3 of screen width
- 1 display window positioned in the bottom half, taking full screen width
- All windows automatically join the same session with their respective roles

## Problem Statement

Currently, demonstrating the app requires:
1. Starting a fresh session manually
2. Opening 4 separate browser tabs/windows
3. Joining each with the correct role (left judge, center judge, right judge, display)

This is tedious and error-prone. Demo mode eliminates these steps with a single click.

## User Flow

1. User opens the app and sees the landing page
2. User clicks "Start Demo" button
3. App creates a new session via `POST /api/sessions`
4. App opens 4 browser windows simultaneously with correct positioning
5. Each window auto-joins the session with its role
6. User sees the demo running across 4 positioned windows
7. Original window returns to landing page (ready for another demo)

## Technical Design

### Architecture

- **Backend:** No changes required - reuses existing `/api/sessions` endpoint
- **Frontend:** Alpine.js additions for demo mode button and window orchestration
- **Window Management:** Uses `window.open()` with positioning parameters

### Window Layout (Screen-Aware)

All calculations based on `window.screen` dimensions:

```
Left Judge:
  - Width: screenWidth / 3
  - Height: screenHeight / 2
  - Position: (0, 0)

Center Judge:
  - Width: screenWidth / 3
  - Height: screenHeight / 2
  - Position: (screenWidth / 3, 0)

Right Judge:
  - Width: screenWidth / 3
  - Height: screenHeight / 2
  - Position: (2 * screenWidth / 3, 0)

Display:
  - Width: screenWidth
  - Height: screenHeight / 2
  - Position: (0, screenHeight / 2)
```

### Backend Implementation

**No code changes needed.** Existing infrastructure handles everything:
- Session creation via `/api/sessions` endpoint
- WebSocket joining via `/ws` endpoint
- Session state management in `session.py`
- Connection management in `connection.py`

### Frontend Implementation

#### 1. Add Demo Button to Landing Screen

Add to the landing page HTML:
```html
<button @click="startDemo()">Start Demo</button>
```

#### 2. URL Parameter Detection on App Load

Alpine.js should check for URL parameters on initialization:
- `?demo=left_judge` or `?demo=center_judge` or `?demo=right_judge` or `?demo=display`
- `?code=ABC123` (session code)

If both parameters exist:
- Set `sessionCode` to the code parameter
- Immediately call `joinSession(demo_role)`
- Skip landing/role-selection screens

#### 3. Demo Mode Function

Add `startDemo()` function to Alpine.js:

```javascript
async startDemo() {
  try {
    // Create session
    const response = await fetch('/api/sessions', { method: 'POST' });
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
  }
}
```

#### 4. Window Positioning Utility

Add `getWindowSpecs()` function:

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

#### 5. Auto-Join Logic

Modify the app initialization to detect demo parameters and auto-join:

```javascript
// Check URL parameters on load
const urlParams = new URLSearchParams(window.location.search);
const demoRole = urlParams.get('demo');
const sessionCode = urlParams.get('code');

if (demoRole && sessionCode) {
  // Skip to role selection and auto-join
  this.sessionCode = sessionCode;
  this.joinCode = sessionCode;
  this.joinSession(demoRole);
  // Don't show landing screen
} else {
  // Normal landing screen
  this.screen = 'landing';
}
```

## Testing Strategy

### Manual Testing Checklist

**Basic Flow:**
- [ ] Click "Start Demo" on landing page
- [ ] Verify 4 windows open simultaneously
- [ ] Verify correct layout: judges top 1/3 width each, display bottom full width
- [ ] Verify all 4 windows show same session code
- [ ] Verify original window returns to landing

**Functionality:**
- [ ] Left judge can select and lock a vote
- [ ] Center judge can select and lock a vote, plus has timer controls
- [ ] Right judge can select and lock a vote
- [ ] Display shows judge lights when votes locked
- [ ] Timer works (start/reset by center judge)
- [ ] Can proceed to next lift
- [ ] Can end session

**Edge Cases:**
- [ ] Pop-up blocker enabled → show friendly message
- [ ] Very small screen → windows position correctly even if overlapped
- [ ] Browser back button in demo window → returns to role selection
- [ ] Close one demo window → other 3 continue working
- [ ] Create another demo from landing → new session created, new windows opened

### No New Test Code Required

All existing tests in `tests/` directory continue to pass. Demo mode uses only existing backend functionality.

## Edge Cases & Error Handling

**Pop-up Blocker:**
- Browser may block `window.open()` calls
- User will see browser pop-up blocker notification
- Can proceed by allowing pop-ups for the site

**Screen Sizing:**
- Very small screens: windows position correctly but may overlap
- Very large screens: windows position correctly with plenty of space
- Calculation uses `Math.floor()` to prevent fractional pixels

**Network Issues:**
- If `/api/sessions` fails: Show alert "Failed to start demo"
- If WebSocket connection fails: Existing error handling applies

**Window Closing:**
- If user closes one demo window: Other 3 continue normally
- If user closes original window: 4 demo windows stay open
- Closing all 4: No cleanup needed, session expires after 4 hours

## Files to Modify

- `src/judgeme/static/index.html` - Add button, URL parameter detection, startDemo() function, getWindowSpecs() function

## Files NOT Modified

- `src/judgeme/main.py` - No changes
- `src/judgeme/session.py` - No changes
- `src/judgeme/connection.py` - No changes
- `src/judgeme/config.py` - No changes
- `tests/` - No changes

## Implementation Complexity

**Low** - Only frontend changes, reuses all existing backend logic.

**Lines of code:** ~50-70 lines of Alpine.js in index.html

## Success Criteria

✅ One-click demo setup from landing page
✅ 4 windows open with correct screen-aware positioning
✅ All windows auto-join same session with correct roles
✅ Original window returns to landing for subsequent demos
✅ All existing functionality works unchanged
