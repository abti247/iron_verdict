# Fix: Orb Spacing on Judge and Display Screens

## Problem

Orbs on the judge results panel and display screen are unevenly spaced. Each orb is wrapped in a flex column whose width is determined by its widest child (orb or reason text). When reason texts differ in length or are absent (white/good lift), wrap widths diverge — causing orbs to appear at non-uniform horizontal intervals.

## Solution

Replace flexbox with a 3-column CSS grid on both orb containers. Each column gets identical `1fr` width, so orb positions are fixed regardless of reason text length or presence.

## Changes

### `src/iron_verdict/static/css/components.css` — `.judge-results-orbs`

- `display: grid; grid-template-columns: repeat(3, 1fr); justify-items: center;`
- Remove `display: flex`, `gap: 2rem`, `justify-content: center`

### `src/iron_verdict/static/css/layout.css` — `.display-lights`

- `display: grid; grid-template-columns: repeat(3, 1fr); justify-items: center;`
- Remove `display: flex`, `gap: 8rem`
