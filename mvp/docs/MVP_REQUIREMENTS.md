# JudgeMe MVP - Technical Requirements

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## Overview

This document specifies the **technical requirements** for the JudgeMe MVP - a pure judging interface test system. The MVP focuses exclusively on judge voting mechanics with **NO athlete data management**.

**MVP Scope:**
- Judges vote on numbered lifts ("Lift 1", "Lift 2", "Lift 3"...)
- Timer controls (CENTER judge)
- Vote reveal (audience display)
- Admin creates/deletes competition
- Judge position selection and release

**Out of Scope:**
- ❌ NO athlete data (no names, weights, equipment)
- ❌ NO Competition Manager features
- ❌ NO Athlete Manager features
- ❌ NO Platform Loader features (no barbell calculations)
- ❌ NO groups or flights organization
- ❌ NO historical statistics

---

## 1. Session Management & Competition Lifecycle

### FR1: Competition Creation

**Requirement:** System shall allow admin to create competition with minimal setup

**Inputs:**
- Competition name (required, string, max 200 characters)
- Competition date (optional, date format)

**Outputs:**
- Competition ID (UUID)
- Judge URL (shared by all 3 judges)
- Audience URL (for audience display)
- Admin token (for deletion)

**Behavior:**
- Generate 3 cryptographically secure tokens (128-bit entropy each):
  - `judgeToken` (shared by LEFT/CENTER/RIGHT judges)
  - `audienceToken` (for audience display)
  - `adminToken` (for admin to delete competition)
- Set competition status to `ACTIVE`
- Auto-create 10 lifts numbered 1-10
- Set first lift (liftNumber=1) to status `IN_PROGRESS`
- Remaining lifts (2-10) set to status `PENDING`

**Priority:** High

---

### FR2: Token Generation Security

**Requirement:** System shall generate cryptographically secure tokens

**Implementation:**
- Use Node.js `crypto.randomBytes(16)` for 128-bit entropy
- Convert to hexadecimal string (32 characters)
- Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
- Each token must be unique across all competitions

**Security Properties:**
- 2^128 possible tokens (immune to brute-force)
- No collision detection needed (astronomically unlikely)
- Tokens expire when competition deleted

**Priority:** High

---

### FR3: Competition Deletion

**Requirement:** Admin shall be able to manually delete competition

**Authentication:**
- Requires valid `adminToken` in Authorization header
- Format: `Authorization: Bearer {adminToken}`

**Behavior:**
- Validate adminToken matches competition
- DELETE Competition record from database
- CASCADE deletes all related data:
  - All lifts (10 lifts)
  - All votes (up to 30 votes: 3 judges × 10 lifts)
  - All judge positions (up to 3 positions)
- Emit Socket.IO `competition_deleted` event
- All URLs (judge, audience) become invalid immediately

**Error Handling:**
- 401 Unauthorized: Invalid or missing admin token
- 404 Not Found: Competition does not exist

**Priority:** High

---

### FR4: URL Format

**Requirement:** System shall generate shareable URLs with embedded tokens

**URL Formats:**
- Judge URL: `http://localhost:5173/judge?token={judgeToken}`
- Audience URL: `http://localhost:5173/audience?token={audienceToken}`

**Properties:**
- URLs are shareable (can be copied/pasted, sent via text/email)
- Tokens embedded in query parameter for simplicity
- No session cookies required
- Mobile-friendly (work on any device with browser)

**Priority:** High

---

### FR5: Competition Status

**Requirement:** System shall track competition lifecycle status

**Status Values:**
- `SETUP`: Competition created, not yet active (NOT USED IN MVP)
- `ACTIVE`: Competition in progress, judges can vote
- `ENDED`: Competition completed (NOT USED IN MVP - deleted instead)

**MVP Behavior:**
- All competitions created with status `ACTIVE`
- No competition ending workflow in MVP (admin deletes instead)

**Priority:** Medium

---

### FR6: Lift Auto-Creation

**Requirement:** System shall auto-create 10 numbered lifts when competition created

**Behavior:**
- Create 10 Lift records with sequential numbering: 1, 2, 3... 10
- Lift 1: status `IN_PROGRESS` (active, ready for voting)
- Lifts 2-10: status `PENDING` (not yet active)
- No athlete data associated with lifts
- Display label: "Lift 1", "Lift 2", etc.

