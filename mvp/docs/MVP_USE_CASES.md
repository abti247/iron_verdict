# JudgeMe MVP - Use Cases

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## Overview

This document describes the **7 core use cases** for the JudgeMe MVP (Minimum Viable Product). The MVP focuses exclusively on judge voting mechanics with NO athlete data, NO weight tracking, and NO barbell calculations.

**MVP Use Cases:**
1. UC1: Admin Creates Competition
2. UC2: Judge Selects Position
3. UC3: Judge Votes on Lift
4. UC4: CENTER Judge Advances to Next Lift
5. UC5: Audience Views Vote Results
6. UC6: Judge Releases Position
7. UC7: Admin Deletes Competition

**Out of Scope:**
- ❌ Competition Manager athlete entry (UC1a)
- ❌ Groups/Flights creation (UC1b)
- ❌ Admin starts flight (UC3)
- ❌ Athlete Manager weight updates (UC3a)
- ❌ Platform Loader plate calculator (UC3b)
- ❌ Remote Audience dashboard (UC4b)
- ❌ Historical dashboard (UC5)
- ❌ Competition Host (UC6)

---

## UC1: Admin Creates Competition

**ID:** UC1
**Actor:** Admin
**Preconditions:** None (no authentication required)
**Priority:** High (Core MVP functionality)

### Main Flow

1. Admin navigates to JudgeMe homepage
2. Admin clicks "Create Competition" button
3. System displays competition creation form
4. Admin enters competition name (e.g., "Test Competition")
5. Admin optionally enters competition date
6. Admin clicks "Create Competition" button
7. System validates input (competition name not empty)
8. System generates 3 cryptographically secure tokens (128-bit entropy):
   - Judge token (shared by all 3 judges)
   - Audience token (for big screen display)
   - Admin token (for deletion)
9. System creates competition record in database with status `ACTIVE`
10. System auto-creates 10 lifts (numbered 1-10):
    - Lift 1: status `IN_PROGRESS`
    - Lifts 2-10: status `PENDING`
11. System displays success page with 2 shareable URLs + admin token:
    - **Judge URL:** `https://judgeme.app/judge?token=<judgeToken>`
    - **Audience URL:** `https://judgeme.app/audience?token=<audienceToken>`
    - **Admin Token:** `<adminToken>` (displayed separately for admin to copy)
12. Admin copies URLs using "Copy to Clipboard" buttons
13. Admin shares Judge URL with all 3 judges
14. Admin shares Audience URL for big screen display

### Alternative Flows

**A1: Invalid Competition Name**
- At step 7: System detects empty competition name
- System displays error: "Competition name is required"
- Return to step 4

### Postconditions

- Competition created with status `ACTIVE`
- 10 lifts auto-created (Lift 1-10)
- 2 unique, secure URLs generated
- Admin has URLs for sharing

### Success Metrics

- Competition creation completed in < 60 seconds
- URLs successfully copied to clipboard
- All URLs functional and unique

### MVP Simplification

**Compared to full system:**
- ❌ NO athlete data entry
- ❌ NO groups or flights
- ❌ Only 2 URLs generated (instead of 7)
- ✅ Simplified to bare minimum for judging

---

## UC2: Judge Selects Position

**ID:** UC2
**Actor:** Judge (any of 3 positions)
**Preconditions:**
- Competition created by Admin (UC1)
- Judge has received shared judge URL
**Priority:** High (Core MVP functionality)

### Main Flow

1. Judge opens shared judge URL in browser
2. System validates judge token
3. System displays position selection screen with 3 large buttons:
   ```
   ┌─────────────────────────┐
   │        LEFT             │
   │   Side Referee          │
   └─────────────────────────┘

   ┌─────────────────────────┐
   │       CENTER            │
   │   Head Referee          │
   │ (Timer + Vote + Next)   │
   └─────────────────────────┘

   ┌─────────────────────────┐
   │       RIGHT             │
   │   Side Referee          │
   └─────────────────────────┘
   ```
