# JudgeMe Design: Playful & Dimensional

**Date:** 2026-02-09
**Project:** JudgeMe - Powerlifting Competition Judging
**Design Direction:** Playful & Dimensional (with depth and visual interest)
**Status:** Design Complete - Ready for Implementation
**Reference:** `example-dimensional.html`

---

## Overview

This design builds on the **Playful & Accessible** foundation but adds significant **visual depth and dimension** through shadows, gradients, and enhanced animations. The result is a visually engaging interface that feels tactile and polished while maintaining the warm, friendly aesthetic.

### Key Differentiators from Flat Design

1. **Multi-level shadow system** - 4 shadow depths for visual hierarchy
2. **Gradient backgrounds** - Subtle gradients on buttons, cards, and judge lights
3. **Enhanced hover effects** - Pronounced lifting and shadow changes
4. **Text shadows** - Adds depth to headings and timers
5. **Radial gradients on judge lights** - Light source effect for realism
6. **Smooth cubic-bezier transitions** - More polished than linear transitions

---

## Color Palette

### Base Colors (Warm & Friendly)

**Backgrounds:**
- **Base Background:** `#FFF8F0` → `#FFE8D6` (gradient)
- **Surface Background:** `#FFF4E6` (elevated surfaces)

**Accents:**
- **Primary Accent:** `#FF7A5C` (coral)
- **Primary Gradient:** `#FF7A5C` → `#FF5A3C` (for buttons)
- **Secondary Accent:** `#FFB088` (light coral)

**Text:**
- **Primary Text:** `#3E2723` (warm brown/charcoal)
- **Secondary Text:** `#6D4C41` (medium brown)

**Functional:**
- **Success/Locked:** `#81C784` (soft green)
- **Success Gradient:** `#81C784` → `#66BB6A`
- **Disabled:** `#BCAAA4` (muted gray-brown)

### IPF Judge Colors (with Gradients)

**Standard Colors (unchanged):**
- White: `#FFFFFF`
- Red: `#EF4444`
- Blue: `#3B82F6`
- Yellow: `#FBBF24`

**Gradient Enhancements for Buttons:**
- **White:** `linear-gradient(135deg, #FFFFFF 0%, #F5F5F5 100%)`
- **Red:** `linear-gradient(135deg, #EF4444 0%, #DC2626 100%)`
- **Blue:** `linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)`
- **Yellow:** `linear-gradient(135deg, #FBBF24 0%, #F59E0B 100%)`

**Radial Gradients for Display Lights:**
- **White:** `radial-gradient(circle at 30% 30%, #FFFFFF 0%, #F5F5F5 100%)`
- **Red:** `radial-gradient(circle at 30% 30%, #EF4444 0%, #DC2626 100%)`
- **Blue:** `radial-gradient(circle at 30% 30%, #3B82F6 0%, #2563EB 100%)`
- **Yellow:** `radial-gradient(circle at 30% 30%, #FBBF24 0%, #F59E0B 100%)`

---

## Shadow System

**Four levels of depth for visual hierarchy:**

```css
--shadow-sm: 0 2px 4px rgba(62, 39, 35, 0.08);   /* Subtle depth */
--shadow-md: 0 4px 12px rgba(62, 39, 35, 0.12);  /* Standard depth */
--shadow-lg: 0 8px 24px rgba(62, 39, 35, 0.16);  /* Elevated depth */
--shadow-xl: 0 16px 48px rgba(62, 39, 35, 0.20); /* Dramatic depth */
```

**Usage Guidelines:**

| Element | Default | Hover | Selected/Active |
|---------|---------|-------|-----------------|
| Input fields | `inset shadow-sm` | `inset shadow-sm + ring` | - |
| Secondary buttons | `shadow-sm` | `shadow-md` | - |
| Primary buttons | `shadow-md` | `shadow-lg` | - |
| Cards/surfaces | `shadow-md` | - | - |
| Vote buttons | `shadow-md` | `shadow-lg` | `shadow-xl` |
| Lock button | `shadow-lg` | `shadow-xl` | - |
| Judge lights | `shadow-md` | - | `shadow-xl` |

