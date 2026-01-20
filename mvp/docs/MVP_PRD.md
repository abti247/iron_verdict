# JudgeMe MVP - Product Requirements Document
## Judge Voting System

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## 1. Executive Summary

JudgeMe MVP is an **ultra-simplified judge voting system** designed to test the core mechanics of powerlifting competition judging. The MVP focuses exclusively on:

- **Judge position selection** (LEFT/CENTER/RIGHT)
- **Vote submission** (WHITE/RED lights)
- **Timer controls** (60-second countdown by CENTER judge)
- **Audience vote reveal** (simultaneous display after all 3 votes)
- **Lift progression** (CENTER judge advances to next lift)

### What's NOT in MVP

The MVP explicitly **excludes** all athlete management, weight tracking, and equipment features:
- ❌ NO athlete data (no names, no weights)
- ❌ NO barbell weight calculations or plate loading
- ❌ NO Competition Manager, Athlete Manager, or Platform Loader roles
- ❌ NO groups, flights, or competition structure
- ❌ NO rack heights, safety heights, or equipment setup

### MVP Scope Summary

**3 Personas:**
1. Admin (creates competition, deletes it)
2. Judges (3 positions: LEFT/CENTER/RIGHT)
3. Venue Audience (big screen display)

**2 URLs + Admin Token:**
1. Judge URL (shared by all 3 judges)
2. Audience URL (for big screen)
3. Admin Token (for deletion)

**Simple Numbered Lifts:**
- Judges vote on "Lift 1", "Lift 2", "Lift 3"... up to "Lift 10"
- No athlete names or weight displayed
- Pure voting interface testing

---

## 2. MVP Scope

### In Scope ✅

**Core Features:**
1. **Competition Creation (Admin)**
   - Simple form: Competition name + date
   - System generates 2 URLs (Judge, Audience)
   - Admin receives admin token for deletion

2. **Judge Position Selection**
   - Shared judge URL for all 3 judges
   - Position selection screen (LEFT/CENTER/RIGHT)
   - Server-side locking (first-come, first-served)
   - Real-time updates when positions taken

3. **CENTER Judge Controls**
   - START CLOCK button (60-second countdown)
   - RESET CLOCK button
   - NEXT LIFT button (advances to next numbered lift)
   - WHITE/RED vote buttons
   - RELEASE POSITION button (disabled during timer)

4. **LEFT/RIGHT Judge Controls**
   - WHITE/RED vote buttons only
   - Read-only timer display
   - RELEASE POSITION button

5. **Vote Changing**
   - Judges can change vote BEFORE all 3 votes submitted
   - Confirmation dialog in UI
   - After 3rd vote: Voting locked (403 Forbidden)

6. **Lift Progression**
   - CENTER judge controls when to advance
   - "NEXT LIFT" button enabled after all 3 votes received
   - Advances from Lift 1 → Lift 2 → ... → Lift 10
   - Timer resets to 60 seconds (not started)

7. **Audience Display**
   - 60-second countdown timer (color-coded)
   - 3 vote light circles (LEFT, CENTER, RIGHT)
   - **Simultaneous reveal** when all 3 votes received
   - Result banner: "GOOD LIFT" or "NO LIFT"
   - Lift number display ("Lift 5")

8. **Competition Deletion**
   - Admin can manually delete competition
   - Cascade deletes all data (lifts, votes, positions)
   - URLs become invalid

### Out of Scope ❌

**Features NOT in MVP:**
- Competition Manager (athlete data entry)
- Athlete Manager (live weight updates)
- **Platform Loader (barbell calculations, plate loading)**
- Competition Host (announcer display)
- Remote Audience dashboard (home viewing)
- Historical statistics
- Groups and flights organization
- Multi-platform support
- Auto-deletion after 3 days
- Break management
- Video replay
- Email notifications

---

## 3. User Personas

### 3.1 Admin - Competition Coordinator

**Name:** Sarah (from full system documentation)