4. Judge clicks desired position button
5. System generates session ID for judge's browser
6. System attempts to claim position in database (UNIQUE constraint check)
7. If position available:
   - System creates JudgePosition record
   - System emits `position_claimed` Socket.IO event
   - System redirects judge to voting interface
8. If position already taken:
   - System returns 409 Conflict error
   - System displays error: "Position already taken by another judge"
   - Taken position button becomes disabled/greyed out
9. Judge sees appropriate interface based on position:
   - CENTER: Full controls (timer, vote, next lift, release)
   - LEFT/RIGHT: Simplified controls (vote, release)

### Alternative Flows

**A1: Position Already Taken**
- At step 6: Database UNIQUE constraint prevents duplicate claim
- System returns 409 Conflict error
- Judge sees error message: "Position already taken. Please select another position."
- Taken position button greyed out automatically
- Return to step 4

**A2: Invalid Judge Token**
- At step 2: System detects invalid or expired token
- System displays error: "Invalid judge URL. Please check the link."
- End use case

**A3: Network Disconnection During Position Selection**
- At step 6: Network drops before server response
- Judge's browser retries request automatically
- If position was claimed: System returns success (idempotent)
- If position was taken by another judge: Return to A1

### Postconditions

- Judge position claimed and locked in database
- Other judges see position as "Taken" in real-time
- Judge sees appropriate voting interface

### Success Metrics

- Position selection completed in < 10 seconds
- No race conditions (server-side locking prevents double-claiming)
- Real-time updates (other judges notified within 500ms)

### MVP Simplification

**Compared to full system:**
- ✅ Same as full system (no changes needed)
- ✅ Single shared URL for all 3 judges
- ✅ Position locking with UNIQUE constraint

---

## UC3: Judge Votes on Lift

**ID:** UC3
**Actor:** Judge (any claimed position)
**Preconditions:**
- Judge has claimed position (UC2)
- Lift is in `IN_PROGRESS` status
**Priority:** High (Core MVP functionality)

### Main Flow

1. Judge views current lift number (e.g., "Lift 5")
2. Judge presses WHITE or RED button to vote
3. System validates judge has claimed position
4. System validates lift is in `IN_PROGRESS` status
5. System creates Vote record in database
6. System emits `vote_submitted` Socket.IO event (internal, not shown to audience)
7. System increments vote count (1/3, 2/3, or 3/3)
8. System displays confirmation: "Vote submitted"
9. "Change Vote" button appears on judge's interface
10. If 3rd vote just submitted:
    - System calculates result:
      - 2-3 WHITE votes → `GOOD_LIFT`
      - 2-3 RED votes → `NO_LIFT`
    - System updates Lift status to `COMPLETED`
    - System emits `lift_completed` Socket.IO event with result + all 3 votes
    - Audience display updates (simultaneous reveal of all 3 votes)
    - "NEXT LIFT" button becomes enabled for CENTER judge

### Alternative Flows

**A1: Judge Changes Vote (Before 3rd Vote)**
- After step 9: Judge clicks "Change Vote" button
- System displays confirmation dialog: "Change vote to RED LIGHT?"
- Judge confirms
- System checks if 3 votes already submitted
- If < 3 votes:
  - System updates Vote record (decision field)
  - System emits `vote_changed` Socket.IO event
  - System displays: "Vote changed successfully"
  - Continue from step 9
- If 3 votes already submitted:
  - System returns 403 Forbidden error
  - System displays: "Cannot change vote. All 3 judges have already voted."
  - End use case

**A2: Judge Already Voted for This Lift**
- At step 5: Database UNIQUE constraint prevents duplicate vote
- System returns 409 Conflict error
- System displays: "You already voted for this lift. Use 'Change Vote' to modify."
- End use case

**A3: Judge Has Not Claimed Position**
- At step 3: System detects no position claimed for this session ID
- System returns 401 Unauthorized error
- System redirects judge to position selection screen (UC2)
- End use case

### Postconditions