**Database Fields:**
- `liftNumber` (Int): 1, 2, 3... 10
- `status` (String): PENDING, IN_PROGRESS, COMPLETED
- `result` (String, nullable): GOOD_LIFT, NO_LIFT (null until all 3 votes)
- `timerStartedAt` (DateTime, nullable): When CENTER judge started timer
- `timerResetCount` (Int, default 0): How many times timer was reset
- `createdAt` (DateTime): Timestamp
- `completedAt` (DateTime, nullable): When all 3 votes received

**Priority:** High

---

## 2. Judge Position Selection & Management

### FR10: Shared Judge URL

**Requirement:** All 3 judges shall use single shared URL

**Behavior:**
- Admin shares one judge URL with all 3 judges
- Judges open URL → see position selection screen
- Judges select LEFT, CENTER, or RIGHT position
- First-come, first-served position claiming
- Server-side locking prevents conflicts

**UI Display:**
- 3 large buttons: LEFT | CENTER | RIGHT
- Available positions: Full color, clickable
- Taken positions: Greyed out, not clickable
- Real-time updates via Socket.IO when position claimed

**Priority:** High

---

### FR10a: Judge Position Claiming

**Requirement:** Judge shall claim position (LEFT/CENTER/RIGHT)

**API Endpoint:** `POST /api/judge/select-position`

**Request Body:**
```json
{
  "token": "a1b2c3d4e5f6g7h8...",
  "position": "CENTER",
  "sessionId": "browser-session-id-123"
}
```

**Response (Success):**
```json
{
  "position": "CENTER",
  "sessionId": "browser-session-id-123",
  "claimedAt": "2026-02-15T14:30:00Z"
}
```

**Errors:**
- 401 Unauthorized: Invalid judge token
- 409 Conflict: Position already taken by another judge
- 400 Bad Request: Invalid position (must be LEFT, CENTER, or RIGHT)

**Database:**
- INSERT into JudgePosition table
- UNIQUE constraint on (competitionId, position) prevents double-claiming
- Race condition handling: Database constraint enforced, not application logic

**Socket.IO:**
- Emit `position_claimed` event to all clients
- Other judges see position greyed out immediately

**Priority:** High

---

### FR10b: Judge Position Release

**Requirement:** Judge shall be able to release claimed position

**API Endpoint:** `DELETE /api/judge/release-position`

**Request Body:**
```json
{
  "token": "a1b2c3d4e5f6g7h8...",
  "sessionId": "browser-session-id-123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Position released successfully"
}
```

**Constraints:**
- CENTER judge: Cannot release while timer is running
- LEFT/RIGHT judges: Can release anytime

**Errors:**
- 401 Unauthorized: Invalid token or session ID
- 409 Conflict: Cannot release while timer running (CENTER only)

**Database:**
- DELETE from JudgePosition table WHERE sessionId matches

**Socket.IO:**
- Emit `position_released` event to all clients
- Position becomes available for other judges

**Priority:** High

---

### FR10c: Position-Specific UI

**Requirement:** System shall adapt judge UI based on selected position

**CENTER Position UI:**
- NEXT LIFT button (advances to next lift in sequence)
- START CLOCK button (begins 60-second countdown)
- RESET CLOCK button (stops timer, returns to 60s)
- WHITE LIGHT button (vote good lift)
- RED LIGHT button (vote no lift)
- RELEASE POSITION button (disabled when timer running)
- Timer display (shows countdown)

**LEFT/RIGHT Position UI:**
- WHITE LIGHT button
- RED LIGHT button
- Timer display (read-only)
- RELEASE POSITION button (always enabled)
- NO clock controls (START/RESET/NEXT LIFT)

**Priority:** High

---

### FR10d: Session Persistence

**Requirement:** Judge position shall persist across page refreshes

**Implementation:**
- Store `sessionId` in browser localStorage
- On page load, check if position already claimed by this sessionId
- If yes: Show judge interface directly (skip position selection)
- If no: Show position selection screen

**Priority:** Medium

---

