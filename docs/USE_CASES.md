# JudgeMe - Use Cases

## UC1: Create Competition Session

**ID:** UC1
**Actor:** Admin (Competition Organizer)
**Preconditions:** None (no authentication required)
**Priority:** High (Core functionality)

### Main Flow
1. Admin navigates to JudgeMe homepage
2. Admin clicks "Create Competition" button
3. System displays competition creation form
4. Admin enters competition name (e.g., "Spring Open 2026")
5. Admin enters competition date
6. Admin clicks "Create Competition" button
7. System validates input (competition name not empty)
8. System generates 7 cryptographically secure tokens (128-bit entropy):
   - Admin token
   - Competition Manager token
   - Athlete Manager token
   - Platform Loader token
   - Judge token (shared by all 3 judges)
   - Audience token
   - Competition Host token
9. System creates competition record in database with status "SETUP"
10. System displays success page with 7 shareable URLs:
    - **Admin Control Panel:** `https://judgeme.app/admin?token=<adminToken>`
    - **Competition Manager:** `https://judgeme.app/comp-manager?token=<compManagerToken>`
    - **Athlete Manager:** `https://judgeme.app/athlete-manager?token=<athleteManagerToken>`
    - **Platform Loader:** `https://judgeme.app/loader?token=<loaderToken>`
    - **Judge (Shared):** `https://judgeme.app/judge?token=<judgeToken>`
    - **Audience Display:** `https://judgeme.app/audience?token=<audienceToken>`
    - **Competition Host:** `https://judgeme.app/host?token=<hostToken>`
11. Admin copies URLs using "Copy to Clipboard" buttons
12. Admin shares Competition Manager URL for pre-competition setup
13. Admin shares single Judge URL with all 3 judges and Audience URL for competition day

### Alternative Flows

**A1: Invalid Competition Name**
- At step 7: System detects empty competition name
- System displays error: "Competition name is required"
- Return to step 4

### Postconditions
- Competition created with status "SETUP"
- 7 unique, secure URLs generated
- Admin has access to all URLs for sharing
- Competition ready for athlete data entry by Competition Manager

### Success Metrics
- Competition creation completed in < 1 minute
- URLs successfully copied to clipboard
- All URLs functional and unique

---

## UC1a: Competition Manager Enters Athletes

**ID:** UC1a
**Actor:** Competition Manager
**Preconditions:**
- Competition has been created by Admin
- Competition Manager has received their unique URL
**Priority:** High (Core functionality)

### Main Flow
1. Competition Manager opens Competition Manager URL
2. System validates token and loads competition
3. System displays athlete management interface
4. Competition Manager clicks "Add Athlete" button
5. System displays athlete entry form
6. Competition Manager enters athlete details:
   - Name (required)
   - Weigh-in weight (required)
   - Opening squat attempt weight
   - Opening bench attempt weight
   - Opening deadlift attempt weight
7. Competition Manager clicks "Save Athlete"
8. System validates input and creates athlete record
9. System generates 9 lift attempts for athlete (3 per discipline)
10. System sets 1st attempt weights from opening attempts entered
11. System displays athlete in athlete list
12. Competition Manager repeats steps 4-11 for all athletes

### Alternative Flows

**A1: Bulk Import Athletes**
- At step 4: Competition Manager clicks "Import from CSV"
- System displays file upload dialog
- Competition Manager uploads CSV with athlete data
- System validates CSV format and data
- System creates all athlete records in bulk
- Continue from step 11

**A2: Edit Existing Athlete**
- At step 4: Competition Manager clicks "Edit" on existing athlete
- System displays athlete edit form with current data
- Competition Manager updates fields
- System saves changes
- Continue from step 11

**A3: Delete Athlete**
- At step 4: Competition Manager clicks "Delete" on athlete
- System confirms: "Remove athlete and all their lifts?"
- Competition Manager confirms
- System soft-deletes athlete and associated lifts
- Continue from step 4

### Postconditions
- All athletes entered with weigh-in weights and opening attempts
- 9 lift attempts generated per athlete
- Athletes ready to be organized into groups/flights

### Success Metrics
- Athlete entry takes < 30 seconds per athlete
- Bulk import handles 50+ athletes successfully
- No data entry errors requiring correction

---

## UC1b: Competition Manager Creates Groups and Flights

**ID:** UC1b
**Actor:** Competition Manager
**Preconditions:**
- Athletes have been entered (UC1a completed)
- Competition Manager has access to competition

**Priority:** High (Core functionality)

### Main Flow
1. Competition Manager navigates to "Groups & Flights" section
2. System displays all athletes in unassigned list
3. Competition Manager clicks "Create Group"
4. System prompts for group name (e.g., "Men's Open")
5. Competition Manager enters group name
6. System creates group
7. Competition Manager clicks "Create Flight" within group
8. System prompts for flight name (e.g., "Flight A")
9. Competition Manager enters flight name
10. System creates flight within group
11. Competition Manager drags athletes from unassigned list to flight
12. System assigns athletes to flight
13. Competition Manager repeats steps 7-12 to create additional flights
14. Competition Manager repeats steps 3-13 to create additional groups
15. Competition Manager clicks "Finalize Groups"
16. System validates all athletes are assigned
17. System updates competition status to "READY"

### Alternative Flows

**A1: Not All Athletes Assigned**
- At step 16: System detects unassigned athletes
- System displays warning: "X athletes not assigned to a flight"
- System lists unassigned athletes
- Competition Manager returns to step 11

**A2: Auto-Create Flights by Weight**
- At step 3: Competition Manager clicks "Auto-Create Flights"
- System prompts for flight size (e.g., 10 athletes per flight)
- System automatically creates flights based on weight classes
- Competition Manager reviews and adjusts assignments
- Continue from step 15

**A3: Reorder Athletes Within Flight**
- At step 11: Competition Manager drags athletes to reorder within flight
- System updates lifting order
- Continue from step 11

### Postconditions
- All athletes assigned to groups and flights
- Lifting order established
- Competition ready to start
- Admin can now start competition