**Role:** Creates and manages competitions

**Responsibilities:**
- Create competition (name + date)
- Share judge URL with judges
- Share audience URL for big screen
- Delete competition when done

**User Story:**
> "As an admin, I want to quickly create a competition and get shareable URLs so I can start judging immediately without complex setup."

**Pain Points Addressed:**
- No complicated setup or configuration
- No athlete data to manage (not needed for MVP)
- Simple creation process (< 1 minute)

**Goals:**
- Create competition in under 60 seconds
- Successfully share URLs with judges and audience
- Delete competition cleanly after use

**Technical Details:**
- Receives admin token after creation (for deletion)
- Saves token securely for later use
- No authentication required for creation

---

### 3.2 Judges (3 Positions)

#### 3.2a CENTER Judge (Head Referee)

**Name:** Marcus (from full system documentation)

**Role:** Head referee with timer controls and lift progression

**Responsibilities:**
- Select CENTER position on shared URL
- Start/reset 60-second timer
- Vote on lifts (WHITE/RED)
- Advance to next lift when voting complete
- Release position when needed

**User Story:**
> "As a head referee, I want to control the timer and advance lifts so I can manage the flow of the competition."

**Interface Elements:**
- NEXT LIFT button (top of screen, purple)
- START CLOCK button (blue)
- RESET CLOCK button (orange)
- WHITE LIGHT button (green, 80px height)
- RED LIGHT button (red, 80px height)
- RELEASE POSITION button (disabled during timer)
- Timer display (large font, color-coded)

**Pain Points Addressed:**
- Large, easily-pressable buttons on mobile
- Clear visual hierarchy (NEXT LIFT at top)
- Timer controls separated from voting buttons

**Goals:**
- Vote accurately on every lift
- Control timer without errors
- Advance smoothly to next lift

---

#### 3.2b LEFT/RIGHT Judges (Side Referees)

**Name:** Jessica (from full system documentation)

**Role:** Side referee with voting capability only

**Responsibilities:**
- Select LEFT or RIGHT position
- Vote on lifts (WHITE/RED)
- View timer countdown (read-only)
- Release position when needed

**User Story:**
> "As a side referee, I want a simple voting interface without distracting timer controls so I can focus solely on judging the lift."

**Interface Elements:**
- WHITE LIGHT button (green, 80px height)
- RED LIGHT button (red, 80px height)
- Timer display (read-only, for reference)
- RELEASE POSITION button

**Pain Points Addressed:**
- Simplified interface (no clock controls to accidentally press)
- Large voting buttons for quick decisions
- Timer visible for awareness but not distracting

**Goals:**
- Vote quickly and accurately
- No accidental timer presses

---

### 3.3 Venue Audience

**Name:** Alex (from full system documentation)

**Role:** Big screen display for venue audience

**Viewing Experience:**
- Large timer countdown (visible from 30+ feet)
- 3 judge vote circles (LEFT, CENTER, RIGHT labels)
- Lift number ("Lift 5")
- **Simultaneous vote reveal** (dramatic suspense)
- Result banner (GOOD LIFT / NO LIFT)

**User Story:**
> "As a spectator, I want to see the timer and votes clearly from the back of the venue so I can follow the competition."

**Interface Elements:**
- Timer: Green (60-30s) → Yellow (29-10s) → Red (9-0s)
- Vote circles: Grey (waiting) → Green (WHITE) / Red (RED)
- Result banner: Green background (GOOD LIFT) / Red background (NO LIFT)

**Pain Points Addressed:**
- All 3 votes appear simultaneously (no sequential reveal)
- Large fonts readable from 30+ feet
- Clear color coding (intuitive green/red)

**Goals:**
- Follow competition easily
- Feel dramatic suspense before vote reveal
- Understand results instantly

---

## 4. Core Features (Detailed)

### 4.1 Competition Creation

**Admin Workflow:**
1. Admin navigates to homepage
2. Clicks "Create Competition" button
3. Enters competition name (required)
4. Optionally enters competition date
5. Clicks "Create" button