- Vote recorded in database
- Vote count incremented
- If 3rd vote: Result calculated, lift marked `COMPLETED`
- If 3rd vote: Audience sees all 3 votes simultaneously
- If 3rd vote: NEXT LIFT button enabled for CENTER judge

### Success Metrics

- Vote submission latency < 300ms
- Vote change allowed before 3rd vote
- Vote change blocked after 3rd vote (403 error)
- Result calculation correct (2 WHITE = GOOD_LIFT, 2 RED = NO_LIFT)
- Simultaneous reveal on audience display (all 3 votes within 200ms)

### MVP Simplification

**Compared to full system:**
- ✅ Same voting mechanics as full system
- ❌ NO athlete name displayed (just "Lift 5")
- ❌ NO weight displayed
- ❌ NO lift type (Squat/Bench/Deadlift)

---

## UC4: CENTER Judge Advances to Next Lift

**ID:** UC4
**Actor:** CENTER Judge
**Preconditions:**
- CENTER judge has claimed position
- Current lift has all 3 votes (status `COMPLETED`)
**Priority:** High (Core MVP functionality)

### Main Flow

1. All 3 judges complete voting on current lift (e.g., Lift 5)
2. System emits `lift_completed` event
3. "NEXT LIFT" button becomes enabled (purple) on CENTER judge interface
4. CENTER judge presses "NEXT LIFT" button
5. System validates CENTER judge position
6. System validates current lift has 3 votes
7. System marks current lift as `COMPLETED`
8. System finds next pending lift (liftNumber + 1)
9. System updates next lift status to `IN_PROGRESS`
10. Timer remains at 60 seconds (not started)
11. System emits `next_lift_started` Socket.IO event
12. All displays update to show new lift number
13. All judges see new lift number (e.g., "Lift 6")
14. Audience display shows new lift number
15. CENTER judge presses "START CLOCK" when ready

### Alternative Flows

**A1: Last Lift Completed (Lift 10)**
- At step 8: System detects no more pending lifts
- System marks Lift 10 as `COMPLETED`
- "NEXT LIFT" button shows "Competition Complete"
- System displays message: "All lifts finished. Admin can now delete competition."
- End use case

**A2: Not CENTER Judge**
- At step 5: System detects judge is LEFT or RIGHT position
- System returns 403 Forbidden error
- System displays: "Only CENTER judge can advance to next lift"
- End use case

**A3: Current Lift Not Completed**
- At step 6: System detects less than 3 votes for current lift
- System returns 409 Conflict error
- System displays: "Cannot advance. Current lift not yet completed (need 3 votes)"
- End use case

**A4: Network Disconnection During Advancement**
- At step 7: Network drops before server completes operation
- Judge's browser retries request
- Server checks if next lift already activated (idempotent)
- If yes: Returns success with next lift info
- If no: Completes activation
- Continue from step 11

### Postconditions

- Current lift marked `COMPLETED`
- Next lift marked `IN_PROGRESS`
- Timer remains at 60 seconds (ready state)
- All displays updated to new lift number
- Vote buttons cleared/reset for new lift

### Success Metrics

- NEXT LIFT only enabled after all 3 votes (enforced client + server)
- Lift number increments correctly (5 → 6 → 7... → 10)
- Timer does NOT auto-start on new lift
- Smooth transition (< 500ms) between lifts
- All clients synchronized (within 1 second tolerance)

### MVP Simplification

**Compared to full system:**
- ✅ Same as full system but simpler (no athlete data to load)
- ✅ CENTER judge controls lift progression (not admin)
- ❌ NO "Next Athlete" concept (just "Next Lift")
- ❌ NO athlete name/weight to display

---

## UC5: Audience Views Vote Results

**ID:** UC5
**Actor:** Venue Audience (big screen display)
**Preconditions:**
- Competition created (UC1)
- Audience display opened with audience URL
- Lift is in `IN_PROGRESS` status
**Priority:** High (Core MVP functionality)

### Main Flow

1. Audience opens audience URL in browser (big screen)
2. System validates audience token
3. System displays audience interface:
   - Lift number (e.g., "Lift 5")
   - 60-second countdown timer (large font)
   - 3 vote light circles (LEFT, CENTER, RIGHT) - all grey