## 3. Judging & Voting

### FR11: Vote Submission

**Requirement:** Judge shall vote WHITE or RED for current lift

**API Endpoint:** `POST /api/votes`

**Request Body:**
```json
{
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "WHITE",
  "sessionId": "browser-session-id-123"
}
```

**Response:**
```json
{
  "voteId": "vote-uuid-456",
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "WHITE",
  "timestamp": "2026-02-15T14:35:00Z"
}
```

**Validation:**
- `decision` must be "WHITE" or "RED"
- `judgePosition` must be LEFT, CENTER, or RIGHT
- Judge must have claimed position (verify sessionId)
- Lift must be status `IN_PROGRESS`

**Errors:**
- 401 Unauthorized: Judge position not claimed
- 409 Conflict: Judge already voted for this lift (use PUT to change)
- 400 Bad Request: Invalid decision value

**Database:**
- INSERT into Vote table
- UNIQUE constraint on (liftId, judgePosition) prevents duplicate votes

**Socket.IO:**
- Emit `vote_submitted` event (internal only, NOT shown to audience)
- Event contains: `{liftId, voteCount}` (e.g., "1 of 3 voted")

**Priority:** High

---

### FR12: Vote Changing

**Requirement:** Judge shall be able to change vote before all 3 votes received

**API Endpoint:** `PUT /api/votes/:voteId`

**Request Body:**
```json
{
  "decision": "RED",
  "sessionId": "browser-session-id-123"
}
```

**Response:**
```json
{
  "voteId": "vote-uuid-456",
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "RED",
  "timestamp": "2026-02-15T14:35:30Z"
}
```

**Constraints:**
- Only allowed if fewer than 3 votes exist for lift
- Once 3rd vote submitted: Voting locked (403 Forbidden)
- Must be same sessionId that submitted original vote

**Errors:**
- 401 Unauthorized: Not authorized to change this vote
- 403 Forbidden: All 3 votes already received, voting locked

**UI:**
- Show confirmation dialog: "Are you sure you want to change your vote?"
- Update vote button highlight after change

**Socket.IO:**
- Emit `vote_changed` event

**Priority:** High

---

### FR13: Result Calculation

**Requirement:** System shall calculate lift result when 3rd vote received

**Logic:**
- Count WHITE votes and RED votes
- If 2 or 3 WHITE votes → Result: `GOOD_LIFT`
- If 2 or 3 RED votes → Result: `NO_LIFT`
- Impossible to have tie (3 votes total, odd number)

**Database:**
- UPDATE Lift SET result={result}, status=COMPLETED, completedAt=now()

**Socket.IO:**
- Emit `lift_completed` event (PUBLIC, shown to audience)
- Event contains:
  ```json
  {
    "liftId": "lift-uuid-123",
    "liftNumber": 5,
    "result": "GOOD_LIFT",
    "votes": [
      {"position": "LEFT", "decision": "WHITE"},
      {"position": "CENTER", "decision": "WHITE"},
      {"position": "RIGHT", "decision": "RED"}
    ],
    "completedAt": "2026-02-15T14:35:30Z"
  }
  ```

**Priority:** High

---

### FR14: Vote Display (Judges Only)

**Requirement:** Judges shall see vote count indicator (NOT individual votes)

**Display:**
- "0 of 3 voted" (no votes yet)
- "1 of 3 voted" (1 judge voted)
- "2 of 3 voted" (2 judges voted)
- "3 of 3 voted - Result: GOOD LIFT" (all voted, result shown)

**Privacy:**
- Judges do NOT see which other judges voted
- Judges do NOT see other judges' vote decisions
- Only vote count displayed

**Priority:** Medium

---

### FR15: Audience Vote Hiding

**Requirement:** Audience shall NOT see individual votes until all 3 received

**Behavior:**
- Vote submission events are internal only
- Audience display shows 3 empty circles while voting in progress
- After `lift_completed` event: ALL 3 circles update simultaneously
- Maintains dramatic suspense

**Priority:** High

---

## 4. CENTER Judge Lift Progression

### FR16: Next Lift Button

**Requirement:** CENTER judge shall advance to next lift after current lift completed