### Success Metrics
- Group/flight creation takes < 5 minutes for 50 athletes
- Drag-and-drop interface works smoothly
- Auto-creation feature creates balanced flights

---

## UC2: Judge Selects Position

**ID:** UC2
**Actor:** All 3 Judges (Marcus, Jessica, David)
**Preconditions:**
- Competition exists
- Admin has shared single judge URL with all 3 judges

**Priority:** High (Core functionality)

### Main Flow
1. Judge 1 (Marcus) receives shared judge URL via text message from admin
2. Judge 1 clicks URL link on mobile device
3. Browser opens to judge position selection page
4. System extracts token from URL query parameter
5. System validates token against database (confirms judge role)
6. System queries database for current position assignments
7. System displays position selection screen with three large buttons:
   - [LEFT] (Available)
   - [CENTER] (Available)
   - [RIGHT] (Available)
8. Judge 1 presses [CENTER] button
9. System sends position selection to backend: POST /api/judge/select-position
   - Body: `{ token, position: "CENTER" }`
10. Backend starts database transaction
11. Backend checks if CENTER position is available
12. Backend inserts record: `judge_positions (competitionId, position: CENTER, claimedAt: NOW, sessionId)`
13. Backend commits transaction
14. Backend returns success: `{ position: "CENTER" }`
15. System displays CENTER judge interface:
    - START CLOCK button
    - RESET CLOCK button
    - WHITE voting button
    - RED voting button
    - RELEASE POSITION button (initially enabled, disabled when timer starts)
16. Judge 1 is now positioned as CENTER referee

**Meanwhile (concurrent):**
17. Judge 2 (Jessica) opens same judge URL
18. System displays position selection screen with:
    - [LEFT] (Available)
    - [CENTER - TAKEN] (Greyed out/disabled)
    - [RIGHT] (Available)
19. Judge 2 presses [LEFT] button
20. Backend processes position claim (steps 9-14 for LEFT position)
21. System displays LEFT judge interface (simplified):
    - WHITE voting button
    - RED voting button
    - Timer display (read-only)
    - RELEASE POSITION button (initially enabled, disabled when timer starts)
22. Judge 2 is now positioned as LEFT referee

**Finally:**
23. Judge 3 (David) opens same judge URL
24. System displays position selection screen with:
    - [LEFT - TAKEN] (Greyed out/disabled)
    - [CENTER - TAKEN] (Greyed out/disabled)
    - [RIGHT] (Available)
25. Judge 3 presses [RIGHT] button
26. Backend processes position claim (steps 9-14 for RIGHT position)
27. System displays RIGHT judge interface (simplified, same as LEFT)
28. All 3 judges now positioned and ready

### Alternative Flows

**A1: Position Already Taken (Race Condition)**
- At step 11: Backend detects CENTER already claimed by another judge
- Backend returns 409 Conflict error: "Position already taken, please select another position"
- System displays error message to judge
- System refreshes position selection screen (CENTER now greyed out)
- Judge returns to step 8 and selects different position

**A2: Judge Releases Position**
- After step 16, 22, or 28: Judge presses RELEASE POSITION button
- System checks if timer is running
- If timer running: Button is disabled (cannot release)
- If timer NOT running: System sends release request to backend
- Backend deletes judge_position record for that judge
- System returns judge to position selection screen (step 7)
- Position becomes available for other judges

**A3: Judge Refreshes Page After Selecting Position**
- Judge has selected position (e.g., CENTER)
- Judge refreshes browser
- System validates token and checks database
- System finds existing position assignment
- System loads appropriate interface (CENTER or LEFT/RIGHT)
- Judge continues from where they left off

**A4: Invalid Token**
- At step 5: System cannot find token in database
- System displays error page: "Invalid judge link. Please contact competition admin."
- Flow ends

### Postconditions
- All 3 judge positions (LEFT, CENTER, RIGHT) are claimed
- Each judge has appropriate UI loaded (CENTER with timer controls, LEFT/RIGHT simplified)
- System ready for competition to begin
- Position assignments stored in database

### Success Metrics
- Position selection takes < 10 seconds per judge
- No race condition errors (server-side locking works)
- Judges understand which position they selected
- UI adapts correctly based on position

---

## UC2a: Judge Votes on Lift (with Vote Changing)

**ID:** UC2a
**Actor:** Judge (any position - LEFT, CENTER, or RIGHT)
**Preconditions:**
- Judge has selected their position (UC2 completed)
- Competition exists and is active
- Admin has started a lift

**Priority:** High (Core functionality)

### Main Flow
1. Judge has already selected position (UC2 completed)
2. System loads current lift information
3. System displays judge interface showing:
   - Competition name
   - Judge position (e.g., "Judge: LEFT")
   - Current athlete name
   - Lift type (SQUAT, BENCH, or DEADLIFT)
   - Attempt number (1, 2, or 3)
   - Weight (if specified)
   - Timer display (CENTER has controls, LEFT/RIGHT read-only)
4. System displays two large voting buttons:
   - WHITE LIGHT button (green, 80px+ height)
   - RED LIGHT button (red, 80px+ height)
5. Judge watches athlete perform lift
6. Judge presses WHITE or RED button based on lift validity
7. System highlights selected button (shows visual feedback)
8. System displays loading indicator
9. System sends vote to backend API: POST /api/votes
    - Body: `{ liftId, position, decision: "WHITE" }`
10. Backend validates:
    - Judge has claimed a position
    - Lift exists and is IN_PROGRESS
11. Backend records or updates vote in database:
    - Judge position
    - Decision (WHITE or RED)
    - Timestamp
12. Backend emits Socket.IO event: `vote_submitted` (internal, not shown to audience yet)
13. System updates judge interface with confirmation:
    - "Vote recorded: WHITE LIGHT" (or RED LIGHT)
    - **Shows "Change Vote" button** (allows judge to change vote before all 3 judges vote)
    - Other vote button remains enabled (for changing vote)
