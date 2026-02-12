# Session Name Design

**Date:** 2026-02-11
**Problem:** Display screen shows session join code, allowing audience members to join as judges.

## Solution

Add a required session name at creation. Display screen shows the name; join code stays on judge/role-selection screens only.

## Changes

### Session creation (frontend)
- Add required text input "Session name" to landing page creation form
- Disable Create button until name is non-empty

### Backend (`session.py`, `main.py`)
- `POST /api/sessions` accepts `{ "name": "Platform A" }` - reject with 400 if missing/empty
- Session dict gains `name` field
- `name` included in session state and all `session_state` broadcasts

### Display screen
- Replace session code in top-right corner with session name
- Demo mode: show fixed label "DEMO" instead of session name, styled distinctly (muted/warning color)

### Judge & role selection screens
- No change - session code remains visible as-is

## Non-goals
- Session name on judge screens (not needed)
- Optional/fallback session names
- Changing join flow in any way
