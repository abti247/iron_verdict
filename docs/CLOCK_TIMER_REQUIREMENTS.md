# Clock Timer Requirements - Head Referee Control

## Overview

The head referee (CENTER position) has an additional critical responsibility beyond voting: **controlling the 60-second clock** that gives the athlete time to complete their lift.

## Key Distinction

- **Head Referee (CENTER):** Controls clock + votes
- **Side Referees (LEFT/RIGHT):** Only vote

## Functional Requirements

### FR-CLOCK-1: 60-Second Countdown Timer

**Requirement:** System shall implement a 60-second countdown timer for each lift

**Behavior:**
- Initial state: Timer shows "60" or "READY" (not counting)
- Start trigger: Head referee presses "START CLOCK" button
- Countdown: Decrements from 60 → 0 at 1-second intervals
- Expiration: Timer reaches 0:00, displays "TIME" (does NOT auto-fail lift)

**Priority:** High

---

### FR-CLOCK-2: Head Referee Clock Control and Lift Progression Buttons

**Requirement:** Head referee interface shall include clock control and lift progression buttons

**UI Elements:**
- **NEXT ATHLETE button**
  - Large button (minimum 80px height)
  - Color: Purple or distinct color (different from clock and voting buttons)
  - Position: Top of interface, above clock controls
  - Label: "NEXT ATHLETE" or "➡ NEXT ATHLETE"
  - Enabled state: Only after current lift completed (all 3 judges voted)
  - Disabled state: Greyed out during active lift

- **START CLOCK button**
  - Large, prominent button (minimum 80px height)
  - Color: Blue or neutral color (distinct from voting buttons)
  - Position: Above or below voting buttons, clearly separated
  - Label: "START CLOCK" or "▶ START (60s)"

- **RESET CLOCK button**
  - Similar size to START button
  - Color: Orange or yellow (indicates action)
  - Position: Next to START button
  - Label: "RESET CLOCK" or "↻ RESET"