14. Backend checks if all 3 judges have voted
15. If NOT all 3 voted yet: Judge can change vote (see Alternative Flow A2)
16. If all 3 voted: Backend calculates result (2+ WHITE = GOOD LIFT)
17. Backend emits Socket.IO event: `lift_completed` with result and all 3 votes
18. **All vote lights appear simultaneously** on audience display
19. Judge interface updates to show result and all 3 votes
20. RELEASE POSITION button becomes enabled (timer not running)
21. Judge waits for next lift to begin

**Note:**
- CENTER referee has timer controls in addition to voting buttons
- LEFT/RIGHT referees see simplified interface with voting buttons only
- Judges can change their vote any time before all 3 judges have voted
- Vote results are only shown after all 3 judges have voted (suspense maintained)

### Alternative Flows

**A1: Judge Changes Vote (Fat Finger Correction)**
- At step 13: Judge realizes they pressed wrong button
- Judge presses opposite button (RED instead of WHITE, or vice versa)
- System confirms: "Change vote to RED LIGHT?"
- Judge confirms change
- System sends updated vote: PUT /api/votes/:voteId
- Backend updates vote decision in database
- Backend emits updated `vote_submitted` event
- System displays new confirmation: "Vote changed to: RED LIGHT"
- If all 3 judges have now voted: Flow continues to step 16
- If not all voted: Judge can still change again (return to step 13)

**A2: Competition Not Active**
- At step 2: Competition status is "SETUP" or "ENDED"
- System displays waiting screen: "Waiting for competition to start..."
- Judge can refresh or wait for Socket.IO event

**A3: No Current Lift**
- At step 2: No lift is currently IN_PROGRESS
- System displays waiting screen: "Waiting for next lift..."
- System listens for Socket.IO `lift_started` event

**A4: Duplicate Vote Attempt**
- At step 10: Backend detects judge already voted
- Backend returns error: 400 Bad Request
- System displays error: "You have already voted on this lift"
- Buttons remain disabled

**A5: Network Interruption During Vote**
- At step 9: Network request fails
- System displays error: "Network error. Retrying..."
- System automatically retries vote submission (up to 3 times)
- If all retries fail: System displays: "Vote failed. Please check connection."

**A6: Socket.IO Disconnection**
- During flow: WebSocket connection drops
- System automatically attempts reconnection
- System displays connection status: "Reconnecting..."
- On reconnect: System re-joins competition room
- System fetches current lift state
- Flow continues from current state

### Postconditions
- Vote recorded in database
- Vote count for lift incremented
- Audience display updated with judge's decision
- If 3 votes complete: Lift result calculated and saved
- Judge interface ready for next lift

### Success Metrics
- Vote submission latency < 300ms
- Vote reaches database without errors
- Real-time update appears on audience display within 500ms
- No duplicate votes recorded

---

## UC2a: Head Referee Controls Clock Timer

**ID:** UC2a
**Actor:** Head Referee (CENTER position)
**Preconditions:**
- Competition exists and is active
- Head referee has received CENTER judge URL
- Lift is ready to start (athlete on platform)

**Priority:** High (Core functionality - critical timing control)

### Main Flow
1. Head referee opens CENTER judge URL on mobile device
2. System validates token and determines position: CENTER
3. System displays head referee interface showing:
   - Competition name
   - Judge position: "HEAD REFEREE (CENTER)"
   - Current athlete name and lift details
   - **Timer display** (large, color-coded: Green/Yellow/Red)
   - **START CLOCK button** (80px+ height, blue/neutral color)
   - **RESET CLOCK button** (80px+ height, orange/yellow color)
   - WHITE LIGHT button (green, 80px+ height)
   - RED LIGHT button (red, 80px+ height)
4. Head referee verifies platform is ready:
   - Bar loaded with correct weight
   - Spotters in position
   - Athlete is prepared
5. Head referee presses **START CLOCK** button
6. System sends API request: POST /api/lifts/:liftId/start-clock
   - Body: `{ headRefToken }`
7. Backend validates:
   - Token is CENTER position (head referee only)
   - Lift exists and is IN_PROGRESS
8. Backend records timer start time
9. Backend emits Socket.IO event: `clock_started`
   - Event data: `{ liftId, startTime, duration: 60 }`
10. System updates timer display to show countdown: "0:60"
11. Backend emits `clock_tick` events every second
12. Timer counts down: 60 → 59 → 58 → ... → 0
13. Timer display changes color based on time:
    - Green: 60-30 seconds
    - Yellow: 29-10 seconds
    - Red: 9-0 seconds
14. Athlete performs lift (or timer expires)
15. Head referee watches athlete perform lift
16. Head referee presses WHITE or RED button based on lift validity
17. System highlights selected button (shows visual feedback)
18. System disables START CLOCK and RESET CLOCK buttons (voting phase)
19. System sends vote to backend API: POST /api/votes
20. Backend records vote with position: CENTER
21. Backend emits Socket.IO event: `vote_submitted` (internal, not shown to audience yet)
22. System updates head referee interface with confirmation:
    - "Vote recorded: WHITE LIGHT" (or RED LIGHT)
    - **Shows "Change Vote" button** (allows head referee to change vote before all 3 judges vote)
    - Other vote button remains enabled (for changing vote)
23. Backend checks if all 3 judges have voted
24. If NOT all 3 voted yet: Head referee can change vote (see Alternative Flow A6)
25. If all 3 voted: Backend calculates result (2+ WHITE = GOOD LIFT)
26. Backend emits Socket.IO event: `lift_completed` with result and all 3 votes
27. **All vote lights appear simultaneously** on audience display
28. System re-enables clock controls for next lift

### Alternative Flows

**A1: Reset Clock Before Athlete Ready**
- At step 5: Athlete signals they are not ready
- Head referee presses **RESET CLOCK** button
- System sends API request: POST /api/lifts/:liftId/reset-clock
- Backend validates head referee token
- Backend emits Socket.IO event: `clock_reset`
- Timer returns to "0:60" or "READY" state
- Timer stops counting
- Head referee must press START CLOCK again
- Return to step 5

