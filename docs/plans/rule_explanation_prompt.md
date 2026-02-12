# Task: Implement Card Reason Display for Powerlifting Judging App

## Overview
Add a feature to display rule explanations on the display screen after judges vote. This helps the audience understand why lifts receive red, blue, or yellow cards.

## Requirements

### 1. Head Judge Settings Panel

Create a settings panel for the head judge with two controls:

**A. Toggle: Show Rule Explanations**
- Checkbox or toggle switch labeled "Show rule explanations"
- Default: OFF
- Persist in localStorage
- When OFF: Skip explanation display, proceed directly to next attempt after showing vote result
- When ON: Show explanation after vote result

**B. Dropdown: Current Lift Type**
- Options: "Squat" | "Bench Press" | "Deadlift"
- Default: "Squat"
- Persist in localStorage
- Determines which rules are shown on the display
- Large, clearly visible selector

### 2. Card Reasons Database
Create a data structure with short, audience-friendly reasons for each card color and lift type:

const cardReasons = {
  squat: {
    red: [
      "Not deep enough",
      "No upright position"
    ],
    blue: [
      "Double bounce",
      "Movement during ascent"
    ],
    yellow: [
      "Foot movement",
      "Didn't wait for signal",
      "Elbow touching thighs",
      "Dropped the bar",
      "Incomplete attempt"
    ]
  },
  
  bench: {
    red: [
      "Bar didn't touch chest",
      "Elbows not low enough"
    ],
    blue: [
      "Downward movement during press",
      "Arms not fully locked"
    ],
    yellow: [
      "Bar bounced on chest",
      "Didn't wait for signal",
      "Position changed",
      "Feet moved or lifted",
      "Bar touched uprights",
      "Incomplete attempt"
    ]
  },
  
  deadlift: {
    red: [
      "Knees not locked",
      "Shoulders not back"
    ],
    blue: [
      "Downward movement",
      "Supported on thighs"
    ],
    yellow: [
      "Lowered before signal",
      "Dropped the bar",
      "Foot movement",
      "Incomplete attempt"
    ]
  }
};

### 3. Display Timing Sequence

Implement automatic state transitions with these exact timings:

**Phase 1: Vote Result (3 seconds)**
- Show judge lights (colored circles: ⚪🔴🔵🟡)
- Duration: Exactly 3 seconds
- Next: If explanations enabled AND lift invalid → Phase 2, otherwise → Phase 3

**Phase 2: Rule Explanation (6 seconds) - CONDITIONAL**
- Only shown if:
  - Head judge has "Show rule explanations" enabled AND
  - The lift got any red/blue/yellow card
- Display format:
  - Display result indicators: ✅ VALID, ❌ INVALID (invalid if only 1 white vote)
  - Show ONLY the unique invalid card colors that were given and only for the lift selected by the head judge
  - Group by card color
  - Do NOT show white cards or duplicate reasons
  - One line per unique invalid reason
  - If there are multiple reasons for e.g. a yellow card, list them all.

**Phase 3: Ready for Next Attempt**
- Clear the display (or show idle state)
- System ready for next athlete
- Head judge can start timer for next attempt