**System Behavior:**
1. Validates competition name (not empty, max 200 chars)
2. Generates 3 cryptographically secure tokens (128-bit):
   - Judge Token (shared by all 3 judges)
   - Audience Token (for big screen)
   - Admin Token (for deletion)
3. Creates competition record with status `ACTIVE`
4. Auto-creates 10 lifts (numbered 1-10)
   - Lift 1: status `IN_PROGRESS`
   - Lifts 2-10: status `PENDING`
5. Displays success page with:
   - Judge URL: `https://judgeme.app/judge?token=<judgeToken>`
   - Audience URL: `https://judgeme.app/audience?token=<audienceToken>`
   - Admin Token: `<adminToken>` (displayed separately for admin to copy)

**Success Criteria:**
- Competition created in < 60 seconds
- URLs displayed with copy buttons
- Admin saves admin token securely

**API Endpoint:** `POST /api/competitions`

---

### 4.2 Judge Position Selection

**Judge Workflow:**
1. Judge opens shared judge URL
2. Sees position selection screen with 3 large buttons:
   - [LEFT] [CENTER] [RIGHT]
3. Judge clicks desired position
4. System validates position availability
5. Position locked, judge proceeds to voting interface

**System Behavior:**
1. Checks if position already claimed (database UNIQUE constraint)
2. If available: Claims position, stores session ID
3. If taken: Returns 409 Conflict error
4. Socket.IO emits `position_claimed` event to all clients
5. Other judges see disabled button for claimed positions

**UI States:**
- **Available:** Green button, clickable
- **Claimed:** Grey button, disabled, shows "Taken"
- **Selected:** Current judge's position highlighted

**Success Criteria:**
- Position claimed in < 10 seconds
- No race conditions (server-side locking prevents double-claiming)
- Real-time updates (other judges see position taken instantly)

**API Endpoint:** `POST /api/judge/select-position`

**Socket.IO Event:** `position_claimed`

---

### 4.3 Judge Voting Interface

#### CENTER Position UI (Head Referee)

**Layout (Top to Bottom):**
```
┌─────────────────────────────────┐
│  Lift 5                         │
│                                 │
│  ┌─────────────────────────┐   │
│  │   ➡ NEXT LIFT          │   │ (Purple, 80px)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   TIMER: 0:45           │   │ (Color-coded)
│  └─────────────────────────┘   │
│                                 │
│  ┌───────────┐ ┌───────────┐   │
│  │ ▶ START  │ │ ↻ RESET   │   │ (Blue/Orange)
│  │  CLOCK   │ │  CLOCK    │   │
│  └───────────┘ └───────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   ✓ WHITE LIGHT         │   │ (Green, 80px)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   ✗ RED LIGHT           │   │ (Red, 80px)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   RELEASE POSITION      │   │ (Disabled if timer running)
│  └─────────────────────────┘   │
└─────────────────────────────────┘
```

**Button States:**
- **NEXT LIFT:**
  - Disabled (grey) until all 3 votes received
  - Enabled (purple) after voting complete
  - On click: Advances to next lift

- **START CLOCK:**
  - Enabled when timer stopped
  - Disabled when timer running
  - On click: Begins 60-second countdown

- **RESET CLOCK:**
  - Enabled when timer running
  - On click: Stops timer, returns to 60s

- **VOTE BUTTONS:**
  - Large (80px+ height) for easy pressing
  - Immediate visual feedback on press
  - "Change Vote" button appears after voting

- **RELEASE POSITION:**
  - Disabled when timer running (prevents accidental release)
  - Enabled when timer stopped

---

#### LEFT/RIGHT Position UI (Side Referees)