- **Timer Display**
  - Shows current countdown: "0:45" (minutes:seconds)
  - Large font size (readable at arm's length)
  - Color changes based on time remaining:
    - Green: 60-30 seconds
    - Yellow: 29-10 seconds
    - Red: 9-0 seconds

**Priority:** High

**Mockup:**
```
┌─────────────────────────────┐
│  HEAD REFEREE (CENTER)      │
│                             │
│  Athlete: Alice Smith       │
│  SQUAT - Attempt 1 - 100kg  │
│                             │
│  ┌───────────────────────┐  │
│  │   ➡ NEXT ATHLETE     │  │ ← Lift progression
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────┐      │
│  │   TIMER: 0:45    │      │ ← Timer display
│  └───────────────────┘      │
│                             │
│  ┌──────────┐ ┌──────────┐ │
│  │ ▶ START  │ │ ↻ RESET  │ │ ← Clock controls
│  │  CLOCK   │ │  CLOCK   │ │
│  └──────────┘ └──────────┘ │
│                             │
│  ┌───────────────────────┐  │
│  │   ✓ WHITE LIGHT       │  │ ← Voting buttons
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │   ✗ RED LIGHT         │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

---

### FR-CLOCK-3: Side Referee Interface (No Clock Controls)

**Requirement:** Side referee interfaces (LEFT and RIGHT) shall NOT display clock controls

**Rationale:**
- Prevents confusion
- Simpler UI for side refs
- Only head ref has timing authority

**UI:** Side referees see ONLY:
- Current lift information
- WHITE and RED voting buttons
- Timer display (read-only, for information only)

**Priority:** High

---

### FR-CLOCK-4: Reset Clock Functionality

**Requirement:** Head referee shall be able to reset timer at any time

**Use Cases:**
- Athlete not ready after being called
- Equipment malfunction (bar not loaded correctly, etc.)
- Technical issue on platform
- Athlete requests bathroom break

**Behavior:**
- Pressing RESET stops countdown
- Timer returns to 60 seconds
- Timer state changes to "READY" (not counting)
- Head ref must press START again to restart countdown

**Priority:** High

---

### FR-CLOCK-5: Audience Display Timer

**Requirement:** Audience display shall show timer prominently

**Display Requirements:**
- Large, easily readable font (visible from 30+ feet)
- Positioned near athlete name or lift info
- Color coding: Green → Yellow → Red (based on time remaining)
- Updates in real-time every second

**Priority:** High

**Mockup:**
```
┌─────────────────────────────────┐
│   ALICE SMITH                   │
│   SQUAT - Attempt 1 - 100kg     │
│                                 │
│   ┌─────────┐                   │
│   │  0:45   │  ← Timer display  │
│   └─────────┘                   │
│                                 │
│   ◯  ◯  ◯   ← Vote lights       │
│  LEFT CTR RGT                   │
└─────────────────────────────────┘
```

---

### FR-CLOCK-6: Real-Time Clock Synchronization

**Requirement:** Timer state shall broadcast to all connected clients in real-time

**Socket.IO Events:**

**Server → Client:**
- `clock_started` - { liftId, startTime, duration: 60 }
- `clock_tick` - { liftId, remainingSeconds: 45 } (emitted every second)
- `clock_reset` - { liftId }
- `clock_expired` - { liftId } (when timer reaches 0)

**Client → Server:**
- `start_clock` - { liftId, headRefToken }
- `reset_clock` - { liftId, headRefToken }

**Synchronization:**
- All displays (judge phones, audience screen) show same time
- Tolerance: ±1 second acceptable due to network latency
- Server is source of truth for timer state

**Priority:** High

---

### FR-CLOCK-7: Timer Does Not Auto-Fail Lift

**Requirement:** Timer expiration shall NOT automatically fail the lift

**Behavior:**
- When timer reaches 0:00, display shows "TIME" or flashing red
- Head referee makes final decision on whether to allow lift
- Judges still vote normally if lift is attempted
- Timer is regulatory/informational, not automatic enforcement

**Rationale:**
- Powerlifting rules allow referee discretion
- Athlete may start lift at 0:01 and it may still be valid
- Technical issues shouldn't auto-fail

**Priority:** Medium

---

### FR-CLOCK-8: Next Athlete Button Behavior

**Requirement:** Center judge shall advance to next athlete in flight

**Behavior:**
- **Enabled state:** Only after `lift_completed` event (all 3 judges voted)
- **Click action:** Marks current lift as completed, loads next lift in queue
- **Timer state:** Timer remains at 60 seconds (not started)
- **Next action:** Center judge must press START CLOCK for new athlete
- **Socket.IO:** Emits `next_lift_started` event with new athlete details
- **Flight completion:** If last athlete in flight, shows "Flight Complete - Notify Admin" message
- **Admin notification:** System sends notification to admin dashboard that flight is complete

**Priority:** High

**Flow:**
1. All 3 judges vote on current lift
2. System emits `lift_completed` event
3. NEXT ATHLETE button becomes enabled for center judge
4. Center judge presses NEXT ATHLETE button
5. System loads next athlete's information
6. Timer resets to 60 seconds (ready state, not running)
7. Center judge presses START CLOCK when athlete is ready
8. Process repeats for next athlete

**Edge Cases:**
- If NEXT ATHLETE pressed on last lift in flight: Show "Flight Complete" message, disable button
- If network disconnects during button press: System should gracefully handle reconnection and resume
- If center judge releases position before pressing NEXT ATHLETE: New center judge can press button

---

## Database Schema Changes

Add to **Lift** table:
```
timerStartedAt: DateTime? (nullable)
timerResetCount: Int (default 0) - for statistics
```

---

## API Endpoints

### POST /api/lifts/:liftId/start-clock
**Auth:** Requires headRefToken (CENTER position token)
**Body:** `{ headRefToken: string }`
**Response:** `{ liftId, timerStartedAt, expiresAt }`

### POST /api/lifts/:liftId/reset-clock
**Auth:** Requires headRefToken
**Body:** `{ headRefToken: string }`
**Response:** `{ liftId, timerReset: true }`

---

## Testing Scenarios

### Test 1: Normal Clock Flow
1. Head ref starts clock
2. Timer counts down 60 → 0
3. Athlete completes lift at 0:35
4. All judges vote
5. ✅ Pass: Timer visible on all screens, synchronized

### Test 2: Clock Reset
1. Head ref starts clock
2. Timer at 0:45
3. Athlete signals not ready
4. Head ref presses RESET
5. Timer returns to 60
6. ✅ Pass: Timer resets on all screens

### Test 3: Side Ref Cannot Control Clock
1. Side ref (LEFT) opens interface
2. ✅ Pass: No START/RESET buttons visible
3. ✅ Pass: Timer display still visible (read-only)

### Test 4: Timer Expiration
1. Head ref starts clock
2. Timer counts to 0:00
3. Display shows "TIME" in red
4. ✅ Pass: Lift can still proceed (not auto-failed)
5. Judges can still vote

---

## Priority Summary

**High Priority (MVP):**
- FR-CLOCK-1: 60-second countdown
- FR-CLOCK-2: Head ref controls (START/RESET buttons)
- FR-CLOCK-3: Side refs NO controls
- FR-CLOCK-4: Reset functionality
- FR-CLOCK-5: Audience timer display
- FR-CLOCK-6: Real-time sync

**Medium Priority:**
- FR-CLOCK-7: Timer doesn't auto-fail

---

## Implementation Notes

- Timer runs on **server-side** (not client-side JavaScript)
- Server emits `clock_tick` events every second
- Clients display timer but don't compute countdown locally
- This prevents clock drift across devices
- Head ref token validates clock control authority