**A2: Reset Clock Due to Equipment Issue**
- During countdown (step 12): Bar not loaded correctly or equipment issue
- Head referee presses **RESET CLOCK** button
- System resets timer
- Flow returns to step 5

**A3: Timer Expires (Reaches 0:00)**
- At step 12: Timer reaches 0:00
- System displays "TIME" in red (flashing)
- Backend emits Socket.IO event: `clock_expired`
- **Important:** Lift does NOT auto-fail
- Head referee has discretion whether to allow lift
- If athlete attempts lift, judges still vote normally
- Head referee can reset clock if needed

**A4: Side Judge Token Attempts Clock Control**
- At step 6: Non-CENTER token tries to start/reset clock
- Backend returns error: 403 Forbidden
- System displays: "Only head referee can control clock"
- Flow ends

**A5: Timer Already Running**
- At step 5: Clock is already counting down
- START CLOCK button is disabled
- Only RESET CLOCK button available
- Head referee must reset before starting again

**A6: Head Referee Changes Vote (Fat Finger Correction)**
- At step 22: Head referee realizes they pressed wrong button
- Head referee presses opposite button (RED instead of WHITE, or vice versa)
- System confirms: "Change vote to RED LIGHT?"
- Head referee confirms change
- System sends updated vote: PUT /api/votes/:voteId
- Backend updates vote decision in database
- Backend emits updated `vote_submitted` event
- System displays new confirmation: "Vote changed to: RED LIGHT"
- If all 3 judges have now voted: Flow continues to step 25
- If not all voted: Head referee can still change again (return to step 22)

### Postconditions
- Timer started and visible to all participants
- Athlete has 60 seconds to complete lift
- All displays (judges, audience) show synchronized timer
- Timer expiration does not auto-fail lift (referee discretion)
- Head referee can vote after athlete attempts lift

### Success Metrics
- Clock starts within 200ms of button press
- Timer synchronized across all displays (±1 second tolerance)
- Head referee can reset clock at any time without errors
- Timer expiration clearly visible to all participants

**Interface Distinction:**
- **HEAD REFEREE (CENTER):** Sees START CLOCK + RESET CLOCK + voting buttons
- **SIDE REFEREES (LEFT/RIGHT):** See ONLY voting buttons + read-only timer display

---

## UC3: Admin Starts Competition for Group/Flight and Discipline

**ID:** UC3
**Actor:** Admin
**Preconditions:**
- Competition has been created
- Competition Manager has set up all groups, flights, and athletes (UC1b completed)
- Admin has opened admin control panel URL

**Priority:** High (Core functionality)

### Main Flow
1. Admin opens admin control panel URL in browser
2. System extracts adminToken from URL query parameter
3. System validates token against database
4. System loads competition data and displays admin dashboard with:
   - Competition header (name, status, date)
   - **Group/Flight selector** dropdown
   - **Discipline selector** (Squat / Bench / Deadlift)
   - **START COMPETITION** button (large, prominent)
   - Current competition status (e.g., "Not Started", "Men's Open Flight A - Squat - In Progress")
   - Live results summary panel
5. Admin selects group/flight from dropdown (e.g., "Men's Open - Flight A")
6. Admin selects discipline from dropdown (e.g., "Squat")
7. Admin clicks **START COMPETITION** button
8. System sends API request: POST /api/competitions/:id/start-flight
   - Body: `{ adminToken, groupId, flightId, discipline: "SQUAT" }`
9. Backend validates:
   - Token matches competition admin token
   - Group and flight exist
   - No other flight currently active
10. Backend updates competition status to "ACTIVE"
11. Backend sets activeFlightId and activeDiscipline
12. Backend marks all lifts for selected flight + discipline as "READY"
13. Backend emits Socket.IO event: `flight_started`
    - Event data: `{ flightId, groupName, flightName, discipline, athletes }`
14. System updates admin dashboard:
    - Shows active flight: "Men's Open - Flight A - SQUAT"
    - Displays progress: "0 of 30 lifts completed"
    - Shows link to Athlete Manager: "Share with Athlete Manager →"
15. System automatically activates first lift in flight
16. Head referee and judges see first athlete's lift details
17. Competition proceeds with lifts (judges vote, system calculates results)
18. When all lifts in flight complete:
    - System displays: "Flight complete. Start next flight or end competition."
19. Admin selects next flight/discipline or clicks "End Competition"
20. If ending: System saves end timestamp and redirects to historical dashboard

### Alternative Flows

**A1: Invalid Admin Token**
- At step 3: Token not found or doesn't match any competition
- System displays error: "Invalid admin link"
- Flow ends

**A2: Another Flight Currently Active**
- At step 9: Backend detects another flight is active
- Backend returns error: 409 Conflict
- System displays error: "Flight 'X' is currently active. End it before starting a new flight."
- Admin must end current flight first

**A3: No Athletes in Selected Flight**
- At step 9: Backend detects selected flight has zero athletes
- Backend returns error: 400 Bad Request
- System displays error: "No athletes in this flight. Contact Competition Manager."
- Flow ends

**A4: Change Active Flight Mid-Competition**
- At step 5: Admin wants to switch to different flight while one is active
- System warns: "Flight X is active. Switching will pause it. Continue?"
- Admin confirms
- System pauses current flight, starts new flight
- Continue from step 9

### Postconditions
- Flight is active with selected discipline
- First lift is ready for head referee to start clock
- Athlete Manager can see active flight athletes
- Competition progressing smoothly

### Success Metrics
- Starting flight takes < 10 seconds
- Group/flight selection is intuitive
- Admin can monitor progress at a glance
- Smooth transitions between flights

---

## UC3a: Athlete Manager Updates Attempt Weights During Competition

**ID:** UC3a
**Actor:** Athlete Manager
**Preconditions:**
- Competition is active (UC3 - flight has been started)
- Athlete Manager has received their unique URL
- Athletes are approaching after lifts to declare next attempts

**Priority:** High (Core functionality - time-critical)