**Layout (Top to Bottom):**
```
┌─────────────────────────────────┐
│  Lift 5                         │
│                                 │
│  ┌─────────────────────────┐   │
│  │   TIMER: 0:45           │   │ (Read-only)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   ✓ WHITE LIGHT         │   │ (Green, 80px)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   ✗ RED LIGHT           │   │ (Red, 80px)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │   RELEASE POSITION      │   │
│  └─────────────────────────┘   │
└─────────────────────────────────┘
```

**Key Differences from CENTER:**
- No NEXT LIFT button
- No START/RESET CLOCK buttons
- Timer display only (cannot control)
- Simplified, focused interface

---

### 4.4 Vote Submission and Changing

**Vote Submission Workflow:**
1. Judge presses WHITE or RED button
2. System validates judge has claimed position
3. Vote stored in database (liftId + judgePosition unique)
4. Socket.IO emits `vote_submitted` event (internal, not shown to audience)
5. Vote count incremented (1/3, 2/3, 3/3)
6. "Change Vote" button appears

**Vote Changing Workflow:**
1. Judge presses "Change Vote" button
2. Confirmation dialog: "Change vote to RED LIGHT?"
3. Judge confirms
4. System checks if 3 votes already submitted
5. If < 3 votes: Update allowed, emit `vote_changed` event
6. If 3 votes: Return 403 Forbidden error

**Result Calculation (After 3rd Vote):**
1. System counts WHITE vs RED votes
2. Result determined:
   - 2-3 WHITE lights → `GOOD_LIFT`
   - 2-3 RED lights → `NO_LIFT`
3. Lift status changed to `COMPLETED`
4. Socket.IO emits `lift_completed` event with result + all 3 votes
5. Audience display updates (simultaneous reveal)

**Success Criteria:**
- Vote submission latency < 300ms
- Vote change allowed before 3rd vote
- Vote change blocked after 3rd vote (403 error)
- Result calculation correct (2 WHITE = GOOD_LIFT)

**API Endpoints:**
- `POST /api/votes` (submit vote)
- `PUT /api/votes/:voteId` (change vote)

---

### 4.5 Timer Controls (CENTER Judge Only)

**Start Clock Workflow:**
1. CENTER judge presses "START CLOCK" button
2. System validates CENTER judge position
3. Timer starts at 60 seconds
4. `timerStartedAt` timestamp saved to database
5. Socket.IO emits `clock_started` event
6. Server emits `clock_tick` event every second (60, 59, 58... 0)
7. All displays (judges, audience) update in real-time

**Timer Color Coding:**
- **Green:** 60-30 seconds remaining
- **Yellow:** 29-10 seconds remaining
- **Red:** 9-0 seconds remaining

**Reset Clock Workflow:**
1. CENTER judge presses "RESET CLOCK" button
2. System validates CENTER judge position
3. Timer stops, returns to 60 seconds
4. `timerResetCount` incremented in database
5. Socket.IO emits `clock_reset` event
6. All displays reset to 60 seconds

**Timer Expiration (Reaches 0):**
1. Timer reaches 0:00
2. Socket.IO emits `clock_expired` event
3. Timer displays "TIME" in red
4. **Does NOT auto-fail lift** (judges still vote normally)
5. CENTER judge has discretion to allow lift or not

**Success Criteria:**
- Timer synchronized across all displays (±1 second tolerance)
- START/RESET only accessible to CENTER judge (403 error for others)
- Timer expiration does not interfere with voting

**API Endpoints:**
- `POST /api/lifts/:liftId/start-clock`
- `POST /api/lifts/:liftId/reset-clock`

**Socket.IO Events:**
- `clock_started`
- `clock_tick` (every second)
- `clock_reset`
- `clock_expired`

---

### 4.6 Lift Progression (NEXT LIFT Button)

**CENTER Judge Workflow:**
1. All 3 judges vote on current lift
2. System calculates result, emits `lift_completed` event
3. "NEXT LIFT" button becomes enabled (purple)
4. CENTER judge presses "NEXT LIFT" button
5. System marks current lift as `COMPLETED`
6. Next lift status changed to `IN_PROGRESS`
7. Timer remains at 60 seconds (not started)
8. Socket.IO emits `next_lift_started` event
9. All displays update to show new lift number
10. CENTER judge presses "START CLOCK" when ready

