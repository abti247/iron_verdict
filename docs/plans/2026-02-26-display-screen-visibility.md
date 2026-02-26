# Display Screen Visibility Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Increase orb, reasoning text, and verdict sizes by 20% on the display screen, and add a connection status dot to the display screen's top-right tag.

**Architecture:** Pure CSS/HTML changes. Three CSS value edits in `components.css`, one CSS layout change in `layout.css`, and one HTML element added in `index.html`. No backend changes, no JS changes.

**Tech Stack:** HTML, Alpine.js (existing `connectionStatus` data property reused), CSS.

---

### Task 1: Increase orb size by 20%

**Files:**
- Modify: `src/iron_verdict/static/css/components.css` (around line 322)

**Step 1: Open components.css and locate `.display-orb`**

Find the `.display-orb` rule — it starts around line 321. The current size values are:
```css
width: min(20vw, 200px);
height: min(20vw, 200px);
```

**Step 2: Apply the change**

Replace both lines with:
```css
width: min(24vw, 240px);
height: min(24vw, 240px);
```

**Step 3: Verify visually**

Start the dev server (`uvicorn iron_verdict.main:app --reload`), open the display screen, confirm orbs are noticeably larger.

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "feat: increase display orb size by 20%"
```

---

### Task 2: Increase reasoning text font size by 20%

**Files:**
- Modify: `src/iron_verdict/static/css/components.css` (around line 313)

**Step 1: Locate `.display-orb-reason`**

Find the rule around line 312. Current font size:
```css
font-size: 1.8rem;
```

**Step 2: Apply the change**

Replace with:
```css
font-size: 2.16rem;
```

**Step 3: Verify visually**

On the display screen with a completed lift (red/blue/yellow vote + reason visible), confirm the reasoning text below the orbs is larger.

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "feat: increase display orb reasoning text size by 20%"
```

---

### Task 3: Increase verdict stamp font size by 20%

**Files:**
- Modify: `src/iron_verdict/static/css/components.css` (around line 394)

**Step 1: Locate `.verdict-stamp`**

Find the rule around line 392. Current font size:
```css
font-size: min(7vw, 60px);
```

**Step 2: Apply the change**

Replace with:
```css
font-size: min(8.4vw, 72px);
```

**Step 3: Verify visually**

Trigger a verdict on the display screen, confirm "GOOD LIFT" / "NO LIFT" text is larger.

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "feat: increase verdict stamp font size by 20%"
```

---

### Task 4: Add connection dot to display screen

**Files:**
- Modify: `src/iron_verdict/static/index.html` (around line 321)
- Modify: `src/iron_verdict/static/css/layout.css` (around line 236)

**Step 1: Add the conn-dot span to `.display-tag` in index.html**

Find the `.display-tag` div (around line 321):
```html
<div class="display-tag">
    <span x-show="!isDemo" x-text="sessionName"></span>
    <span x-show="isDemo">DEMO</span>
</div>
```

Replace with:
```html
<div class="display-tag">
    <span class="conn-dot" :class="connectionStatus"></span>
    <span x-show="!isDemo" x-text="sessionName"></span>
    <span x-show="isDemo">DEMO</span>
</div>
```

**Step 2: Make `.display-tag` a flex row in layout.css**

Find `.display-tag` (around line 236):
```css
.display-tag {
    position: absolute;
    top: 16px;
    right: 20px;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    font-size: 18px;
    letter-spacing: 2px;
    color: var(--text-dim);
}
```

Replace with:
```css
.display-tag {
    position: absolute;
    top: 16px;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    font-size: 18px;
    letter-spacing: 2px;
    color: var(--text-dim);
}
```

**Step 3: Verify visually**

Open the display screen. Confirm:
- An 8px dot appears to the left of the session name (or DEMO label)
- Dot is dark gray when disconnected
- Dot turns green when connected
- Dot turns yellow and pulses when reconnecting (test by temporarily blocking the WS connection)

**Step 4: Commit**

```bash
git add src/iron_verdict/static/index.html src/iron_verdict/static/css/layout.css
git commit -m "feat: add connection status dot to display screen"
```
