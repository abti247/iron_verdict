# JudgeMe MVP - User Flows

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## Overview

This document contains **8 Mermaid sequence diagrams** showing the visual workflows for all MVP features. These flows focus exclusively on judge voting mechanics with **NO athlete data management**.

**MVP Scope:** Pure judging interface test system
- Judges vote on numbered lifts ("Lift 1", "Lift 2", "Lift 3"...)
- Timer controls (CENTER judge)
- Vote reveal (audience display)
- Admin creates/deletes competition
- Judge position selection and release

---

## Flow 1: Admin Creates Competition

**Purpose:** Admin creates a new competition and receives 2 URLs for judges and audience.

```mermaid
sequenceDiagram
    participant Admin
    participant Browser
    participant Backend
    participant Database

    Admin->>Browser: Navigate to homepage
    Admin->>Browser: Click "Create Competition"
    Browser->>Admin: Show competition form

    Note over Admin,Browser: Admin fills form (name + date only)
    Admin->>Browser: Enter competition name
    Admin->>Browser: Enter competition date (optional)
    Admin->>Browser: Click "Create Competition"

    Browser->>Backend: POST /api/competitions<br/>{name, date}

    Note over Backend: Generate secure tokens (2 URLs + admin token)
    Backend->>Backend: Generate judgeToken (128-bit, shared by all 3 judges)
    Backend->>Backend: Generate audienceToken (128-bit)
    Backend->>Backend: Generate adminToken (128-bit, for deletion)

    Backend->>Database: INSERT Competition<br/>(name, date, status=ACTIVE, tokens)
    Database-->>Backend: Competition created (id, tokens)

    Note over Backend: Auto-create 10 numbered lifts
    Backend->>Database: INSERT Lift (liftNumber=1, status=IN_PROGRESS)
    Backend->>Database: INSERT Lift (liftNumber=2, status=PENDING)
    Backend->>Database: INSERT Lift (liftNumber=3, status=PENDING)
    Backend->>Database: ... INSERT Lifts 4-9 (status=PENDING)
    Backend->>Database: INSERT Lift (liftNumber=10, status=PENDING)
    Database-->>Backend: 10 lifts created

    Note over Backend: Build URLs with tokens
    Backend->>Backend: judgeUrl = /judge?token={judgeToken}
    Backend->>Backend: audienceUrl = /audience?token={audienceToken}

    Backend-->>Browser: 201 Created<br/>{competitionId, judgeUrl, audienceUrl, adminToken}

    Browser->>Admin: Display URLs + adminToken

    Note over Admin: Admin copies URLs
    Admin->>Admin: Save adminToken (for deletion)
    Admin->>Admin: Share judgeUrl with 3 judges
    Admin->>Admin: Share audienceUrl with audience display
```

**Key Points:**
- Only name + date entered (NO athlete data)
- System auto-generates 10 lifts numbered 1-10
- First lift (liftNumber=1) set to IN_PROGRESS
- Admin receives 2 URLs + adminToken

---

## Flow 2: Judge Position Selection

**Purpose:** Judges use shared URL to select their position (LEFT/CENTER/RIGHT).

```mermaid
sequenceDiagram
    participant Judge1
    participant Judge2
    participant Browser1
    participant Browser2
    participant Backend
    participant Database
    participant SocketIO

    Note over Judge1,Judge2: All 3 judges use same URL

    Judge1->>Browser1: Open judgeUrl
    Browser1->>Backend: GET /judge?token={judgeToken}
    Backend->>Database: Validate judgeToken
    Database-->>Backend: Token valid
    Backend-->>Browser1: Serve judge position selection page

    Browser1->>Judge1: Show position selection:<br/>LEFT | CENTER | RIGHT

    Note over Judge1: Judge1 selects CENTER
    Judge1->>Browser1: Click CENTER button

    Browser1->>Backend: POST /api/judge/select-position<br/>{token, position: CENTER, sessionId}

    Backend->>Database: INSERT JudgePosition<br/>(competitionId, position=CENTER, sessionId)
    Note over Database: UNIQUE(competitionId, position)<br/>prevents double-claiming
    Database-->>Backend: Position claimed

    Backend->>SocketIO: Emit position_claimed<br/>{position: CENTER}
    Backend-->>Browser1: 200 OK<br/>{position: CENTER, sessionId}

    Browser1->>Judge1: Show CENTER judge interface<br/>(timer controls + vote buttons)

    Note over Judge2: Judge2 opens same URL
    Judge2->>Browser2: Open judgeUrl
    Browser2->>Backend: GET /judge?token={judgeToken}
    Backend-->>Browser2: Serve judge position selection page

    SocketIO->>Browser2: position_claimed<br/>{position: CENTER}
    Browser2->>Judge2: Update UI: CENTER position taken<br/>Show: LEFT | RIGHT (grayed: CENTER)

    Judge2->>Browser2: Click LEFT button
    Browser2->>Backend: POST /api/judge/select-position<br/>{token, position: LEFT, sessionId}

    Backend->>Database: INSERT JudgePosition<br/>(competitionId, position=LEFT, sessionId)
    Database-->>Backend: Position claimed

    Backend->>SocketIO: Emit position_claimed<br/>{position: LEFT}
    Backend-->>Browser2: 200 OK<br/>{position: LEFT, sessionId}

    Browser2->>Judge2: Show LEFT judge interface<br/>(vote buttons only, read-only timer)
```