---

## Typography

### Font Stacks

**Body/UI Text:**
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
```

**Timers (Sharp Sans-Serif):**
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
font-weight: 900;
letter-spacing: -0.03em;
font-variant-numeric: tabular-nums;
```

**Session Code (Monospace):**
```css
font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', 'Menlo', monospace;
font-weight: bold;
letter-spacing: -0.01em;
```

### Font Sizes & Treatments

**Display Timer:**
- Size: `240px`
- Weight: `900` (extra bold)
- Text shadow: `0 8px 24px rgba(62, 39, 35, 0.15)`
- Expired shadow: `0 8px 32px rgba(239, 68, 68, 0.4)` (red glow)

**Judge Timer:**
- Size: `48px`
- Weight: `900`
- Text shadow: `0 2px 8px rgba(62, 39, 35, 0.1)`
- Expired shadow: `0 2px 8px rgba(239, 68, 68, 0.3)` (red glow)

**Headlines:**
- H1: `32px`, bold, text shadow `0 2px 4px rgba(62, 39, 35, 0.1)`
- H2: `24px`, bold
- H3: `18px`, bold

**Vote Button Text:**
- Size: `28px`
- Weight: `bold`

**Body Text:**
- Size: `16-18px`
- Weight: Regular

---

## Spacing & Border Radius

**Spacing System:**
```css
--space-xs: 8px;
--space-sm: 12px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;
```

**Border Radius:**
```css
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 16px;
```

---

## Animations & Transitions

**Transition System:**

```css
--transition-fast: 150ms ease;                              /* Quick feedback */
--transition-smooth: 250ms cubic-bezier(0.4, 0, 0.2, 1);   /* Polished motion */
```

**Standard Transitions:**
- Button states: `all 250ms cubic-bezier(0.4, 0, 0.2, 1)`
- Input focus: `all 250ms cubic-bezier(0.4, 0, 0.2, 1)`
- Session code hover: `all 150ms ease`
- Judge lights: `all 250ms cubic-bezier(0.4, 0, 0.2, 1)`

**Hover Effects:**

| Element | Transform | Shadow Change |
|---------|-----------|---------------|
| All buttons | `translateY(-3px)` | Base → Next level |
| Vote buttons | `translateY(-4px)` | `shadow-md` → `shadow-lg` |
| Judge lights (voted) | `scale(1.05)` | `shadow-md` → `shadow-xl` |

**Active/Press Effects:**
- Buttons: `translateY(-1px)` (less lift than hover)
- Vote buttons: `translateY(-2px)`

**Selected State:**
- Vote buttons: `translateY(-2px)` + `shadow-xl` + `border: 4px solid`

---

## Component Specifications

### Background Gradient

```css
body {
    background: linear-gradient(135deg, #FFF8F0 0%, #FFE8D6 100%);
}
```

### Buttons

**Primary Button:**
```css
.btn-primary {
    background: linear-gradient(135deg, #FF7A5C 0%, #FF5A3C 100%);
    color: white;
    box-shadow: var(--shadow-md);
    transition: all var(--transition-smooth);
}

.btn-primary:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
}
```

**Secondary Button:**
```css
.btn-secondary {
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 2px solid var(--accent-secondary);
    box-shadow: var(--shadow-sm);
    transition: all var(--transition-smooth);
}

.btn-secondary:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
    border-color: var(--accent-primary);
}
```

**Muted Button:**
```css
.btn-muted {
    background: var(--bg-surface);
    color: var(--text-secondary);
    font-size: 16px;
    min-height: 48px;
    box-shadow: var(--shadow-sm);
    transition: all var(--transition-smooth);
}

.btn-muted:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
}
```

### Input Fields

```css
input[type="text"] {
    background: var(--bg-surface);
    border: 2px solid var(--accent-secondary);
    box-shadow: inset 0 2px 4px rgba(62, 39, 35, 0.06);
    transition: all var(--transition-smooth);
}

input[type="text"]:focus {
    border-color: var(--accent-primary);
    box-shadow: inset 0 2px 4px rgba(62, 39, 35, 0.06),
                0 0 0 3px rgba(255, 122, 92, 0.1);
}
```

