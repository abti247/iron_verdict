# Iron Verdict Restyle — Design Doc

## Goal

Rename app from "JudgeMe" to "Iron Verdict" and apply the Blood & Chrome visual design (`design2-blood-chrome.html`). All existing Alpine.js logic and WebSocket behaviour is preserved unchanged.

## Approach

Full HTML restructure + CSS swap (Approach A). Each screen gets its own viewport-filling wrapper matching the design reference. No intermediate container div.

## Changes

### Metadata

- `<title>`: `Iron Verdict — Powerlifting Judging`
- Add Google Fonts link (Bebas Neue + Rajdhani, `display=swap`)
- Update CSP header: add `https://fonts.googleapis.com` to `style-src`, `https://fonts.gstatic.com` to `font-src`

### CSS

Full replacement. New design tokens:

- Backgrounds: `--bg-void #0A0A0A`, `--bg-surface #141414`, `--bg-raised #1E1E1E`
- Accent: `--blood #B91C1C`, `--blood-bright #EF4444`, `--blood-glow rgba(185,28,28,0.3)`
- Text: `--text-chrome #D4D4D4`, `--text-dim #6B6B6B`
- Fonts: Bebas Neue (headings, buttons, labels), Rajdhani (body, inputs)
- Cut-corner shapes via `clip-path: polygon(...)` utilities: `cut-corner`, `cut-corner-sm`

### HTML screen wrappers

| Screen | Old | New |
|---|---|---|
| Landing | `.container > .screen` | `.landing-wrap > .landing-panel.cut-corner` |
| Role select | `.container > .screen` | `.role-wrap > .role-panel.cut-corner` |
| Judge | `.container > .screen` | `.judge-wrap` |
| Display | `.container > .screen` | `.display-full` |

### Class renames

| Old | New |
|---|---|
| `input[type=text]` | `.chrome-input` |
| `.btn-primary` | `.btn-blood.btn-blood-primary` |
| `.btn-secondary` | `.btn-blood.btn-blood-secondary` |
| `.btn-muted` | `.btn-blood.btn-blood-ghost` |
| `.vote-button.white/red/blue/yellow` | `.vote-btn.vote-white/red/blue/yellow.cut-corner-sm` |
| `.lock-button` | `.lock-btn.cut-corner-sm` |
| `.vote-status` | `.locked-status` |
| `.judge-light` | `.display-orb` |
| `.result-indicator` | `.verdict-stamp` |
| `.card-reason-group` | `.reason-card` |
| `.card-reason-header` | `.reason-card-header` |
| `.card-reason-list` | `.reason-card-body` |
| `.display-timer` | `.display-timer-big` |

### Locked vote state

Vote grid: `:style="voteLocked ? 'opacity:0.35;pointer-events:none' : ''"`. Individual `:disabled` bindings kept for semantics.

### No changes

All Alpine.js data properties, methods, WebSocket logic, `CARD_REASONS` data, and `x-` directive bindings are untouched.

## Files affected

- `src/judgeme/static/index.html` — full restyle
- `src/judgeme/main.py` (or wherever CSP header is set) — add Google Fonts domains