**UI Element:**
- Button label: "NEXT LIFT" or "➡ NEXT LIFT"
- Button color: Purple or distinct color (different from clock/voting buttons)
- Button size: Minimum 80px height (large, easy to tap)
- Position: Top of interface, above clock controls

**Enabled State:**
- Only after `lift_completed` event (all 3 judges voted)
- Greyed out / disabled during active lift

**Disabled State:**
- During active lift (less than 3 votes)
- Button appears greyed out, not clickable

**Priority:** High

---

### FR17: Next Lift Behavior

**Requirement:** Pressing NEXT LIFT shall advance to next numbered lift

**API Endpoint:** `POST /api/lifts/:liftId/complete`

**Headers:**
- `Authorization: Bearer {judgeToken}`
- `X-Judge-Position: CENTER`

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response (More lifts remaining):**
```json
{
  "currentLiftId": "lift-uuid-123",
  "currentLiftNumber": 5,
  "nextLiftId": "lift-uuid-124",
  "nextLiftNumber": 6
}
```

**Response (Last lift):**
```json
{
  "currentLiftId": "lift-uuid-130",
  "currentLiftNumber": 10,
  "nextLiftId": null,
  "message": "All lifts complete. Competition finished."
}
```

**Behavior:**
- Mark current lift as `COMPLETED` (if not already)
- Find next lift WHERE liftNumber = currentLiftNumber + 1
- Update next lift: SET status = `IN_PROGRESS`
- Timer remains at 60 seconds (not started)
- CENTER judge must press START CLOCK separately

**Errors:**
- 403 Forbidden: Not CENTER judge
- 409 Conflict: Current lift not yet completed (need 3 votes)

**Socket.IO:**
- Emit `next_lift_started` event
- All judge interfaces update to new lift
- Vote buttons re-enabled
- NEXT LIFT button disabled until 3 votes received

**Priority:** High

---

## 5. Timer Controls (CENTER Judge Only)

### FR-CLOCK-1: 60-Second Countdown Timer

**Requirement:** System shall implement 60-second countdown timer for lifts

**Timer Properties:**
- Duration: 60 seconds
- Start trigger: CENTER judge presses "START CLOCK" button
- Countdown: Decrements from 60 → 0 at 1-second intervals
- Expiration: Timer reaches 0:00, displays "TIME" (does NOT auto-fail lift)

**Priority:** High

---

### FR-CLOCK-2: Clock Control Buttons

**Requirement:** CENTER judge interface shall include clock control buttons

**UI Elements:**

**START CLOCK button:**
- Large, prominent button (minimum 80px height)
- Color: Blue or neutral color (distinct from voting buttons)
- Label: "START CLOCK" or "▶ START (60s)"
- Enabled: When timer not running
- Disabled: When timer already running

**RESET CLOCK button:**
- Similar size to START button
- Color: Orange or warning color
- Label: "RESET CLOCK" or "↻ RESET"
- Enabled: Always (even when timer running)
- Behavior: Stops countdown, returns to 60s

**Priority:** High

---

### FR-CLOCK-3: Start Clock API

**Requirement:** CENTER judge shall start 60-second countdown timer

**API Endpoint:** `POST /api/lifts/:liftId/start-clock`

**Headers:**
- `Authorization: Bearer {judgeToken}`
- `X-Judge-Position: CENTER` (validates CENTER position)

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response:**
```json
{
  "liftId": "lift-uuid-123",
  "timerStartedAt": "2026-02-15T14:36:00Z",
  "expiresAt": "2026-02-15T14:37:00Z"
}
```

**Database:**
- UPDATE Lift SET timerStartedAt = now() WHERE id = liftId

**Socket.IO:**
- Emit `clock_started` event: `{liftId, startTime, duration: 60}`
- Server begins emitting `clock_tick` events every second

**Errors:**
- 403 Forbidden: Not CENTER judge
- 409 Conflict: Timer already running

**Priority:** High

---

### FR-CLOCK-4: Clock Tick Events

**Requirement:** Server shall emit countdown events every second

**Socket.IO Event:** `clock_tick`

**Payload:**
```json
{
  "liftId": "lift-uuid-123",
  "remainingSeconds": 45
}
```