### Cards/Surfaces

**Role Header, Judge Header:**
```css
.role-header, .judge-header {
    background: var(--bg-surface);
    padding: var(--space-md);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
}
```

### Session Code

```css
.session-code {
    font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', 'Menlo', monospace;
    font-size: 20px;
    font-weight: bold;
    color: var(--accent-primary);
    text-decoration: underline;
    letter-spacing: -0.01em;
    transition: all var(--transition-fast);
}

.session-code:hover {
    color: #FF5A3C;
}
```

### Voting Buttons

**Base Styles:**
```css
.vote-button {
    font-size: 28px;
    font-weight: bold;
    min-height: 120px;
    border: 4px solid transparent;
    box-shadow: var(--shadow-md);
    transition: all var(--transition-smooth);
}

.vote-button:hover:not(:disabled) {
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
}

.vote-button.selected {
    border-color: var(--text-primary);
    box-shadow: var(--shadow-xl);
    transform: translateY(-2px);
}
```

**Color Variants:**
```css
.vote-button.white {
    background: linear-gradient(135deg, #FFFFFF 0%, #F5F5F5 100%);
    color: var(--text-primary);
    border: 2px solid var(--text-secondary);
}

.vote-button.red {
    background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
    color: white;
}

.vote-button.blue {
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
    color: white;
}

.vote-button.yellow {
    background: linear-gradient(135deg, #FBBF24 0%, #F59E0B 100%);
    color: var(--text-primary);
}
```

### Lock Button

```css
.lock-button {
    width: 100%;
    background: linear-gradient(135deg, #81C784 0%, #66BB6A 100%);
    color: white;
    font-size: 24px;
    min-height: 80px;
    box-shadow: var(--shadow-lg);
    transition: all var(--transition-smooth);
}

.lock-button:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-xl);
}
```

### Vote Status Card

```css
.vote-status {
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
    padding: var(--space-md);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
}
```

### Judge Lights (Display Screen)

**Base Styles:**
```css
.judge-light {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: linear-gradient(135deg, #E0E0E0 0%, #BDBDBD 100%);
    border: 4px solid var(--text-secondary);
    box-shadow: var(--shadow-md);
    transition: all var(--transition-smooth);
}

.judge-light.voted {
    border-color: var(--text-primary);
    box-shadow: var(--shadow-xl);
    transform: scale(1.05);
}
```

**Color Variants (Radial Gradients):**
```css
.judge-light.white {
    background: radial-gradient(circle at 30% 30%, #FFFFFF 0%, #F5F5F5 100%);
}

.judge-light.red {
    background: radial-gradient(circle at 30% 30%, #EF4444 0%, #DC2626 100%);
}

.judge-light.blue {
    background: radial-gradient(circle at 30% 30%, #3B82F6 0%, #2563EB 100%);
}

.judge-light.yellow {
    background: radial-gradient(circle at 30% 30%, #FBBF24 0%, #F59E0B 100%);
}
```

### Timer Displays

**Display Timer (Stadium Scale):**
```css
.display-timer {
    font-size: 240px;
    font-weight: 900;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    color: var(--text-primary);
    line-height: 1;
    text-shadow: 0 8px 24px rgba(62, 39, 35, 0.15);
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
}

.display-timer.expired {
    color: var(--vote-red);
    text-shadow: 0 8px 32px rgba(239, 68, 68, 0.4);
}
```

**Judge Timer:**
```css
.judge-timer {
    font-size: 48px;
    font-weight: 900;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    color: var(--text-primary);
    text-align: center;
    text-shadow: 0 2px 8px rgba(62, 39, 35, 0.1);
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
}

.judge-timer.expired {
    color: var(--vote-red);
    text-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}
```

### Display Header

```css
.display-header {
    position: fixed;
    top: var(--space-md);
    right: var(--space-md);
    background: var(--bg-surface);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
}
```

---