4. CENTER judge starts timer
5. System emits `clock_started` event
6. Timer begins countdown: 60 → 59 → 58... → 0
7. Timer color changes based on time:
   - Green: 60-30 seconds
   - Yellow: 29-10 seconds
   - Red: 9-0 seconds
8. Judges vote (1st vote, 2nd vote, 3rd vote)
9. Vote circles remain GREY during voting (suspense)
10. When 3rd vote submitted:
    - System emits `lift_completed` event with all 3 votes
    - **ALL 3 CIRCLES UPDATE SIMULTANEOUSLY** (within 200ms)
    - Circles change to GREEN (WHITE vote) or RED (RED vote)
    - Result banner appears:
      - Green background: "GOOD LIFT" (if 2-3 WHITE)
      - Red background: "NO LIFT" (if 2-3 RED)
11. Vote lights and result banner remain visible
12. CENTER judge advances to next lift (UC4)
13. Display updates to new lift number
14. Vote circles reset to grey
15. Repeat from step 4

### Alternative Flows

**A1: Timer Reaches 0 Before Voting Complete**
- At step 7: Timer reaches 0:00
- System emits `clock_expired` event
- Timer displays "TIME" in red
- Voting continues normally (timer expiration does NOT affect voting)
- Continue from step 8

**A2: CENTER Judge Resets Timer**
- During step 6: CENTER judge presses RESET button
- System emits `clock_reset` event
- Timer returns to 60 seconds
- Timer color returns to green
- Continue from step 6

**A3: Invalid Audience Token**
- At step 2: System detects invalid token
- System displays error: "Invalid audience URL"
- End use case

**A4: Network Disconnection**
- During any step: Network connection drops
- Browser automatically attempts reconnection
- When reconnected: System emits current lift state
- Display resumes with current data
- Continue from current step

### Postconditions

- Audience has seen vote results
- Result (GOOD_LIFT or NO_LIFT) clearly displayed
- All 3 votes visible simultaneously

### Success Metrics

- All 3 vote lights appear simultaneously (< 200ms difference)
- Timer synchronized with judge displays (±1 second tolerance)
- Display readable from 30+ feet away
- Vote reveal creates dramatic suspense
- Result immediately clear to audience

### MVP Simplification

**Compared to full system:**
- ❌ NO athlete name displayed
- ❌ NO weight displayed
- ❌ NO lift type (Squat/Bench/Deadlift)
- ✅ Timer + vote lights + result only (absolute minimum)

---

## UC6: Judge Releases Position

**ID:** UC6
**Actor:** Judge (any claimed position)
**Preconditions:**
- Judge has claimed position (UC2)
- Timer is NOT running (for CENTER judge)
**Priority:** Medium

### Main Flow

1. Judge decides to release position (bathroom break, fatigue, etc.)
2. Judge presses "RELEASE POSITION" button
3. System displays confirmation dialog: "Release CENTER position?"
4. Judge confirms
5. System validates judge's session ID matches position claim
6. System validates timer is not running (if CENTER judge)
7. System deletes JudgePosition record from database
8. System emits `position_released` Socket.IO event
9. System redirects judge to position selection screen (UC2)
10. Position becomes available for other judges
11. Other judges see position as available in real-time

### Alternative Flows

**A1: Timer Running (CENTER Judge Only)**
- At step 6: System detects timer is running
- System returns 409 Conflict error
- System displays: "Cannot release position while timer is running. Press RESET first."
- "RELEASE POSITION" button remains disabled
- End use case

**A2: Session ID Mismatch**
- At step 5: System detects session ID does not match position claim
- System returns 401 Unauthorized error
- System displays: "Not authorized to release this position"
- End use case

**A3: Judge Changes Mind**
- At step 4: Judge clicks "Cancel" in confirmation dialog
- System does nothing
- End use case

### Postconditions

- Position released and deleted from database
- Judge returned to position selection screen
- Position available for other judges
- Socket.IO notifies all clients of release