**Frequency:** Every 1 second

**Sequence:** 60, 59, 58, 57... 3, 2, 1, 0

**Client Behavior:**
- Update timer display in real-time
- Color coding:
  - Green: >30 seconds remaining
  - Yellow: 10-30 seconds remaining
  - Red: <10 seconds remaining

**Priority:** High

---

### FR-CLOCK-5: Reset Clock API

**Requirement:** CENTER judge shall reset timer to 60 seconds

**API Endpoint:** `POST /api/lifts/:liftId/reset-clock`

**Headers:**
- `Authorization: Bearer {judgeToken}`
- `X-Judge-Position: CENTER`

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response:**
```json
{
  "liftId": "lift-uuid-123",
  "timerReset": true,
  "timerResetCount": 1
}
```

**Behavior:**
- Stop countdown
- Return timer to 60 seconds (not started)
- Increment `timerResetCount` in database (for statistics)
- CENTER judge must press START again to restart countdown

**Database:**
- UPDATE Lift SET timerStartedAt = NULL, timerResetCount = timerResetCount + 1

**Socket.IO:**
- Emit `clock_reset` event: `{liftId}`
- All displays return timer to 60 seconds

**Priority:** High

---

### FR-CLOCK-6: Clock Expiration

**Requirement:** System shall emit event when timer reaches 0

**Socket.IO Event:** `clock_expired`

**Payload:**
```json
{
  "liftId": "lift-uuid-123",
  "expiredAt": "2026-02-15T14:37:00Z"
}
```

**Behavior:**
- Timer display shows "TIME" or "0:00"
- Visual/audio alert (optional)
- Does NOT auto-fail lift (judges must still vote)

**Rationale:**
- Powerlifting rules allow referee discretion
- Athlete may start lift at 0:01 and it may still be valid
- Technical issues shouldn't auto-fail

**Priority:** Medium

---

### FR-CLOCK-7: Server-Side Timer

**Requirement:** Timer countdown shall run on server (not client)

**Implementation:**
- Server starts Node.js interval timer
- Server emits `clock_tick` events every 1 second
- Clients display timer but don't compute countdown locally
- Prevents clock drift across devices

**Benefits:**
- All devices synchronized (judges, audience)
- No client-side manipulation possible
- Consistent timing regardless of device performance

**Priority:** High

---

## 6. Audience Display

### FR23: Audience Display Components

**Requirement:** Audience display shall show timer and vote results

**Components:**

**1. Timer Display:**
- Large countdown: "0:45" format (MM:SS)
- Color-coded:
  - Green: >30 seconds
  - Yellow: 10-30 seconds
  - Red: <10 seconds
- Font size: Very large (readable from 30+ feet)

**2. Vote Indicator Circles:**
- 3 circles representing judges: LEFT | CENTER | RIGHT
- Empty/grey circles while voting in progress
- After all 3 votes: Circles update simultaneously
  - WHITE vote: Green circle with checkmark ✓
  - RED vote: Red circle with X ✗

**3. Result Banner:**
- Large text: "GOOD LIFT" (green) or "NO LIFT" (red)
- Displayed after all 3 votes received
- Remains visible until next lift

**4. Current Lift Label:**
- Text: "Lift 5" (top of display)
- Simple, minimal

**Priority:** High

---

### FR24: Simultaneous Vote Reveal

**Requirement:** All 3 vote circles shall update simultaneously

**Behavior:**
- While voting: Show 3 empty/grey circles
- When `lift_completed` event received: Update ALL 3 circles at once
- No individual vote reveals (maintains suspense)

**Technical Implementation:**
- Listen for `lift_completed` Socket.IO event
- Event contains all 3 votes: `[{LEFT: WHITE}, {CENTER: WHITE}, {RIGHT: RED}]`
- Update DOM elements simultaneously (not sequentially)

**Priority:** High

---

### FR25: Audience Authentication

**Requirement:** Audience display shall use audienceToken for access

**URL Format:** `http://localhost:5173/audience?token={audienceToken}`

**Validation:**
- Backend validates audienceToken on page load
- If invalid: Show error message, redirect to homepage
- If valid: Subscribe to Socket.IO events for competition