## CSS Custom Properties (Complete Set)

```css
:root {
    /* Warm & Friendly Palette */
    --bg-base: #FFF8F0;
    --bg-surface: #FFF4E6;
    --accent-primary: #FF7A5C;
    --accent-secondary: #FFB088;
    --text-primary: #3E2723;
    --text-secondary: #6D4C41;
    --success: #81C784;
    --disabled: #BCAAA4;

    /* IPF Judge Colors */
    --vote-white: #FFFFFF;
    --vote-red: #EF4444;
    --vote-blue: #3B82F6;
    --vote-yellow: #FBBF24;

    /* Spacing */
    --space-xs: 8px;
    --space-sm: 12px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;

    /* Border Radius */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;

    /* Shadows - Multiple levels for depth */
    --shadow-sm: 0 2px 4px rgba(62, 39, 35, 0.08);
    --shadow-md: 0 4px 12px rgba(62, 39, 35, 0.12);
    --shadow-lg: 0 8px 24px rgba(62, 39, 35, 0.16);
    --shadow-xl: 0 16px 48px rgba(62, 39, 35, 0.20);

    /* Transitions */
    --transition-fast: 150ms ease;
    --transition-smooth: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## Layout Specifications

### Landing Page
- Centered vertical layout
- Background gradient: `linear-gradient(135deg, #FFF8F0 0%, #FFE8D6 100%)`
- Primary button with gradient and shadow
- Input with inset shadow and focus ring
- Secondary button with border and shadow
- Muted demo button at bottom

### Role Selection
- Header card with shadow
- Clickable session code with hover color change
- Judge buttons: 3-column grid
- Display button: full-width, primary style
- All buttons have shadows and hover lift

### Judge Screen
- **Header:** 3-column grid (position | timer | session code) with shadow
- **Voting Grid:** 2×2 grid with extra-large buttons (120px height)
- **Vote buttons:** Gradients, shadows, pronounced hover lift (-4px)
- **Lock button:** Full-width, green gradient, dramatic shadow
- **Vote status:** Green gradient background with shadow
- **Head controls:** Bordered section with button grid

### Display Screen
- **Header:** Fixed top-right, floating with shadow
- **Timer:** Massive (240px), bold (900), with text shadow
- **Judge Lights:** 3 circles with radial gradients, scale on voted state
- **Spacing:** Extra large gaps for visual breathing room

---

## Responsive Behavior

### Mobile (< 600px)
- Judge header: Single column (stacked)
- Display timer: `120px` (half size)
- Judge lights: `100px` diameter
- Vote buttons: Maintain `120px` height (never shrink)
- All shadows and gradients maintained
- Hover effects converted to active states on touch

### Tablet (600px - 1024px)
- Standard sizing as defined
- Optimal for judge screens
- All dimensional effects fully visible

### Desktop/TV (1024px+)
- Display timer: Full `240px`
- Judge lights: Full `180px` diameter
- Maximum shadow visibility
- Dramatic hover effects fully visible

---

## Implementation Checklist

### Phase 1: CSS Setup
- [ ] Add CSS custom properties (colors, shadows, spacing, transitions)
- [ ] Set up body gradient background
- [ ] Configure font stacks (system sans-serif for timers, monospace for codes)

### Phase 2: Button System
- [ ] Implement gradient backgrounds on all primary buttons
- [ ] Add 4-level shadow system
- [ ] Configure hover effects (transform + shadow changes)
- [ ] Add smooth cubic-bezier transitions
- [ ] Test active/press states

### Phase 3: Voting Buttons
- [ ] Create 2×2 grid layout
- [ ] Add gradient backgrounds for each color
- [ ] Implement selected state (border + shadow-xl + transform)
- [ ] Configure pronounced hover lift (-4px)
- [ ] Test on mobile touch devices

### Phase 4: Judge Lights
- [ ] Create circular elements with radial gradients
- [ ] Add voted state (scale + shadow + border)
- [ ] Implement light source effect (gradient at 30% 30%)
- [ ] Test visibility from distance

### Phase 5: Timers
- [ ] Apply system sans-serif with weight 900
- [ ] Add tabular-nums for consistent width
- [ ] Implement text shadows (normal + expired states)
- [ ] Configure tight letter-spacing (-0.03em)
- [ ] Test countdown animation smoothness

### Phase 6: Cards & Surfaces
- [ ] Add shadows to all elevated surfaces
- [ ] Implement gradient backgrounds where specified
- [ ] Add focus rings on input fields
- [ ] Test shadow hierarchy

### Phase 7: Polish
- [ ] Verify all transitions use cubic-bezier
- [ ] Test hover effects on all interactive elements
- [ ] Confirm shadow levels create proper hierarchy
- [ ] Test on different screen sizes
- [ ] Verify accessibility (contrast, touch targets)

---

## Key Design Principles

1. **Depth Through Shadows** - 4 shadow levels create clear visual hierarchy
2. **Gradients Add Richness** - Subtle gradients make surfaces feel less flat
3. **Smooth Motion** - Cubic-bezier transitions feel more polished
4. **Pronounced Feedback** - Hover effects are noticeable (-3px to -4px lift)
5. **Light Source Consistency** - All radial gradients use 30% 30% origin
6. **Text Shadows for Depth** - Timers and headings have subtle shadows
7. **Scale for Emphasis** - Judge lights scale up when voted
8. **Sharp Typography** - Extra bold (900) system fonts for timers
9. **Warm Atmosphere** - Gradient background and warm colors throughout
10. **Tactile Feel** - Every interactive element responds to hover/press

---

## Browser Compatibility

**Required Features:**
- CSS Custom Properties (all modern browsers)
- CSS Grid (IE11+)
- Flexbox (IE11+)
- Linear/Radial Gradients (all modern browsers)
- CSS Transitions (all modern browsers)
- CSS Transforms (all modern browsers)

**Minimum Versions:**
- Chrome 88+
- Firefox 85+
- Safari 14+
- Edge 88+
- iOS Safari 14+
- Android Chrome 88+

---

## Performance Considerations

1. **Hardware Acceleration** - Transforms trigger GPU acceleration
2. **Efficient Transitions** - Only transform and opacity (no layout changes)
3. **System Fonts** - No web font loading delays
4. **CSS Variables** - Computed once, reused everywhere
5. **Minimal Repaints** - Transitions don't trigger layout recalculation

---

## Success Criteria

✅ All interactive elements have visible depth (shadows)
✅ Hover effects provide clear feedback (lift + shadow change)
✅ Gradients add visual richness without feeling overdone
✅ Timers use sharp, clean fonts (no dotted zeros)
✅ Judge lights feel dimensional with radial gradients
✅ Transitions feel smooth and polished (cubic-bezier)
✅ Design maintains warm, friendly aesthetic
✅ Stadium-scale visibility preserved on display screen
✅ Touch targets remain large (60-120px)
✅ Zero scrolling on all screens

---

## Reference Implementation

**See:** `example-dimensional.html` in the `design_ideas` folder for complete working implementation of all specifications in this document.

---

## Comparison to Other Design Options

**vs. Flat Design (example.html):**
- ➕ More visually interesting and engaging
- ➕ Better feedback on interactions
- ➕ More professional/polished appearance
- ➖ Slightly more complex CSS
- ➖ More GPU usage for animations

**vs. Cool & Calming (example-cool-calming.html):**
- Different color palette (warm vs cool)
- Same dimensional approach
- Warm palette feels more inviting for sports environment

**vs. Bright & Energetic (example-bright-energetic.html):**
- Different color palette (warm vs bright)
- Same dimensional approach
- Warm palette less harsh than pure white backgrounds

---

## Next Steps for Implementation

1. **Review this document** with stakeholders
2. **Test example-dimensional.html** with actual judges on physical devices
3. **Gather feedback** on shadow intensity, hover effects, color choices
4. **Integrate into existing codebase** following the implementation checklist
5. **Test on TV/projector** to verify display screen visibility
6. **Conduct usability testing** during practice competition
7. **Iterate based on feedback** before production use