# Judge Reason Selection — Design

**Date:** 2026-02-21

## Problem

When a head judge enables "show rule explanations", the display screen currently shows all possible reasons for the given card color. This leaves too much room for interpretation. The fix: each judge selects a specific reason before locking in, and only that reason is shown beneath their light on the display.

## Changes in Scope

### 1. Judge Voting Flow (Frontend)

Two-step voting for non-white votes:

- **Step 1 — Color selection** (unchanged): judge taps WHITE / RED / BLUE / YELLOW.
  - WHITE → skip to Lock In immediately (no reason needed).
  - Non-white → transition to Step 2.
- **Step 2 — Reason selection** (new): scrollable list of full-text reasons for the chosen color + current lift type.
  - Header shows `← back` + color name.
  - Each row is a large tap target.
  - Selected reason is highlighted.
  - Tapping `← back` returns to Step 1 with color still selected.
  - Lock In appears immediately (non-mandatory mode) or only after a reason is selected (mandatory mode).

### 2. Data Flow & Backend

**Session state** — new field per judge:
```
"current_reason": str | None
```

**Settings** — new field alongside `show_explanations`:
```
"require_reasons": bool  (default: false)
```

**`vote_lock` message** — new optional field:
```json
{ "type": "vote_lock", "color": "yellow", "reason": "Buttocks up" }
```

**Backend validation** — if `require_reasons` is true and color is non-white, reject `vote_lock` without a reason.

**`show_results` broadcast** — new `reasons` field:
```json
{
  "votes": { "left": "yellow", "center": "white", "right": "yellow" },
  "reasons": { "left": "Buttocks up", "center": null, "right": "Incomplete lift" }
}
```

`settings_update` broadcast carries `require_reasons` alongside existing fields.

### 3. Display Screen

- **Explanation phase eliminated.** The separate "show all possible reasons" phase is removed entirely.
- **Reason label** shown beneath each orb when:
  - `show_explanations` is on, AND
  - that judge's vote is non-white, AND
  - that judge submitted a reason.
- **Orbs** spaced wider horizontally to accommodate reason text.
- **Verdict** ("Good Lift" / "No Lift") shown simultaneously with orbs — no separate phase.
- **Head judge settings bar** gains a "Require reasons" toggle.

Visual layout on display:
```
     ●              ●              ●
   YELLOW          WHITE          YELLOW

 Buttocks up                  Incomplete
                                  lift
```

## Settings Summary

| Setting | Existing? | Effect |
|---|---|---|
| Show rule explanations | Yes (renamed context) | Shows chosen reason beneath each light on display |
| Require reasons | New | Forces judges to pick a reason before locking non-white vote |

## Out of Scope

- Multi-reason selection (one reason per judge only)
- Reason selection for white votes
- Editing reasons after lock-in