### Main Flow
1. Athlete Manager opens Athlete Manager URL on tablet
2. System validates token and loads active flight
3. System displays focused athlete management interface showing:
   - Current flight: "Men's Open - Flight A - SQUAT"
   - **Search bar** (large, auto-focus)
   - List of athletes in current flight (ordered by lifting order)
   - For each athlete:
     - Name (large font)
     - Current attempt number
     - Last attempt result (GOOD/NO/Pending)
     - **Next attempt weight field** (large, editable)
4. Athlete approaches table after completing lift
5. Athlete states next attempt weight (e.g., "105 kg for attempt 2")
6. Athlete Manager types athlete name in search bar
7. System filters list to matching athletes in real-time
8. Athlete Manager clicks on athlete row
9. System highlights athlete and focuses on "Next Attempt Weight" field
10. Athlete Manager enters weight: "105"
11. Athlete Manager presses Enter or clicks "Save"
12. System validates weight (must be >= previous attempt if GOOD lift)
13. System updates next attempt weight in database
14. System emits Socket.IO event: `attempt_weight_updated`
15. System displays confirmation: "Updated: Alice Smith - 105kg"
16. System auto-clears search and returns to athlete list
17. Athlete Manager ready for next athlete (return to step 4)

### Alternative Flows

**A1: Invalid Weight (Lighter Than Previous Good Lift)**
- At step 12: System detects weight is less than last successful lift
- System displays error: "Weight must be ≥ 102.5kg (previous lift)"
- Athlete Manager corrects weight or confirms exception
- Continue from step 10

**A2: Athlete Changes Mind About Weight**
- At step 4: Athlete returns and wants to change weight again
- Athlete Manager searches for athlete again
- System shows current next attempt weight
- Athlete Manager edits weight
- System updates weight (can be done multiple times before lift)
- Continue from step 15

**A3: Quick Entry via Lot Number**
- At step 6: Athlete Manager types lot number instead of name
- System finds athlete by lot number
- Continue from step 9

**A4: No Athletes Found**
- At step 7: Search returns no results
- System displays: "No athletes found in active flight"
- Athlete Manager clears search and tries again

**A5: Flight Switches Mid-Competition**
- During step 3: Admin starts a different flight
- System receives `flight_started` event
- System displays notification: "Flight changed to X"
- System refreshes athlete list with new flight
- Continue from step 4

### Postconditions
- Athlete next attempt weight updated in database
- System knows what weight to display when lift starts
- Athlete Manager ready for next athlete immediately
- Platform crew and judges can see updated weight

### Success Metrics
- Weight update takes < 15 seconds per athlete
- Search finds athletes within 2 seconds
- Zero data entry errors
- Athlete Manager interface never blocks competition flow

---

## UC3b: Platform Loader Views Plate Loading Display

**ID:** UC3b
**Actor:** Platform Loader
**Preconditions:**
- Competition is active (flight has been started)
- Platform Loader has received their unique URL
- Athletes are lifting and weights need to be loaded/changed

**Priority:** HIGH (Core functionality - time-critical for competition flow)

### Main Flow
1. Platform Loader opens Loader Display URL on tablet near platform
2. System validates token and loads active flight
3. System displays large, distance-readable interface showing:
   - **Current Athlete Panel (highlighted):**
     - Name (very large font - readable from 10-15 feet)
     - Discipline: "SQUAT" with icon
     - Attempt number: "Attempt 2 of 3"
     - **Total weight on bar:** "125 kg" (HUGE font)
   - **Plate Loading Calculator (visual breakdown):**
     - Bar weight: "20 kg (Men's Bar)" or "15 kg (Women's Bar)"
     - **Visual plate diagram** showing colored plates to load:
       - 25kg plate (red) × 2
       - 20kg plate (blue) × 1
       - 5kg plate (white) × 1
       - 2.5kg plate (black) × 1
     - Each plate shown as colored rectangle with number
   - **Next 2-3 Athletes "On Deck":**
     - Shows: Name, Weight, Plates needed
     - Example: "Bob Johnson - 110kg - 25×2, 15×1, 5×1"
     - Allows loaders to anticipate big weight jumps
4. Platform Loader sees current athlete is on platform
5. Platform Loader loads plates according to visual diagram
6. Platform Loader double-checks total weight on display
7. Head referee starts clock and athlete lifts
8. System receives Socket.IO event: `lift_completed`
9. System automatically advances to next athlete
10. System updates display with next athlete's weight and plate breakdown
11. Platform Loader sees new weight: "110 kg"
12. System calculates difference: "+5 kg" (or "-15 kg" if lighter)
13. System highlights which plates to ADD or REMOVE:
    - Example: "REMOVE: 2.5kg × 1, ADD: 5kg × 1"
14. Platform Loader makes plate changes quickly
15. Return to step 7 for next lift

### Alternative Flows

**A1: Large Weight Jump (>20kg difference)**
- At step 12: System detects weight jump is > 20kg
- System displays alert: "LARGE WEIGHT CHANGE: +45kg"
- System shows full plate breakdown (not just difference)
- Platform Loader has extra time to prepare
- Continue from step 14

**A2: Athlete Manager Updates Weight Mid-Flight**
- At step 3: Display shows upcoming athlete weight "100kg"
- Athlete Manager changes weight to "105kg" (UC3a)
- System receives Socket.IO event: `attempt_weight_updated`
- System immediately recalculates plate breakdown
- System updates "On Deck" section with new plates needed
- Platform Loader sees updated information before athlete's turn
- Continue from step 3

**A3: Switch Between Men's and Women's Athletes**
- At step 10: Next athlete is female (previous was male)
- System detects bar weight change: 20kg → 15kg
- System displays alert: "BAR CHANGE: Switch to 15kg Women's Bar"
- System recalculates all plate weights for 15kg bar
- Platform Loader changes bar and loads plates
- Continue from step 14

**A4: Invalid or Impossible Weight**
- At step 10: Weight is not possible with standard plates (e.g., 101.25kg)
- System displays warning: "INVALID WEIGHT: 101.25kg cannot be loaded with standard plates"
- System shows closest possible weight: "100kg or 102.5kg"
- Platform Loader notifies Athlete Manager
- Athlete Manager corrects weight
- Continue from step 3