**Key Points:**
- Single shared URL for all 3 judges
- Server-side UNIQUE constraint prevents conflicts
- Real-time updates via Socket.IO
- CENTER judge gets timer controls, LEFT/RIGHT get voting only

---

## Flow 3: Judge Votes on Lift

**Purpose:** Judges vote (WHITE/RED) on current lift, result calculated when all 3 votes received.

```mermaid
sequenceDiagram
    participant JudgeL as Judge LEFT
    participant JudgeC as Judge CENTER
    participant JudgeR as Judge RIGHT
    participant Backend
    participant Database
    participant SocketIO
    participant Audience

    Note over JudgeL,JudgeR: Current lift: Lift 5

    JudgeL->>Backend: POST /api/votes<br/>{liftId: lift-5, judgePosition: LEFT,<br/>decision: WHITE}
    Backend->>Database: INSERT Vote<br/>(liftId=lift-5, judgePosition=LEFT, decision=WHITE)
    Database-->>Backend: Vote recorded (1 of 3)

    Backend->>SocketIO: Emit vote_submitted (internal)<br/>{liftId: lift-5, voteCount: 1}
    Backend-->>JudgeL: 201 Created<br/>{voteId, timestamp}

    Note over JudgeL,JudgeR: Vote indicator updates<br/>(judges see "1 of 3 voted")

    JudgeC->>Backend: POST /api/votes<br/>{liftId: lift-5, judgePosition: CENTER,<br/>decision: WHITE}
    Backend->>Database: INSERT Vote<br/>(liftId=lift-5, judgePosition=CENTER, decision=WHITE)
    Database-->>Backend: Vote recorded (2 of 3)

    Backend->>SocketIO: Emit vote_submitted (internal)<br/>{liftId: lift-5, voteCount: 2}
    Backend-->>JudgeC: 201 Created<br/>{voteId, timestamp}

    Note over JudgeL,JudgeR: Vote indicator: "2 of 3 voted"

    JudgeR->>Backend: POST /api/votes<br/>{liftId: lift-5, judgePosition: RIGHT,<br/>decision: RED}
    Backend->>Database: INSERT Vote<br/>(liftId=lift-5, judgePosition=RIGHT, decision=RED)
    Database-->>Backend: Vote recorded (3 of 3)

    Note over Backend: Calculate result
    Backend->>Backend: Count votes:<br/>2 WHITE, 1 RED → GOOD_LIFT

    Backend->>Database: UPDATE Lift<br/>SET result=GOOD_LIFT, status=COMPLETED, completedAt=now()
    Database-->>Backend: Lift updated

    Backend->>SocketIO: Emit lift_completed (PUBLIC)<br/>{liftId: lift-5, result: GOOD_LIFT,<br/>votes: [{LEFT: WHITE}, {CENTER: WHITE}, {RIGHT: RED}]}
    Backend-->>JudgeR: 201 Created<br/>{voteId, timestamp}

    SocketIO->>Audience: lift_completed event
    Note over Audience: ALL 3 vote circles update simultaneously<br/>Display: "GOOD LIFT"

    SocketIO->>JudgeC: lift_completed event
    Note over JudgeC: NEXT LIFT button becomes enabled
```

**Key Points:**
- Each judge can only vote once per lift (UNIQUE constraint)
- Votes hidden from audience until all 3 received
- Result calculated: 2-3 WHITE = GOOD_LIFT, 2-3 RED = NO_LIFT
- Simultaneous reveal maintains dramatic suspense

---

## Flow 4: CENTER Judge Advances to Next Lift

**Purpose:** CENTER judge presses NEXT LIFT button to move to next numbered lift.

