# JudgeMe - Live Powerlifting Judging Application Design

**Date:** 2026-01-31
**Status:** Design Approved

## Overview

JudgeMe is a web-based real-time judging application for powerlifting competitions. It enables three judges to independently make lift decisions (White/Red/Blue/Yellow lights) on their own devices, with results displayed synchronously on a shared display screen for the audience.

## Core Requirements

- **Primary Use Case:** Live competition judging
- **Users:** 3 judges (Left, Center/Head, Right) + 1 display device
- **Voting System:** 4-color lights (White=valid, Red/Blue/Yellow=invalid for different reasons per IPF rules)
- **Real-time Sync:** All devices connected via WebSockets through cloud/internet
- **Session-based:** Simple session codes, ephemeral (no data persistence)
- **Timer:** 60-second countdown for lift attempts
- **Head Judge Control:** Center judge controls timer and session flow

## Technology Stack

- **Backend:** FastAPI (Python) with native WebSocket support
- **Frontend:** HTML + Alpine.js for lightweight reactivity
- **Session Storage:** In-memory dictionary (no database)
- **Communication:** WebSockets for real-time bidirectional messaging
- **Deployment:** Web application accessible via browser

## Architecture

### Session Model

Each session has a unique 6-character alphanumeric code (e.g., "ABC123"). Sessions are stored in-memory:

```python
sessions = {
    "ABC123": {
        "judges": {
            "left": {
                "connected": True,
                "is_head": False,
                "current_vote": None,
                "locked": False
            },
            "center": {
                "connected": True,
                "is_head": True,
                "current_vote": None,
                "locked": False
            },
            "right": {
                "connected": True,
                "is_head": False,
                "current_vote": None,
                "locked": False
            }
        },
        "displays": [<websocket_connections>],
        "state": "waiting",  # or "showing_results"
        "timer_state": "idle",  # or "running", "expired"
        "last_activity": <timestamp>
    }
}
```

### Security Considerations

- **6-character codes:** ~2.2 billion combinations, sufficient for ephemeral sessions
- **Role enforcement:** Once a judge position is taken, no one else can claim it
- **Activity-based expiration:** Sessions auto-delete after 4 hours of no voting activity
- **Manual termination:** Head judge can end session with confirmation prompt

### Connection Flow

1. User opens web app → sees "Join Session" or "Create Session"
2. If creating: backend generates random 6-char code, initializes empty session
3. User enters session code and selects role:
   - "Left Judge"
   - "Center Judge (Head)"
   - "Right Judge"
   - "Display"
4. WebSocket connection established with role metadata
5. Server validates role not already taken, adds to session
6. Client receives current session state (timer, votes, results if showing)

## User Interfaces

### Judge Interface

**Role Selection Screen:**
- Four role buttons: Left Judge, Center Judge (Head), Right Judge, Display
- Taken roles are disabled/grayed out
- Session code displayed prominently

**Judge Voting Screen:**

**Layout:**
- **Top Bar:** Session code, timer display (60-second countdown), connection status
- **Main Area:** Four large voting buttons arranged in 2x2 grid:
  - White (valid lift)
  - Red (invalid - generic/depth)
  - Blue (invalid - specific infraction)
  - Yellow (invalid - specific infraction)
- **Button States:**
  - Default: All enabled, neutral styling
  - Selected: Chosen button highlighted, "Lock In" button appears below
  - Locked: All buttons disabled, locked choice shown prominently

**Head Judge Additional Controls (Center Judge Only):**
- "Start Timer" / "Reset Timer" button (always visible)
- "Next Lift" button (enabled only when results are showing)
- "End Session" button (always available, triggers confirmation dialog)

**Voting Flow:**
1. Judge taps a color → button highlights, can change freely
2. Judge taps "Lock In" → vote sent to server, buttons disabled
3. When all 3 judges lock in → results display on all devices
4. Head judge taps "Next Lift" → all devices reset for next attempt

### Display Interface

**Layout:**

**Top Section - Timer:**
- Large, prominent 60-second countdown
- Neutral color when idle/running, red when expired
- Always visible

**Middle Section - Judge Lights:**
- Three large circular indicators positioned horizontally:
  - **Left circle** = Left judge
  - **Center circle** = Center judge (Head)
  - **Right circle** = Right judge
- **No labels** - spatial position identifies the judge
- **States:**
  - Before all votes locked: Empty/gray circles
  - After all votes locked: All three circles simultaneously fill with colors

**Bottom Section (Optional):**
- Small status text: "Waiting for judges..." or "Results shown"

**Key Principle:** Display is read-only, no interaction needed.

## Core Flows

### 1. Voting Flow

**States:**
- **Waiting for lift:** Judges see enabled voting buttons
- **Vote selected:** Judge taps color, "Lock In" appears, can change
- **Vote locked:** Judge taps "Lock In", vote sent, buttons disabled
- **Results shown:** All 3 locked → display shows all colors simultaneously
- **Reset:** Head judge taps "Next Lift" → return to waiting state

**Messages:**
1. Judge selects color (no server message, local UI only)
2. Judge locks in → `{"type": "vote_lock", "color": "red"}`
3. Server validates → broadcasts to display: `{"type": "judge_voted", "position": "left"}` (no color)
4. All 3 locked → server broadcasts: `{"type": "show_results", "votes": {"left": "white", "center": "red", "right": "white"}}`
5. Head judge advances → `{"type": "next_lift"}` → server broadcasts: `{"type": "reset_for_next_lift"}`

### 2. Timer Flow

**Independent of voting state** - head judge can start/reset at any time.