**A5: No Active Flight**
- At step 3: Competition created but no flight started yet
- System displays waiting screen:
   - Competition name
   - Message: "Waiting for competition to start..."
- System listens for `flight_started` event
- Flow continues from step 3

**A6: Connection Lost**
- At step 8: WebSocket disconnects
- System displays reconnection indicator (corner of screen)
- System automatically reconnects
- On reconnect: System fetches current lift state
- System updates display with current athlete and plates
- Flow continues

### Postconditions
- Platform Loader knows exactly which plates to load
- Plates loaded quickly and accurately
- Competition flow maintained without delays
- Zero loading errors that would require corrections

### Success Metrics
- Plate breakdown displayed within 200ms of lift completion
- Visual diagram readable from 15+ feet away
- Zero plate loading errors
- Weight changes completed in < 30 seconds
- Large weight jumps handled smoothly with advance notice

### Technical Requirements

**Plate Calculation Algorithm:**
- Standard IPF plates: 25kg (red), 20kg (blue), 15kg (yellow), 10kg (green), 5kg (white), 2.5kg (black), 1.25kg (chrome)
- Calculate weight per side: (Total Weight - Bar Weight) / 2
- Use greedy algorithm to minimize total number of plates
- Always show largest plates first (25kg before 20kg, etc.)

**Visual Plate Display:**
- Show plates as horizontal stacked rectangles (simulating bar view)
- Color-coded by weight (matches real plate colors)
- Width proportional to plate size
- Label each plate clearly: "25 kg × 2"

**Bar Weight Auto-Detection:**
- Men's bar: 20kg
- Women's bar: 15kg
- System should detect gender from athlete data if available
- Allow manual override if needed

---

## UC4a: View Venue Audience Display (Vote Lights)

**ID:** UC4a
**Actor:** Venue Audience Member (watching big screen at competition)
**Preconditions:**
- Competition exists and is active
- Venue audience display URL is projected on large screen/TV at competition venue

**Priority:** High (Core competition experience)

### Main Flow
1. Admin projects venue audience URL on large screen/TV visible to audience
2. Browser opens to venue audience display page
3. System extracts audienceToken from URL query parameter
4. System validates token against database
5. System loads competition data
6. System establishes Socket.IO connection
7. System joins competition room for real-time updates
8. System displays large, TV-optimized interface showing:
   - Competition name (header)
   - Current lift panel:
     - Athlete name (very large font, readable from 30+ feet)
     - Lift type icon (squat/bench/deadlift)
     - Attempt number (1, 2, or 3)
     - Weight display (large font)
     - **Timer display** (countdown clock from head referee)
   - Three large circles representing judges:
     - LEFT judge circle (grey/empty initially)
     - CENTER judge circle (grey/empty initially)
     - RIGHT judge circle (grey/empty initially)
     - Labels: "LEFT" "CENTER" "RIGHT" under circles
9. Admin starts a lift (UC3, step 7)
10. System receives Socket.IO event: `lift_started`
11. System updates display:
    - Shows new athlete name
    - Shows lift details (type, attempt, weight)
    - Resets all three circles to grey/empty
    - Timer shows "READY" or "60"
12. Head referee starts clock
13. System receives Socket.IO event: `clock_started`
14. Timer begins countdown (updates every second)
15. Athlete performs lift
16. Judges begin voting (audience cannot see individual votes yet)
17. System receives Socket.IO events: `vote_submitted` (internal, not displayed)
    - **Critical:** Individual votes are NOT shown to audience
    - Circles remain grey/empty during voting phase
    - **Maintains suspense** - audience waits for all 3 votes
18. When all 3 votes received:
    - System receives Socket.IO event: `lift_completed`
    - Event data: `{ liftId, result: "GOOD_LIFT", votes: [{position: "LEFT", decision: "WHITE"}, ...] }`
19. **All three circles update SIMULTANEOUSLY:**
    - LEFT circle turns WHITE or RED (smooth animation)
    - CENTER circle turns WHITE or RED (smooth animation)
    - RIGHT circle turns WHITE or RED (smooth animation)
    - **Dramatic reveal effect** - all lights appear at once
20. System displays result banner:
    - Large text: "GOOD LIFT" (green background) or "NO LIFT" (red background)
    - Banner appears for 3 seconds with animation
21. System waits for next lift (return to step 10)

### Alternative Flows

**A1: Invalid Audience Token**
- At step 4: Token not found in database
- System displays error: "Invalid audience link"
- Flow ends

**A2: No Current Lift**
- At step 8: No lift currently IN_PROGRESS
- System displays waiting screen:
   - Competition name
   - Message: "Waiting for next lift..."
   - Optional: Previous lift result
- System listens for `lift_started` event
- Flow continues from step 10

**A3: Connection Lost During Voting**
- At step 17: WebSocket disconnects
- System displays reconnection indicator (small, corner of screen)
- System automatically reconnects
- On reconnect: System fetches current lift state
- If all 3 votes complete: Show all circles simultaneously
- If votes still pending: Keep circles grey and wait for `lift_completed`
- Flow continues

**A4: Rejoining Display Mid-Lift**
- At step 8: Display connects while lift is IN_PROGRESS
- System queries API for current lift state
- System checks if all 3 votes complete
- If votes complete: Show all 3 circles with results
- If votes pending: Show grey circles, wait for `lift_completed`
- **Never show partial votes** - maintain suspense

### Postconditions
- Audience experiences suspenseful vote reveal
- All three lights appear simultaneously
- Final results displayed clearly
- Display ready for next lift

### Success Metrics
- All three vote circles update simultaneously within 200ms of `lift_completed` event
- Animations smooth and visible from back of venue (30+ feet)
- No display lag or freezing
- Display readable from any seat in venue
- **Suspense maintained** - no partial vote reveals

---

## UC4b: View Remote Audience Dashboard (Competition Progress)