```mermaid
sequenceDiagram
    participant JudgeC as CENTER Judge
    participant Backend
    participant Database
    participant SocketIO
    participant AllJudges as All Judges

    Note over JudgeC: Current lift completed (all 3 votes in)
    Note over JudgeC: NEXT LIFT button enabled

    JudgeC->>Backend: POST /api/lifts/lift-5/complete<br/>{sessionId}

    Backend->>Database: UPDATE Lift<br/>SET status=COMPLETED WHERE id=lift-5
    Database-->>Backend: Lift 5 completed

    Backend->>Database: SELECT next lift<br/>WHERE liftNumber=6 AND status=PENDING
    Database-->>Backend: Lift 6 found

    Backend->>Database: UPDATE Lift<br/>SET status=IN_PROGRESS WHERE id=lift-6
    Database-->>Backend: Lift 6 activated

    Backend->>Database: DELETE all votes for lift-6 (if any)
    Database-->>Backend: Votes cleared

    Backend->>SocketIO: Emit next_lift_started<br/>{liftId: lift-6, liftNumber: 6}
    Backend-->>JudgeC: 200 OK<br/>{currentLiftId: lift-5, nextLiftId: lift-6,<br/>nextLiftNumber: 6}

    SocketIO->>AllJudges: next_lift_started event
    Note over AllJudges: UI updates to Lift 6<br/>Timer resets to 60s (not started)<br/>Vote buttons re-enabled<br/>NEXT LIFT button disabled

    Note over JudgeC: CENTER judge must press<br/>START CLOCK separately
```

**Key Points:**
- Only CENTER judge can advance to next lift
- Button enabled only after all 3 votes received
- Timer resets to 60 seconds (not automatically started)
- All judge interfaces update via Socket.IO

---

## Flow 5: Audience Display Updates (Simultaneous Vote Reveal)

**Purpose:** Audience views timer and vote results with simultaneous reveal.

```mermaid
sequenceDiagram
    participant Audience
    participant Browser
    participant Backend
    participant SocketIO

    Audience->>Browser: Open audienceUrl
    Browser->>Backend: GET /audience?token={audienceToken}
    Backend->>Backend: Validate audienceToken
    Backend-->>Browser: Serve audience display page

    Browser->>SocketIO: join_competition<br/>{competitionId, token: audienceToken}
    SocketIO-->>Browser: Subscribed to competition events

    Browser->>Audience: Display:<br/>- Timer: 60 seconds<br/>- 3 empty vote circles (LEFT, CENTER, RIGHT)<br/>- Current lift: "Lift 5"

    Note over SocketIO: CENTER judge starts timer
    SocketIO->>Browser: clock_started<br/>{liftId, startTime, duration: 60}
    Browser->>Audience: Timer starts countdown: 60 → 59 → 58...

    loop Every second
        SocketIO->>Browser: clock_tick<br/>{remainingSeconds}
        Browser->>Audience: Update timer display<br/>Color: Green (>30s), Yellow (10-30s), Red (<10s)
    end

    Note over SocketIO: All 3 judges vote
    Note over SocketIO: (Votes NOT shown to audience yet)

    SocketIO->>Browser: lift_completed<br/>{liftId: lift-5, result: GOOD_LIFT,<br/>votes: [{LEFT: WHITE}, {CENTER: WHITE}, {RIGHT: RED}]}

    Note over Browser: SIMULTANEOUS reveal of all 3 votes
    Browser->>Audience: Show all 3 vote circles at once:<br/>LEFT: WHITE ✓ (green circle)<br/>CENTER: WHITE ✓ (green circle)<br/>RIGHT: RED ✗ (red circle)<br/><br/>Result banner: "GOOD LIFT"

    Note over Audience: Dramatic simultaneous reveal
```

**Key Points:**
- Audience sees timer countdown with color-coding
- Individual votes hidden until all 3 received
- ALL 3 vote circles appear simultaneously
- Result banner shown: "GOOD LIFT" or "NO LIFT"

---

## Flow 6: Judge Releases Position

**Purpose:** Judge releases their position so another judge can claim it.

```mermaid
sequenceDiagram
    participant Judge
    participant Browser
    participant Backend
    participant Database
    participant SocketIO
    participant OtherJudges

    Note over Judge: Judge wants to switch positions<br/>or leave

    Judge->>Browser: Click "RELEASE POSITION" button

    alt Timer is running (CENTER judge only)
        Browser->>Judge: Error: Cannot release position<br/>while timer is running
    else Timer not running OR LEFT/RIGHT judge
        Browser->>Backend: DELETE /api/judge/release-position<br/>{token, sessionId}

        Backend->>Database: DELETE JudgePosition<br/>WHERE competitionId AND sessionId
        Database-->>Backend: Position released

        Backend->>SocketIO: Emit position_released<br/>{position: CENTER}
        Backend-->>Browser: 200 OK<br/>{success: true}

        Browser->>Judge: Show position selection screen again<br/>LEFT | CENTER | RIGHT

        SocketIO->>OtherJudges: position_released<br/>{position: CENTER}
        Note over OtherJudges: CENTER position becomes available again
    end
```

**Key Points:**
- CENTER judge cannot release while timer running
- LEFT/RIGHT judges can release anytime
- Position becomes available for other judges
- Real-time updates via Socket.IO

