# Display Screen Visibility Improvements

**Date:** 2026-02-26

## Goal

Improve audience visibility on the display screen by scaling up key elements and adding a connection status indicator.

## Changes

### 1. Size increases (+20%)

| Element | CSS class | Property | Before | After |
|---|---|---|---|---|
| Vote orbs | `.display-orb` | `width` / `height` | `min(20vw, 200px)` | `min(24vw, 240px)` |
| Reasoning text | `.display-orb-reason` | `font-size` | `1.8rem` | `2.16rem` |
| Verdict stamp | `.verdict-stamp` | `font-size` | `min(7vw, 60px)` | `min(8.4vw, 72px)` |

File: `src/iron_verdict/static/css/components.css`

### 2. Connection status dot on display screen

Add a `conn-dot` to the `.display-tag` element (top-right of display screen), to the left of the session name / DEMO label. Reuses existing `.conn-dot` CSS and `connectionStatus` Alpine.js data property. Shows in both real sessions and demo mode.

**HTML change** (`index.html`): add `<span class="conn-dot" :class="connectionStatus"></span>` as first child of `.display-tag`.

**CSS change** (`layout.css`): convert `.display-tag` to a flex row with `align-items: center` and a small `gap`.

## Files Affected

- `src/iron_verdict/static/css/components.css` — orb size, reasoning font size, verdict font size
- `src/iron_verdict/static/css/layout.css` — display-tag flex layout
- `src/iron_verdict/static/index.html` — add conn-dot span to display-tag