**Last Lift Handling:**
1. CENTER judge completes Lift 10 (last lift)
2. System detects no more pending lifts
3. "NEXT LIFT" button shows "Competition Complete"
4. Message: "All lifts finished. Admin can now delete competition."

**Success Criteria:**
- NEXT LIFT only enabled after all 3 votes (enforced client + server)
- Lift number increments correctly (1 → 2 → 3... → 10)
- Timer does NOT auto-start on new lift
- Smooth transition (< 500ms) between lifts

**API Endpoint:** `POST /api/lifts/:liftId/complete`

**Socket.IO Event:** `next_lift_started`

---

### 4.7 Audience Display

**Display Elements:**
```
┌───────────────────────────────────────┐
│             Lift 5                    │
│                                       │
│        ┌─────────────┐                │
│        │   0:45      │                │ (Timer)
│        └─────────────┘                │
│                                       │
│     ◯         ◯         ◯             │ (Vote circles)
│    LEFT     CENTER     RIGHT          │
│                                       │
│  [Result Banner Appears Here]         │
└───────────────────────────────────────┘
```

**Vote Reveal Sequence:**
1. **Before voting:** All 3 circles grey
2. **During voting (1-2 votes in):** All circles remain grey (suspense!)
3. **After 3rd vote:**
   - Socket.IO receives `lift_completed` event
   - **All 3 circles update SIMULTANEOUSLY** (within 200ms)
   - Circles show GREEN (WHITE) or RED based on vote
   - Result banner appears below:
     - Green background: "GOOD LIFT"
     - Red background: "NO LIFT"

**Timer Display:**
- Large font (10em+)
- Color-coded: Green → Yellow → Red
- Visible from 30+ feet away
- Updates every second

**Font Sizes:**
- Lift number: 8em
- Timer: 10em
- Vote circles: 6em diameter
- Result banner: 6em

**Success Criteria:**
- All 3 votes appear simultaneously (no sequential reveal)
- Timer synchronized with judge displays (±1 second)
- Visible from 30+ feet away
- Result banner clear and immediate

**Socket.IO Events Listened:**
- `clock_tick` (timer updates)
- `lift_completed` (vote reveal)
- `next_lift_started` (new lift loaded)
- `clock_expired` (timer reaches 0)

---

### 4.8 Judge Position Release

**Release Position Workflow:**
1. Judge presses "RELEASE POSITION" button
2. Confirmation dialog: "Release CENTER position?"
3. Judge confirms
4. System validates:
   - Timer not running (for CENTER judge)
   - Session ID matches
5. Position record deleted from database
6. Socket.IO emits `position_released` event
7. Judge returned to position selection screen
8. Position becomes available for other judges

**Constraints:**
- **CENTER judge:** Cannot release while timer running (409 Conflict)
- **LEFT/RIGHT judges:** Can release anytime
- **Session ID validation:** Only judge who claimed position can release it

**Use Cases:**
- Judge needs bathroom break
- Judge feels fatigued, wants to switch position
- Wrong position selected by accident

**Success Criteria:**
- Release blocked when timer running (CENTER only)
- Position immediately available after release
- Other judges see position available in real-time

**API Endpoint:** `DELETE /api/judge/release-position`

**Socket.IO Event:** `position_released`

---

### 4.9 Competition Deletion

**Admin Workflow:**
1. Admin navigates to admin URL (with admin token)
2. Sees competition details and "Delete Competition" button
3. Clicks "Delete Competition"
4. Confirmation dialog: "Permanently delete competition and all data?"
5. Admin confirms
6. System deletes competition + CASCADE all data

**System Behavior:**
1. Validates admin token
2. Deletes competition record
3. CASCADE deletes:
   - All lifts (10 records)
   - All votes (up to 30 records)
   - All judge positions (up to 3 records)
