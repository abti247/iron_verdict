# Card Reason Display — Design

**Date:** 2026-02-10

## Goal

After judges vote, automatically show rule explanations on the display screen so the audience understands why a lift received red, blue, or yellow cards.

---

## Components

### 1. Head Judge Settings Panel

New UI section on the judge screen, visible only to the head judge (center judge).

Two controls:
- **Toggle** — "Show rule explanations" (default: off)
- **Dropdown** — Current lift type: Squat | Bench Press | Deadlift (default: Squat)

Both settings persist in localStorage and are synced to the server on change.

### 2. Card Reasons Data

A static client-side data structure mapping lift type × card color → list of short, audience-friendly reason strings. Covers squat, bench, and deadlift for red, blue, and yellow cards.

### 3. Display Timing Sequence

Three phases, triggered automatically when `show_results` is received:

| Phase | Duration | Condition | Content |
|-------|----------|-----------|---------|
| 1: Vote Result | 3s | Always | Existing colored judge circles |
| 2: Rule Explanation | 6s | Only if explanations enabled AND any non-white card present | VALID/INVALID header + grouped reasons by card color |
| 3: Idle | Until next lift | Always | Cleared display |

Phase 2 shows only unique non-white card colors from the actual votes. Reasons listed per color come from the card reasons data for the current lift type.

---

## Data Flow

```
Head judge toggles setting
  → localStorage updated
  → WebSocket: settings_update { showExplanations, liftType }
  → Server stores in session["settings"]

All judges lock votes
  → Server broadcasts show_results { votes, showExplanations, liftType }

Display client receives show_results
  → Phase 1 (3s)
  → If showExplanations AND non-white cards exist → Phase 2 (6s) → Phase 3
  → Else → Phase 3 directly

Head judge clicks "Next Lift" (unchanged)
  → Server resets votes
  → Display returns to idle
```

---

## Backend Changes

**`session.py`**
- Add `settings: { show_explanations: false, lift_type: "squat" }` to session state
- Add `update_settings()` method

**`main.py`**
- Handle `settings_update` message (head judge only)
- Inject session settings into `show_results` broadcast payload

---

## Frontend Changes

**Judge screen**
- Settings panel (head judge only): toggle + lift type dropdown
- Alpine state: `showExplanations`, `liftType`
- `saveSettings()`: write localStorage + send `settings_update`
- Load from localStorage on init

**Display screen**
- Alpine state: `displayPhase` ('votes' | 'explanation' | 'idle')
- `show_results` handler: starts phase timer sequence
- Card reasons data structure (static JS object)
- Explanation view: VALID/INVALID indicator + reasons grouped by card color
- `reset_for_next_lift` handler: unchanged, resets to idle

---

## Out of Scope

- Editing card reasons in the UI
- Per-session custom reasons
- Translating reasons to other languages