**Socket.IO:**
- Client emits `join_competition` with audienceToken
- Server validates token, subscribes client to competition room

**Priority:** High

---

### FR26: Audience Display - Read-Only

**Requirement:** Audience display shall have NO interactive controls

**Behavior:**
- Pure display (no buttons, no input fields)
- Auto-updates via Socket.IO
- Cannot influence competition state
- Full-screen mode recommended

**Priority:** High

---

## 7. Real-Time Communication (Socket.IO)

### FR30: Socket.IO Events

**Requirement:** System shall use WebSocket for real-time updates

**Server → Client Events:**

**Position Management:**
- `position_claimed`: Judge claimed position
  ```json
  {"competitionId": "uuid-123", "position": "CENTER", "claimedAt": "..."}
  ```
- `position_released`: Judge released position
  ```json
  {"competitionId": "uuid-123", "position": "CENTER", "releasedAt": "..."}
  ```

**Timer Events:**
- `clock_started`: CENTER judge started timer
  ```json
  {"liftId": "...", "startTime": "...", "duration": 60}
  ```
- `clock_tick`: Countdown update (every second)
  ```json
  {"liftId": "...", "remainingSeconds": 45}
  ```
- `clock_reset`: CENTER judge reset timer
  ```json
  {"liftId": "..."}
  ```
- `clock_expired`: Timer reached 0
  ```json
  {"liftId": "...", "expiredAt": "..."}
  ```

**Voting Events:**
- `vote_submitted`: Judge voted (internal only, not shown to audience)
  ```json
  {"liftId": "...", "voteCount": 2}
  ```
- `lift_completed`: All 3 votes received (PUBLIC, shown to audience)
  ```json
  {
    "liftId": "...",
    "liftNumber": 5,
    "result": "GOOD_LIFT",
    "votes": [
      {"position": "LEFT", "decision": "WHITE"},
      {"position": "CENTER", "decision": "WHITE"},
      {"position": "RIGHT", "decision": "RED"}
    ],
    "completedAt": "..."
  }
  ```

**Lift Progression:**
- `next_lift_started`: CENTER judge advanced to next lift
  ```json
  {"liftId": "...", "liftNumber": 6}
  ```

**Competition Lifecycle:**
- `competition_deleted`: Admin deleted competition
  ```json
  {"competitionId": "...", "message": "Competition has been deleted"}
  ```

**Client → Server Events:**
- `join_competition`: Client subscribes to competition updates
  ```json
  {"competitionId": "...", "token": "..."}
  ```
- `leave_competition`: Client unsubscribes
  ```json
  {"competitionId": "..."}
  ```

**Priority:** High

---

### FR31: Socket.IO Rooms

**Requirement:** System shall use Socket.IO rooms for competition isolation

**Implementation:**
- Each competition has unique room ID (e.g., `competition-{competitionId}`)
- Clients join room when connecting: `socket.join('competition-uuid-123')`
- Server emits events to specific room: `io.to('competition-uuid-123').emit('...')`
- Prevents event leakage between competitions

**Priority:** High

---

### FR32: Reconnection Handling

**Requirement:** System shall handle network disconnections gracefully

**Behavior:**
- Socket.IO auto-reconnects by default
- On reconnect: Client re-emits `join_competition` event
- Server sends current state (lift number, timer value, positions claimed)
- Client updates UI to current state

**Priority:** Medium

---

## 8. Error Handling

### FR40: HTTP Status Codes

**Requirement:** API shall use standard HTTP status codes

**Status Codes:**
- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request body or parameters
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: Not authorized for this action (e.g., only CENTER judge can start clock)
- `404 Not Found`: Resource not found
- `409 Conflict`: Conflict with current state (e.g., position already taken, timer already running)
- `500 Internal Server Error`: Server error

**Priority:** High

---

### FR41: Error Response Format

**Requirement:** API errors shall return consistent JSON format

**Format:**
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

**Examples:**
```json
{"error": "Position already taken by another judge", "code": "POSITION_TAKEN"}
{"error": "Only CENTER judge can start timer", "code": "FORBIDDEN"}
{"error": "Invalid judge token", "code": "INVALID_TOKEN"}
```

**Priority:** High

---

