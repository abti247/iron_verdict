# Fix Orb Spacing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the three judge-result orbs and display-screen orbs evenly spaced regardless of reason text length.

**Architecture:** Two CSS-only changes replacing flexbox with CSS grid on the two orb container elements. No HTML or JS changes needed.

**Tech Stack:** CSS Grid

---

### Task 1: Fix judge results panel spacing

**Files:**
- Modify: `src/iron_verdict/static/css/components.css:353-358`

**Step 1: Open the file and locate `.judge-results-orbs`**

Open `src/iron_verdict/static/css/components.css` around line 353.

Current code:
```css
.judge-results-orbs {
    display: flex;
    gap: 2rem;
    justify-content: center;
    padding: 4px 0 8px;
}
```

**Step 2: Replace with grid layout**

```css
.judge-results-orbs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    justify-items: center;
    padding: 4px 0 8px;
}
```

**Step 3: Visual verification**

Start the dev server and open a judge URL with `?demo=left_judge` (or any judge role). Cast a vote. In the Results section at the bottom, confirm the three orbs are evenly spaced even when some have reason text and others don't (white votes have no reason text).

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "fix: even orb spacing on judge results panel using CSS grid"
```

---

### Task 2: Fix display screen orb spacing

**Files:**
- Modify: `src/iron_verdict/static/css/layout.css:256-259`

**Step 1: Open the file and locate `.display-lights`**

Open `src/iron_verdict/static/css/layout.css` around line 256.

Current code:
```css
.display-lights {
    display: flex;
    gap: 8rem;
}
```

**Step 2: Replace with grid layout**

```css
.display-lights {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    justify-items: center;
}
```

**Step 3: Visual verification**

Open a display URL with `?demo=display`. Trigger a vote result. Confirm the three orbs on the display screen are evenly spaced.

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/layout.css
git commit -m "fix: even orb spacing on display screen using CSS grid"
```
