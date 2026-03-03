# Require All Three Votes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Results display only when all 3 judges have locked a vote, regardless of connection status.

**Architecture:** Single-line change in `session.py` — remove the `if j["connected"]` filter from the `all_locked` check so all three judge positions must have `locked=True`. A disconnected judge whose vote is already locked still counts; a disconnected judge who never voted blocks results indefinitely.

**Tech Stack:** Python, pytest, asyncio

---

### Task 1: Write failing test for disconnected-judge-blocks-results

**Files:**
- Modify: `tests/test_session.py` (append after last test)

**Step 1: Append this test to `tests/test_session.py`**

```python
async def test_disconnected_judge_without_vote_blocks_results():
    """Results must not show if a judge disconnected before voting (IPF rule)."""
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    # Simulate right judge disconnecting without voting
    manager.sessions[code]["judges"]["right"]["connected"] = False

    await manager.lock_vote(code, "left", "white")
    result = await manager.lock_vote(code, "center", "white")

    assert result["all_locked"] is False
    assert manager.sessions[code]["state"] != "showing_results"
```

**Step 2: Run the test to verify it fails**

```bash
pytest tests/test_session.py::test_disconnected_judge_without_vote_blocks_results -v
```

Expected: **FAIL** — current code returns `all_locked=True` because it only checks connected judges.

**Step 3: Commit the failing test**

```bash
git add tests/test_session.py
git commit -m "test: add failing test for IPF 3-vote requirement"
```

---

### Task 2: Implement the fix

**Files:**
- Modify: `src/iron_verdict/session.py:146-148`

**Step 1: Open `src/iron_verdict/session.py` and find lines 146-148**

Current code:
```python
all_locked = all(
    j["locked"] for j in session["judges"].values() if j["connected"]
)
```

**Step 2: Remove the `if j["connected"]` filter**

New code:
```python
all_locked = all(
    j["locked"] for j in session["judges"].values()
)
```

**Step 3: Run the new test to verify it passes**

```bash
pytest tests/test_session.py::test_disconnected_judge_without_vote_blocks_results -v
```

Expected: **PASS**

**Step 4: Run the full unit test suite to confirm no regressions**

```bash
pytest tests/test_session.py tests/test_main.py -v
```

Expected: all tests pass. (All existing `all_locked` tests already connect all 3 judges before locking, so they are unaffected.)

**Step 5: Commit**

```bash
git add src/iron_verdict/session.py
git commit -m "fix: require all 3 judge votes before showing results (IPF compliance)"
```

---

### Task 3: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` — add under `[Unreleased] > Fixed`

```
- Results are no longer displayed until all three judges have locked in a vote, matching IPF simultaneous-lights rule
```

**Step 1: Add the entry**

Open `CHANGELOG.md`, find the `[Unreleased]` section and `Fixed` subsection, add the line above.

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog entry for IPF 3-vote enforcement"
```

---

### Task 4: (Optional) Run E2E tests

If you want full confidence:

```bash
pytest tests/e2e/ -v
```

These tests use all 3 judges and are unaffected by this change. If they pass, you're done.
