# Judge Screen Orb & Reason Text Size Fix

## Problem

After increasing display screen orb and font sizes (20%), the judge screen result orbs (60px) and reason text (2.16rem) are too large on phones. With 3 orbs side-by-side, long reason labels like "Supporting contact on legs" wrap across multiple lines and push the third orb off-screen.

## Solution

Two CSS-only changes in `components.css`. No HTML changes required.

### Change 1: Reduce judge screen orb size

`.display-orb--sm` is used exclusively on the judge screen result orbs.

```css
.display-orb--sm {
    width: 44px;   /* was 60px */
    height: 44px;  /* was 60px */
}
```

### Change 2: Scope reason text size to judge screen

Add a descendant rule scoped to `.judge-results-orbs`, which only exists on the judge screen.

```css
.judge-results-orbs .display-orb-reason {
    font-size: 0.7rem;
    max-width: 80px;
}
```

## Scope

- Display screen orbs and reason text: **unaffected**
- Judge screen result orbs and reason text: **smaller**
- Judge screen vote buttons and other UI: **unaffected**