**States:**
- **Idle:** Shows "60", not counting
- **Running:** Counts down 59, 58, 57... in normal color
- **Expired:** Shows "0" in red, stays at 0 (doesn't go negative)

**Messages:**
1. Head judge clicks "Start Timer" → `{"type": "timer_start"}`
2. Server broadcasts: `{"type": "timer_start", "server_timestamp": 1234567890.123}`
3. All clients calculate remaining time from timestamp (prevents drift)
4. Head judge clicks "Reset Timer" → `{"type": "timer_reset"}`
5. Server broadcasts: `{"type": "timer_reset"}`
6. All clients show "60" and stop counting

**Expiration:** Timer turns red, visual indicator only (no automatic action).

### 3. Session End Flow

**Triggered by:**
- Head judge manually ends session
- 4 hours of no voting activity (auto-expiration)

**Manual End:**
1. Head judge clicks "End Session"
2. Client shows confirmation: "Are you sure? This will disconnect all judges and the display"
3. User confirms → `{"type": "end_session_confirmed"}`
4. Server broadcasts: `{"type": "session_ended", "reason": "head_judge"}`
5. All WebSocket connections close
6. Session deleted from memory
7. All devices show "Session ended by head judge"

**Auto-expiration:**
1. Server checks last voting activity
2. If > 4 hours → broadcasts: `{"type": "session_ended", "reason": "timeout"}`
3. Same cleanup as manual end

## WebSocket Protocol

### Client → Server Messages

```javascript
// Session management
{"type": "join", "session_code": "ABC123", "role": "center_judge"}

// Voting
{"type": "vote_lock", "color": "red"}

// Head judge controls
{"type": "timer_start"}
{"type": "timer_reset"}
{"type": "next_lift"}
{"type": "end_session_confirmed"}
```

### Server → Client Messages

```javascript
// Join responses
{"type": "join_success", "role": "center_judge", "is_head": true, "session_state": {...}}
{"type": "join_error", "message": "Role already taken"}

// Vote updates
{"type": "judge_voted", "position": "left"}  // to display, no color revealed
{"type": "show_results", "votes": {"left": "white", "center": "red", "right": "white"}}

// Timer sync
{"type": "timer_start", "server_timestamp": 1234567890.123}
{"type": "timer_reset"}

// Flow control
{"type": "reset_for_next_lift"}
{"type": "session_ended", "reason": "head_judge"}  // or "timeout"

// Connection events
{"type": "judge_disconnected", "position": "right"}
{"type": "judge_reconnected", "position": "right"}
```

## Error Handling & Edge Cases

### Connection Issues

**Judge Disconnects Mid-Vote:**
- Server detects WebSocket close
- Broadcasts to display: `{"type": "judge_disconnected", "position": "left"}`
- Display shows disconnection indicator
- If judge reconnects: restores locked vote state if they had one
- If results showing: judge sees current results on rejoin

**Display Disconnects:**
- Judges continue voting normally
- On reconnect: display receives current session state
- No disruption to judging flow

**Head Judge Disconnects:**
- Session continues, other judges can vote
- Timer continues on all devices (client-side calculation)
- No one can advance to next lift until head judge returns
- On reconnect: head judge resumes control

### Session Edge Cases

**Full Session:**
- All three judge roles taken
- New joiner receives: `{"type": "join_error", "message": "All judge positions filled"}`

**Invalid Session Code:**
- Server responds: `{"type": "join_error", "message": "Session not found"}`

**Multiple Displays:**
- Allowed - multiple screens can show same results (useful for large venues)

**Activity Timeout:**
- 4 hours of no voting activity → auto-cleanup
- Broadcasts `{"type": "session_ended", "reason": "timeout"}`

## Testing Strategy

### Backend Testing

**Session Management:**
- Create session generates unique code
- Join with valid role succeeds
- Join with taken role returns error
- Join invalid session returns error
- Activity timeout triggers cleanup

**WebSocket Communication:**
- Message routing (judge vote → all clients)
- Broadcast logic (results shown to all)
- Connection/disconnection handling
- Reconnection with state restoration

**Voting State Machine:**
- Three votes locked triggers results
- Head judge advance resets state
- Timer start/reset broadcasts correctly

### Frontend Testing

**Manual Multi-Tab Testing (Primary for MVP):**
1. Open 4 browser tabs/windows
2. Join as Left Judge, Center Judge (Head), Right Judge, Display
3. Test voting flow: select colors, lock in, verify results
4. Test timer: start, reset, verify countdown on all tabs
5. Test disconnection: close tab, verify indicator, rejoin
6. Test session end: confirm dialog, verify all tabs disconnect

**UI State Validation:**
- Button enable/disable logic
- Color highlighting
- Timer countdown accuracy
- Display synchronization

### Load Testing (Optional for MVP)
- Simulate 10-20 concurrent sessions
- Verify memory usage
- Test session cleanup

## Implementation Phases

### Phase 1: Core Infrastructure
- FastAPI project setup
- WebSocket connection handling
- Session creation/joining
- Basic role validation

### Phase 2: Judge Interface
- Voting button UI
- Lock-in mechanism
- WebSocket message sending
- Basic state management

### Phase 3: Display Interface
- Three-circle layout
- Results synchronization
- Connection status indicators

### Phase 4: Timer System
- Timer UI on all interfaces
- Head judge controls
- Timestamp-based synchronization
- Expiration visual indicator

### Phase 5: Head Judge Controls
- Next lift functionality
- End session with confirmation
- State reset logic

### Phase 6: Error Handling
- Disconnection detection
- Reconnection with state restoration
- Activity-based expiration
- Edge case handling

### Phase 7: Polish & Testing
- UI refinement
- Multi-tab testing
- Performance optimization
- Documentation

## Open Questions

None - design is complete and approved for implementation.
