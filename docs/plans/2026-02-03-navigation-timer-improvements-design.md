# Navigation & Timer Reset Improvements Design

**Date:** 2026-02-03
**Feature:** Timer reset on next lift, browser back button navigation, clickable session code

## Overview

Three interconnected improvements to JudgeMe's user experience:

1. **Timer Reset on Next Lift** - When center judge clicks "Next Lift", timer resets to 60 seconds and stops counting
2. **Browser Back Button Navigation** - Back button returns to role selection screen (preserves session code)
3. **Clickable Session Code** - Clicking session code on judge/display screens navigates back to role selection

## Architecture & Data Flow

### Timer Management
- Currently: "Next Lift" resets voting but timer continues running
- Solution: Add `stopTimer()` call in `reset_for_next_lift` message handler
- Both judge and display screens will see timer reset to 60

### Navigation Stack
- Role selection screen becomes the "hub" for role switching
- Users can return via: browser back button OR clicking session code
- Session code preserved when returning to role selection (allows quick role change)
- WebSocket closes cleanly on intentional navigation (no error alerts)

### Session Code Interaction
- Make session code clickable on both judge and display screens
- Click handler performs: close WebSocket → reset state → navigate to role selection
- Requires `intentionalNavigation` flag to prevent error alerts on intentional disconnect

## Implementation Details

### Timer Reset (Frontend Only)
**File:** `src/judgeme/static/index.html`

In `handleMessage()` function, update the `reset_for_next_lift` handler:
```javascript
} else if (message.type === 'reset_for_next_lift') {
    this.resetVoting();
    this.stopTimer();  // ADD THIS LINE
    if (this.role === 'display') {
        this.displayVotes = { left: null, center: null, right: null };
        this.displayStatus = 'Waiting for judges...';
    }
}
```

### Browser Back Button (Frontend)
**File:** `src/judgeme/static/index.html`

Add to Alpine.js app initialization:
1. Track `intentionalNavigation` flag (default: false)
2. Listen to `popstate` event
3. On back button: prevent default, set flag, close WebSocket, return to role selection
4. Skip error alert in `onclose` handler if flag is set

### Clickable Session Code (Frontend)
**File:** `src/judgeme/static/index.html`

1. Make session code display clickable on judge and display screens
2. Add click handler that:
   - Sets `intentionalNavigation = true`
   - Closes WebSocket
   - Resets state (selectedVote, voteLocked, resultsShown, etc.)
   - Returns to role selection while preserving sessionCode

## Data Flow Diagram

```
Judge/Display Screen
    ↓
User clicks back OR session code
    ↓
Set intentionalNavigation = true
    ↓
Close WebSocket cleanly
    ↓
Reset app state
    ↓
Navigate to role selection
    ↓
User can rejoin with different role
```

## Testing Considerations

- Timer stops and resets to 60 when "Next Lift" is clicked
- Browser back button on judge/display returns to role selection
- Session code clickable and functional on both judge and display screens
- No error alerts when intentionally navigating back
- Session code preserved for quick role switching
- Display screen can return to role selection without errors
- WebSocket properly closed on all navigation paths

## Open Questions

None—design is complete and approved.