**ID:** UC4b
**Actor:** Remote Audience Member (watching from home, e.g., athlete's family)
**Preconditions:**
- Competition exists and is active
- Remote audience has dashboard URL (shared link)

**Priority:** Medium (Nice-to-have for MVP)

### Main Flow
1. Remote audience member opens dashboard URL on smartphone or tablet at home
2. Browser opens to remote audience dashboard page
3. System extracts dashboardToken from URL query parameter (or uses same audienceToken)
4. System validates token against database
5. System loads competition data
6. System establishes Socket.IO connection
7. System joins competition room for real-time updates
8. System displays simple, mobile-friendly dashboard showing:
   - **Competition header:**
     - Competition name
     - Current flight: "Men's Open - Flight A - SQUAT"
   - **Up Next section:**
     - Current athlete lifting (highlighted)
     - Next 2-3 athletes "on deck" (name, attempt, weight)
   - **Current Standings / Leaderboard:**
     - Athlete names
     - Current totals (best lifts so far)
     - Sorted by total (descending)
     - Color-coded: GREEN for good lifts, RED for failed lifts
   - **Recent Results (scrolling feed):**
     - Last 5 lifts with results
     - Example: "Alice Smith - SQUAT 2 - 105kg - GOOD LIFT ✓"
9. System receives Socket.IO event: `lift_started`
10. System highlights current athlete in "Up Next" section
11. System shows loading indicator: "Lift in progress..."
12. Judges vote (remote audience does not see vote lights)
13. System receives Socket.IO event: `lift_completed`
    - Event data: `{ liftId, result, athlete, weight }`
14. System updates dashboard:
    - Adds result to "Recent Results" feed
    - Updates athlete's total if GOOD LIFT
    - Re-sorts leaderboard
    - Moves to next athlete in "Up Next"
15. System waits for next lift (return to step 9)

### Alternative Flows

**A1: Invalid Dashboard Token**
- At step 4: Token not found in database
- System displays error: "Invalid dashboard link"
- Flow ends

**A2: No Current Flight Active**
- At step 8: Competition created but no flight started yet
- System displays waiting screen:
   - Competition name
   - Message: "Competition has not started yet"
   - List of groups/flights (if available)
- System listens for `flight_started` event
- Flow continues from step 9

**A3: Connection Lost**
- At step 13: WebSocket disconnects
- System displays reconnection indicator (top of screen)
- System automatically reconnects
- On reconnect: System fetches latest competition state
- System updates dashboard with current standings and recent results
- Flow continues

**A4: User Searches for Specific Athlete**
- At step 8: Remote audience member wants to find specific athlete (e.g., their granddaughter)
- System provides search bar at top of dashboard
- User types athlete name
- System filters leaderboard to show matching athlete(s)
- User can clear search to see full leaderboard again

**A5: Multiple Flights Running (Future)**
- At step 8: Multiple platforms/flights active simultaneously
- System provides flight selector dropdown
- User selects flight to follow
- Dashboard updates to show selected flight's athletes and results

### Postconditions
- Remote audience stays informed of competition progress
- Standings updated in real-time
- Remote audience knows when specific athlete is lifting
- Simple, accessible interface for all ages

### Success Metrics
- Dashboard updates within 1 second of lift completion
- Interface easy to use on mobile devices (phone/tablet)
- Large text readable without zooming
- Clear indication of which athlete is lifting next
- Zero confusion about competition status

---

## UC5: View Historical Dashboard

**ID:** UC5
**Actor:** Admin (post-competition)
**Preconditions:**
- At least one competition has been completed
- Admin navigates to dashboard page

**Priority:** Low (Nice-to-have for MVP)

### Main Flow
1. Admin navigates to dashboard URL (e.g., `https://judgeme.app/dashboard`)
2. System displays list of all competitions from database
3. System shows competition cards/table with:
   - Competition name
   - Date (formatted: "March 15, 2026")
   - Duration (calculated: "2h 45m")
   - Number of participants
   - Total lifts attempted
   - Successful lifts (GOOD LIFT count)
   - Success rate percentage
4. Admin clicks on specific competition to view details
5. System navigates to detailed stats page
6. System fetches and displays:
   - **Competition Summary:**
     - All fields from step 3
     - Start and end timestamps
   - **Per-Judge Statistics:**
     - LEFT judge: X white lights, Y red lights
     - CENTER judge: X white lights, Y red lights
     - RIGHT judge: X white lights, Y red lights
   - **Athlete Results:**
     - Table with athlete names
     - Best squat, bench, deadlift
     - Total (sum of best lifts)
     - Sorted by total (descending)
   - **Lift-by-Lift Results (optional):**
     - Expandable table showing all lifts
     - Each lift shows: athlete, type, attempt, result, individual votes
7. Admin reviews statistics
8. Admin optionally exports data (future feature)

### Alternative Flows

**A1: No Competitions Yet**
- At step 2: Database has zero completed competitions
- System displays empty state:
   - Message: "No competitions yet. Create your first competition!"
   - Button: "Create Competition" (links to homepage)

**A2: Filter by Date Range**
- At step 3: Admin uses date range filter
- System filters competitions to selected range
- Display updates with filtered results

**A3: Search by Competition Name**
- At step 3: Admin enters search query
- System filters competitions by name (case-insensitive)
- Display updates with search results

### Postconditions
- Admin has viewed historical data
- Statistics calculated correctly
- Data useful for future planning

### Success Metrics
- Dashboard loads in < 2 seconds
- Statistics accurate (verified against database)
- Data presented clearly and is actionable

---

## UC6: Competition Host Views Announcer Display

**ID:** UC6
**Actor:** Competition Host / Announcer (MC)
**Preconditions:**
- Competition exists and is active
- Competition Host has received announcer display URL
- Flight has been started by Admin

**Priority:** Medium (Enhances competition experience)

### Main Flow
1. Competition Host opens announcer display URL on tablet or laptop at announcer booth
2. System extracts announcerToken from URL query parameter (or uses admin/special token)
3. System validates token against database
4. System loads active competition data
5. System establishes Socket.IO connection
6. System joins competition room for real-time updates
7. System displays announcer-optimized interface showing:
   - **Current flight header:**
     - Flight name: "Men's Open - Flight A"
     - Discipline: "SQUAT" (large, color-coded icon)
   - **Current Athlete Panel (highlighted):**
     - Name (very large font)
     - Discipline: "Squat"
     - Attempt number: "Attempt 2 of 3"
     - Weight: "105 kg"
     - Status: "ON PLATFORM" or "LIFTING NOW"
   - **On Deck Section (next 2-3 athletes):**
     - Each shows: Name, Attempt, Weight
     - Example: "Bob Johnson - Squat 1 - 100kg"
     - Clearly labeled: "NEXT" and "ON DECK"
   - **Timer display** (shows head referee's countdown)
8. System receives Socket.IO event: `lift_started`
9. System updates Current Athlete Panel with new athlete details
10. System shifts "On Deck" queue:
    - Previous "NEXT" athlete moves to "Current"
    - Next athlete in queue moves to "NEXT"
    - Queue auto-scrolls
11. Competition Host reads information aloud:
    - "Next up, we have Alice Smith attempting her second squat at 105 kilograms"
12. System receives Socket.IO event: `clock_started`
13. Timer begins countdown (visible to announcer for timing cues)
14. Athlete performs lift
15. System receives Socket.IO event: `lift_completed`
    - Event data: `{ liftId, result, athlete, weight }`
16. System briefly displays result next to athlete name:
    - "Alice Smith - 105kg - GOOD LIFT ✓" (green)
    - Or "Alice Smith - 105kg - NO LIFT ✗" (red)
17. System waits 2-3 seconds for announcer to acknowledge result
18. System automatically advances to next athlete (return to step 8)

### Alternative Flows

**A1: Invalid Announcer Token**
- At step 3: Token not found or invalid
- System displays error: "Invalid announcer link. Contact admin."
- Flow ends

**A2: No Active Flight**
- At step 7: Competition created but no flight started yet
- System displays waiting screen:
   - Competition name
   - Message: "Waiting for admin to start flight..."
   - List of scheduled flights (if available)
- System listens for `flight_started` event
- Flow continues from step 8

**A3: Attempt Weight Updated by Athlete Manager**
- At step 7: Display shows athlete with weight "100kg"
- Athlete Manager updates attempt weight to "105kg" (UC3a)
- System receives Socket.IO event: `attempt_weight_updated`
- System immediately updates weight display in Current or On Deck section
- Competition Host sees updated weight before announcing

**A4: Flight Changes Mid-Competition**
- At step 7: Admin switches to different flight (e.g., from SQUAT to BENCH)
- System receives Socket.IO event: `flight_started` with new discipline
- System displays notification: "Flight changed to BENCH"
- System updates display with new flight's athletes and discipline
- Competition Host acknowledges change and continues

**A5: Connection Lost**
- At step 12: WebSocket disconnects during competition
- System displays reconnection indicator (top corner)
- System automatically reconnects
- On reconnect: System fetches current lift state
- System updates display to match current competition state
- Flow continues

**A6: Announcer Needs to Review Previous Results**
- At step 7: Competition Host wants to see recent lift results
- System provides "Recent Results" collapsible section
- Shows last 5-10 lifts with athlete, weight, result
- Competition Host can quickly reference without losing current athlete view

### Postconditions
- Competition Host has clear view of current and upcoming athletes
- Announcements are accurate and timely
- Audience experience enhanced by professional commentary
- Competition flows smoothly with minimal delays

### Success Metrics
- Display updates within 500ms of lift events
- Text readable from 6+ feet away (announcer booth to display)
- No missed athlete announcements
- "On Deck" section always shows next 2-3 athletes
- Zero confusion about athlete names, weights, or attempt numbers

---

## Use Case Diagram

```
                                    JudgeMe System

┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  [Admin]                                                                 │
│    │                                                                     │
│    ├──────> UC1: Create Competition                                     │
│    │         │                                                           │
│    │         └──────> Generate Secure URLs                              │
│    │                                                                     │
│    ├──────> UC3: Control Competition Flow                               │
│    │         │                                                           │
│    │         ├──────> Start Lift                                        │
│    │         ├──────> Monitor Voting                                    │
│    │         └──────> End Competition                                   │
│    │                                                                     │
│    └──────> UC5: View Historical Dashboard                              │
│                                                                          │
│                                                                          │
│  [Judge]                                                                 │
│    │                                                                     │
│    └──────> UC2: Vote on Lift                                           │
│             │                                                            │
│             ├──────> Access via Link (no login)                         │
│             └──────> Submit WHITE/RED vote                              │
│                                                                          │
│                                                                          │
│  [Audience]                                                              │
│    │                                                                     │
│    └──────> UC4: View Real-Time Display                                 │
│             │                                                            │
│             ├──────> Watch vote lights                                  │
│             └──────> See final results                                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case Priority Matrix

| Use Case | Priority | Complexity | MVP Required |
|----------|----------|------------|--------------|
| UC1: Create Competition | HIGH | Low | ✅ Yes |
| UC1a: Enter Athletes (Competition Manager) | HIGH | Medium | ✅ Yes |
| UC1b: Create Groups/Flights (Competition Manager) | HIGH | Medium | ✅ Yes |
| UC2: Judge Votes (Side Refs with Vote Changing) | HIGH | Medium | ✅ Yes |
| UC2a: Head Ref Clock Control (with Vote Changing) | HIGH | Medium | ✅ Yes |
| UC3: Admin Starts Flight by Group/Discipline | HIGH | Low | ✅ Yes |
| UC3a: Update Attempt Weights (Athlete Manager) | HIGH | Medium | ✅ Yes |
| UC3b: Platform Loader Plate Display | HIGH | Medium | ✅ Yes |
| UC4a: Venue Audience Display (Vote Lights) | HIGH | Medium | ✅ Yes |
| UC4b: Remote Audience Dashboard | MEDIUM | Medium | ⚠️ Nice-to-have |
| UC5: Historical Dashboard | LOW | Low | ⚠️ Nice-to-have |
| UC6: Competition Host Announcer Display | MEDIUM | Low | ⚠️ Nice-to-have |