---

## Flow 7: CENTER Judge Resets Clock

**Purpose:** CENTER judge resets timer to 60 seconds.

```mermaid
sequenceDiagram
    participant JudgeC as CENTER Judge
    participant Backend
    participant Database
    participant SocketIO
    participant AllDisplays

    Note over JudgeC: Timer is counting down<br/>Currently at 42 seconds

    JudgeC->>Backend: POST /api/lifts/lift-5/reset-clock<br/>{sessionId}

    Backend->>Database: UPDATE Lift<br/>SET timerStartedAt=NULL,<br/>timerResetCount=timerResetCount+1<br/>WHERE id=lift-5
    Database-->>Backend: Timer reset

    Backend->>SocketIO: Emit clock_reset<br/>{liftId: lift-5}
    Backend-->>JudgeC: 200 OK<br/>{liftId: lift-5, timerReset: true,<br/>timerResetCount: 1}

    SocketIO->>AllDisplays: clock_reset event
    Note over AllDisplays: Timer returns to 60 seconds (not started)<br/>All displays update simultaneously

    Note over JudgeC: CENTER judge must press<br/>START CLOCK again to restart
```

**Key Points:**
- Only CENTER judge can reset timer
- Timer returns to 60 seconds (not started)
- timerResetCount incremented (for statistics)
- CENTER judge must press START CLOCK to restart

---

## Flow 8: Admin Deletes Competition

**Purpose:** Admin manually deletes competition and all related data.

```mermaid
sequenceDiagram
    participant Admin
    participant Browser
    participant Backend
    participant Database
    participant SocketIO
    participant AllClients

    Note over Admin: Competition finished<br/>Admin wants to clean up data

    Admin->>Browser: Click "Delete Competition" button
    Browser->>Admin: Confirmation dialog:<br/>"Are you sure? This cannot be undone."

    Admin->>Browser: Click "Confirm Delete"
    Browser->>Backend: DELETE /api/competitions/comp-123<br/>Authorization: Bearer {adminToken}

    Backend->>Backend: Validate adminToken
    alt Invalid admin token
        Backend-->>Browser: 401 Unauthorized<br/>{error: "Invalid admin token"}
        Browser->>Admin: Show error message
    else Valid admin token
        Backend->>Database: DELETE Competition WHERE id=comp-123
        Note over Database: CASCADE deletes:<br/>- All lifts (10 lifts)<br/>- All votes<br/>- All judge positions
        Database-->>Backend: Competition deleted

        Backend->>SocketIO: Emit competition_deleted<br/>{competitionId: comp-123,<br/>message: "Competition has been deleted"}
        Backend-->>Browser: 200 OK<br/>{success: true, message: "Competition deleted"}

        Browser->>Admin: Show success message<br/>Redirect to homepage

        SocketIO->>AllClients: competition_deleted event
        Note over AllClients: All URLs become invalid<br/>Judge/Audience displays show:<br/>"Competition has ended"<br/>Redirect to homepage
    end
```

**Key Points:**
- Requires valid adminToken (128-bit entropy)
- CASCADE deletes all related data (lifts, votes, positions)
- Tokens become invalid immediately
- Socket.IO notifies all connected clients

---

## Summary

The MVP includes **8 comprehensive user flows** covering:

1. ✅ **Admin Creates Competition** - Generates 2 URLs, auto-creates 10 numbered lifts
2. ✅ **Judge Position Selection** - Shared URL with server-side position locking
3. ✅ **Judge Votes on Lift** - Vote submission with simultaneous reveal
4. ✅ **CENTER Judge Advances Lift** - NEXT LIFT button for lift progression
5. ✅ **Audience Display Updates** - Timer + vote reveal with dramatic suspense
6. ✅ **Judge Releases Position** - Position change capability
7. ✅ **CENTER Judge Resets Clock** - Timer reset to 60 seconds
8. ✅ **Admin Deletes Competition** - Manual deletion with CASCADE

**Not included in MVP:**
- ❌ Athlete data entry flows
- ❌ Weight update flows
- ❌ Plate loading calculator flows
- ❌ Competition Manager flows
- ❌ Remote Audience dashboard flows
- ❌ Historical statistics flows

**MVP Focus:** Pure judging interface mechanics - vote submission, timer controls, and real-time synchronization.

---

## Viewing These Diagrams

### GitHub
Mermaid diagrams render automatically in GitHub README and markdown files.

### VS Code
Install the "Markdown Preview Mermaid Support" extension to see diagrams in preview mode.

### Online Viewers
- [Mermaid Live Editor](https://mermaid.live/)
- Copy/paste diagram code to visualize and export

---

**Last Updated:** 2026-01-20
**Status:** MVP Specification Complete