## 9. Performance Requirements

### FR50: Vote Submission Latency

**Requirement:** Vote submission shall complete in <300ms

**Measurement:** Time from button press to database write + Socket.IO emit

**Target:** 95th percentile < 300ms

**Priority:** High

---

### FR51: Real-Time Update Latency

**Requirement:** Socket.IO events shall appear in <500ms

**Measurement:** Time from server emit to client UI update

**Target:** 95th percentile < 500ms

**Priority:** High

---

### FR52: Concurrent Audience Support

**Requirement:** System shall support 100 concurrent audience viewers

**Scope:** 100 connected Socket.IO clients in same competition room

**Performance:** No degradation in vote reveal latency

**Priority:** Medium

---

## 10. Technical Stack

### FR60: Frontend Technology

**Requirement:** Frontend shall use React 18 + TypeScript

**Dependencies:**
- React 18.x
- TypeScript 5.x
- Vite (build tool)
- Socket.IO Client 4.x

**Priority:** High

---

### FR61: Backend Technology

**Requirement:** Backend shall use Node.js + Express + TypeScript

**Dependencies:**
- Node.js 18+
- Express 4.x
- TypeScript 5.x
- Socket.IO 4.x
- Prisma 5.x (ORM)

**Priority:** High

---

### FR62: Database Technology

**Requirement:** System shall use SQLite database

**Rationale:**
- Single file database (no separate server needed)
- Simple deployment
- Perfect for MVP scope
- Sufficient for 100 concurrent users

**File Location:** `./dev.db` (in project root)

**Priority:** High

---

## 11. Mobile Responsiveness

### FR70: Mobile-First Design

**Requirement:** Judge interfaces shall be optimized for smartphones

**Button Sizes:**
- Minimum 80px height (easy to tap)
- Minimum 80px width
- Large, clear labels

**Font Sizes:**
- Button labels: Minimum 18px
- Timer display: Minimum 48px
- Lift number: Minimum 24px

**Priority:** High

---

### FR71: Supported Devices

**Requirement:** System shall work on common mobile devices

**Devices:**
- iPhone SE (320px width minimum)
- iPhone 12/13/14/15
- Samsung Galaxy S series
- iPad / Android tablets

**Browsers:**
- Safari (iOS)
- Chrome (Android)
- Firefox (mobile)

**Priority:** High

---

## Summary

The MVP includes **40+ functional requirements** covering:

**Session Management (6 requirements):**
- FR1-FR6: Competition creation, tokens, deletion, lifts

**Judge Position (5 requirements):**
- FR10-FR10d: Position selection, claiming, release, UI adaptation

**Judging & Voting (5 requirements):**
- FR11-FR15: Vote submission, changing, result calculation, display

**Lift Progression (2 requirements):**
- FR16-FR17: Next Lift button, behavior

**Timer Controls (7 requirements):**
- FR-CLOCK-1 to FR-CLOCK-7: 60-second countdown, start/reset/expire, server-side

**Audience Display (4 requirements):**
- FR23-FR26: Display components, simultaneous reveal, authentication, read-only

**Socket.IO (3 requirements):**
- FR30-FR32: Events, rooms, reconnection

**Error Handling (2 requirements):**
- FR40-FR41: HTTP status codes, error format

**Performance (3 requirements):**
- FR50-FR52: Latency targets, concurrent users

**Tech Stack (3 requirements):**
- FR60-FR62: React, Node.js, SQLite

**Mobile (2 requirements):**
- FR70-FR71: Mobile-first design, supported devices

**Total:** 42 functional requirements for MVP

**Not Included:**
- ❌ Competition Manager requirements (athlete entry, groups/flights)
- ❌ Athlete Manager requirements (weight updates)
- ❌ Platform Loader requirements (barbell calculations, plate loading)
- ❌ Competition Host requirements (announcer display)
- ❌ Remote Audience requirements (home dashboard)
- ❌ Historical statistics requirements
- ❌ Break management requirements
- ❌ Admin flight starting requirements

**MVP Focus:** Pure judging interface - vote submission, timer controls, and real-time synchronization.

---

**Last Updated:** 2026-01-20
**Status:** MVP Specification Complete