4. Tokens become invalid
5. Socket.IO emits `competition_deleted` event
6. All clients disconnected, shown "Competition Deleted" message

**Success Criteria:**
- Deletion completes in < 2 seconds
- All data removed from database
- URLs become invalid immediately
- Clients notified in real-time

**API Endpoint:** `DELETE /api/competitions/:competitionId`

**Socket.IO Event:** `competition_deleted`

---

## 5. Database Schema Summary

(See [MVP_DATABASE_SCHEMA.md](./MVP_DATABASE_SCHEMA.md) for full details)

**Tables (4 total):**
1. **Competition:** id, name, date, status, judgeToken, audienceToken, adminToken
2. **JudgePosition:** id, competitionId, position, sessionId, claimedAt
3. **Lift:** id, competitionId, liftNumber, status, result, timerStartedAt, timerResetCount
4. **Vote:** id, liftId, judgePosition, decision, timestamp

**Relationships:**
- Competition → Lifts (1:N)
- Competition → JudgePositions (1:N)
- Lift → Votes (1:N)

**Constraints:**
- UNIQUE(competitionId, position) - Prevents position double-claiming
- UNIQUE(liftId, judgePosition) - Prevents duplicate votes
- CASCADE DELETE - All child records deleted when competition deleted

---

## 6. API Endpoints Summary

(See [MVP_API.md](./MVP_API.md) for full details)

**Endpoints (7 total):**
1. `POST /api/competitions` - Create competition
2. `DELETE /api/competitions/:id` - Delete competition
3. `POST /api/judge/select-position` - Claim position
4. `DELETE /api/judge/release-position` - Release position
5. `POST /api/votes` - Submit vote
6. `PUT /api/votes/:voteId` - Change vote
7a. `POST /api/lifts/:liftId/start-clock` - Start timer
7b. `POST /api/lifts/:liftId/reset-clock` - Reset timer
7c. `POST /api/lifts/:liftId/complete` - Next lift

**Socket.IO Events (Server → Client):**
- `position_claimed`, `position_released`
- `clock_started`, `clock_tick`, `clock_reset`, `clock_expired`
- `vote_submitted` (internal), `lift_completed` (public)
- `next_lift_started`
- `competition_deleted`

---

## 7. Success Metrics

### Performance Targets

**Response Times:**
- Competition creation: < 1 minute
- Judge position selection: < 10 seconds
- Vote submission latency: < 300ms
- Real-time update delivery: < 500ms
- Timer synchronization: ±1 second tolerance

**Reliability:**
- Zero vote conflicts (server-side locking prevents)
- Zero position double-claims (UNIQUE constraint prevents)
- 100% data consistency (all votes counted correctly)

**Usability:**
- Judge interface mobile-friendly (320px+ width)
- Vote buttons minimum 80px height (WCAG compliance)
- Audience display readable from 30+ feet

### User Satisfaction

**Admin:**
- Creates competition successfully in first attempt
- Understands how to share URLs
- Can delete competition easily

**Judges:**
- Select position without confusion
- Vote accurately on every lift
- No accidental timer presses (CENTER judge)
- Understand when to advance to next lift (CENTER judge)

**Audience:**
- Follows competition easily
- Experiences dramatic suspense before vote reveal
- Understands results immediately

---

## 8. Technical Stack

### Frontend

**Framework:** React 18 + TypeScript
**Build Tool:** Vite
**Real-Time:** Socket.IO Client
**Styling:** Native CSS or minimal Tailwind
**State Management:** React Context API

**Key Libraries:**
- `socket.io-client` - Real-time updates
- `react-router-dom` - URL routing
- `uuid` - Session ID generation

### Backend

**Runtime:** Node.js 18+
**Framework:** Express + TypeScript
**Real-Time:** Socket.IO Server
**Database:** Prisma ORM + SQLite
**Authentication:** Token-based (no user accounts)

