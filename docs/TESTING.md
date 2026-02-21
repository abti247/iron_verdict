# Iron Verdict Manual Testing Guide

## Multi-Tab Testing Procedure

### Setup
1. Start server: `uvicorn iron_verdict.main:app --reload`
2. Open 4 browser tabs/windows

### Test Flow

**Tab 1 - Left Judge:**
1. Click "Create New Session"
2. Note the session code (e.g., ABC123)
3. Click "Left Judge"
4. Verify: Timer shows 60, voting buttons enabled

**Tab 2 - Center Judge (Head):**
1. Enter session code from Tab 1
2. Click "Join Session"
3. Click "Center Judge (Head)"
4. Verify: Timer shows 60, voting buttons enabled, head judge controls visible

**Tab 3 - Right Judge:**
1. Enter session code
2. Click "Join Session"
3. Click "Right Judge"
4. Verify: Timer shows 60, voting buttons enabled

**Tab 4 - Display:**
1. Enter session code
2. Click "Join Session"
3. Click "Display"
4. Verify: Timer shows 60, three empty circles visible

### Test Timer (Tab 2 - Head Judge)
1. Click "Start Timer"
2. Verify all 4 tabs show countdown from 60
3. Wait for timer to reach 0
4. Verify timer turns red on all tabs
5. Click "Reset Timer"
6. Verify all tabs show 60 again

### Test Voting Flow
1. **Tab 1:** Click "White", then "Lock In"
   - Verify button disabled in Tab 1
2. **Tab 2:** Click "Red", then "Lock In"
   - Verify button disabled in Tab 2
3. **Tab 3:** Click "White", then "Lock In"
   - Verify button disabled in Tab 3
   - **All tabs:** Results appear simultaneously
   - **Tab 4:** Three circles fill with colors (White, Red, White)

### Test Next Lift (Tab 2 - Head Judge)
1. Click "Next Lift"
2. Verify all tabs:
   - Voting buttons re-enabled
   - Previous votes cleared
   - Display circles empty again

### Test End Session (Tab 2 - Head Judge)
1. Click "End Session"
2. Confirm dialog appears
3. Click OK
4. Verify all 4 tabs receive session ended message
5. Verify all tabs return to landing screen

## Edge Cases

### Role Already Taken
1. Open 2 tabs
2. Create session in Tab 1, join as Left Judge
3. In Tab 2, join same session, try to join as Left Judge
4. Verify: Error message "Role already taken"

### Invalid Session Code
1. Enter "XXXXXX" as session code
2. Try to join
3. Verify: Error message "Session not found"

### Judge Disconnection
1. Set up full session (3 judges + display)
2. Close one judge tab
3. Verify display shows disconnection (future feature)

## Success Criteria

- ✓ All 4 devices can join session
- ✓ Timer syncs across all devices
- ✓ Votes lock independently
- ✓ Results show simultaneously when all locked
- ✓ Head judge can advance to next lift
- ✓ Head judge can end session
- ✓ Role validation works
