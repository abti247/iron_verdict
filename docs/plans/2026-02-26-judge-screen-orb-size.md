# Judge Screen Orb & Reason Text Size Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce judge screen result orb size (60px → 44px) and reason text size (2.16rem → 0.7rem) without affecting the display screen.

**Architecture:** Two CSS-only edits in `components.css`. `.display-orb--sm` is already exclusive to the judge screen. A new descendant selector scoped to `.judge-results-orbs` handles the reason text.

**Tech Stack:** CSS

---

### Task 1: Set up worktree

**Files:**
- No file changes

**Step 1: Create worktree**

```bash
git worktree add .worktrees/judge-orb-size -b fix/judge-orb-size
```

**Step 2: Open worktree in editor and continue all work there**

---

### Task 2: Reduce judge screen orb size

**Files:**
- Modify: `src/iron_verdict/static/css/components.css`

**Step 1: Find `.display-orb--sm`**

Search for `.display-orb--sm` in `components.css`. Currently:

```css
.display-orb--sm {
    width: 60px;
    height: 60px;
}
```

**Step 2: Update to 44px**

```css
.display-orb--sm {
    width: 44px;
    height: 44px;
}
```

**Step 3: Verify visually**

Open the app, go to the judge screen, cast a non-white vote and lock in. Confirm the result orbs are visibly smaller than before and fit comfortably in 3 columns on a narrow phone screen.

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "fix: reduce judge screen result orb size to 44px"
```

---

### Task 3: Reduce judge screen reason text size

**Files:**
- Modify: `src/iron_verdict/static/css/components.css`

**Step 1: Locate `.display-orb-reason`**

Find the existing rule in `components.css`:

```css
.display-orb-reason {
    font-size: 2.16rem;
    color: rgba(255, 255, 255, 0.85);
    text-align: center;
    max-width: 240px;
    line-height: 1.3;
    font-weight: 500;
}
```

Leave this rule untouched (it's correct for the display screen).

**Step 2: Add scoped override below it**

```css
.judge-results-orbs .display-orb-reason {
    font-size: 0.7rem;
    max-width: 80px;
}
```

**Step 3: Verify visually**

On the judge screen, cast yellow votes for all three judges with reason "Supporting contact on legs". Confirm all three orbs with text fit on screen without wrapping or overflow. Also confirm the display screen reason text is unchanged (still large).

**Step 4: Commit**

```bash
git add src/iron_verdict/static/css/components.css
git commit -m "fix: reduce judge screen reason text to 0.7rem"
```

---

### Task 4: Copy design doc and finish

**Files:**
- Already exists: `docs/plans/2026-02-26-judge-screen-orb-size-design.md`

**Step 1: Verify design doc is present in worktree**

```bash
ls docs/plans/
```

If missing, copy from main branch:

```bash
git checkout main -- docs/plans/2026-02-26-judge-screen-orb-size-design.md
git add docs/plans/2026-02-26-judge-screen-orb-size-design.md
git commit -m "docs: add design doc for judge screen orb size fix"
```

**Step 2: Invoke finishing-a-development-branch skill**