**Key Libraries:**
- `express` - REST API server
- `socket.io` - WebSocket server
- `@prisma/client` - Database ORM
- `crypto` - Token generation

### Database

**Database:** SQLite (single file)
**ORM:** Prisma
**Migrations:** Prisma Migrate

**Rationale:**
- No separate database server needed
- Single file deployment
- Perfect for MVP scale (100s of records)

---

## 9. Deployment

### Development

```bash
# Backend
cd backend
npm install
npx prisma migrate dev
npm run dev

# Frontend
cd frontend
npm install
npm run dev
```

**URLs:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:3001
- Socket.IO: ws://localhost:3001

### Production (MVP)

**Options:**
1. **Railway** - Easy deployment, free tier
2. **Render** - Free tier available
3. **VPS** - DigitalOcean, Linode (< $10/month)

**Requirements:**
- Node.js 18+ runtime
- 512MB RAM minimum
- 1GB disk space
- HTTPS recommended (Let's Encrypt)

---

## 10. Testing Strategy

### Manual Testing Scenarios

**Test 1: End-to-End Competition**
1. Create competition
2. Open judge URL on 3 devices
3. Claim LEFT, CENTER, RIGHT positions
4. CENTER judge starts clock
5. All 3 judges vote
6. Verify vote reveal is simultaneous on audience display
7. CENTER judge advances to next lift
8. Repeat for 10 lifts
9. Verify "Competition Complete" message
10. Admin deletes competition

**Test 2: Vote Changing**
1. Judge votes WHITE
2. "Change Vote" button appears
3. Judge changes to RED
4. Verify vote updated
5. Another judge votes
6. Third judge votes
7. Attempt to change vote → 403 Forbidden error

**Test 3: Position Locking**
1. Two judges click CENTER simultaneously
2. Verify only one succeeds (409 Conflict for other)
3. First judge sees CENTER interface
4. Second judge sees "Position already taken"

**Test 4: Timer Synchronization**
1. CENTER judge starts timer
2. Verify all displays show same time (±1 second)
3. CENTER judge resets timer
4. Verify all displays reset to 60 seconds

---

## 11. Future Enhancements (Post-MVP)

**Not in MVP, but potential additions:**
1. Athlete data management (names, weights)
2. Groups and flights organization
3. Platform loader (barbell calculations)
4. Competition Manager athlete entry
5. Athlete Manager live weight updates
6. Remote Audience dashboard (home viewing)
7. Historical statistics
8. Auto-deletion after 3 days
9. Break management
10. Multi-platform support

---

## 12. Glossary

**Lift:** A single numbered attempt (Lift 1, Lift 2, etc.) that judges vote on

**Judge Position:** One of three positions - LEFT, CENTER, or RIGHT

**WHITE Light:** Good lift vote (successful attempt)

**RED Light:** No lift vote (failed attempt)

**GOOD_LIFT:** Result when 2 or 3 judges vote WHITE

**NO_LIFT:** Result when 2 or 3 judges vote RED

**Timer:** 60-second countdown controlled by CENTER judge

**Simultaneous Reveal:** All 3 vote lights appear at same time on audience display

**Session ID:** Browser-generated unique ID to track judge who claimed position

**Token:** Cryptographically secure random string used for authentication

---

## 13. Appendix: UI Mockups

### Judge Position Selection Screen

```
┌─────────────────────────────────────────┐
│                                         │
│        Select Your Judge Position       │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │           LEFT                  │   │
│  │      Side Referee               │   │
│  │      (Vote Only)                │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │          CENTER                 │   │
│  │      Head Referee               │   │
│  │   (Timer + Vote + Next Lift)    │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │          RIGHT                  │   │
│  │      Side Referee               │   │
│  │      (Vote Only)                │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

---

**END OF MVP PRD**

---

**Document Version:** 1.0
**Last Updated:** 2026-01-20
**Maintained By:** JudgeMe MVP Team
**Status:** Ready for Implementation