### Success Metrics

- Release blocked when timer running (CENTER only)
- Position immediately available after release
- Other judges notified within 500ms
- Judge can re-select same or different position

### MVP Simplification

**Compared to full system:**
- ✅ Same as full system (no changes)

---

## UC7: Admin Deletes Competition

**ID:** UC7
**Actor:** Admin
**Preconditions:**
- Competition exists
- Admin has admin token
**Priority:** Medium

### Main Flow

1. Admin navigates to admin URL (with admin token in query param)
2. System validates admin token
3. System displays competition details:
   - Competition name
   - Competition date
   - Status (ACTIVE, ENDED)
   - Number of lifts completed
4. Admin clicks "Delete Competition" button
5. System displays confirmation dialog: "Permanently delete competition and all data? This cannot be undone."
6. Admin confirms deletion
7. System validates admin token again
8. System deletes competition record from database
9. CASCADE deletes all related data:
   - All lifts (10 records)
   - All votes (up to 30 records)
   - All judge positions (up to 3 records)
10. System emits `competition_deleted` Socket.IO event
11. All connected clients receive event
12. All clients display message: "Competition has been deleted by admin"
13. All clients disconnect and redirect to homepage
14. Admin sees success message: "Competition deleted successfully"

### Alternative Flows

**A1: Invalid Admin Token**
- At step 2: System detects invalid or missing admin token
- System returns 401 Unauthorized error
- System displays: "Invalid admin token. Access denied."
- End use case

**A2: Competition Not Found**
- At step 2: System cannot find competition by ID
- System returns 404 Not Found error
- System displays: "Competition not found"
- End use case

**A3: Admin Changes Mind**
- At step 6: Admin clicks "Cancel" in confirmation dialog
- System does nothing
- Return to step 3

### Postconditions

- Competition deleted from database
- All related data (lifts, votes, positions) deleted
- All tokens invalidated
- All clients notified and disconnected

### Success Metrics

- Deletion completes in < 2 seconds
- All data removed from database
- URLs become invalid immediately
- Clients notified in real-time

### MVP Simplification

**Compared to full system:**
- ✅ Manual deletion only (no auto-deletion after 3 days)
- ✅ Simple admin interface (no complex dashboard)

---

## Use Case Priority Matrix

| Use Case | Priority | Complexity | MVP Status |
|----------|----------|------------|------------|
| UC1: Admin Creates Competition | High | Low | ✅ MVP Core |
| UC2: Judge Selects Position | High | Medium | ✅ MVP Core |
| UC3: Judge Votes on Lift | High | Medium | ✅ MVP Core |
| UC4: CENTER Judge Advances Lift | High | Medium | ✅ MVP Core |
| UC5: Audience Views Votes | High | Low | ✅ MVP Core |
| UC6: Judge Releases Position | Medium | Low | ✅ MVP Core |
| UC7: Admin Deletes Competition | Medium | Low | ✅ MVP Core |

**Total MVP Use Cases:** 7

**Removed from full system:**
- UC1a: Competition Manager Enters Athletes
- UC1b: Competition Manager Creates Groups/Flights
- UC3: Admin Starts Flight
- UC3a: Athlete Manager Updates Weights
- UC3b: Platform Loader Views Plate Calculator
- UC4b: Remote Audience Dashboard
- UC5: Historical Dashboard
- UC6: Competition Host Announcer Display

---

## Success Criteria Summary

**All 7 MVP use cases must:**
- Complete successfully in expected time
- Handle alternative flows gracefully
- Provide clear error messages
- Synchronize state across all clients in real-time
- Work on mobile devices (320px+ width)
- Maintain data consistency (no race conditions)

**Performance Targets:**
- Competition creation: < 60 seconds
- Position selection: < 10 seconds
- Vote submission: < 300ms latency
- Real-time updates: < 500ms delivery
- Audience display update: < 200ms simultaneous reveal

---

**END OF MVP USE CASES**

**Document Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** Ready for Implementation
