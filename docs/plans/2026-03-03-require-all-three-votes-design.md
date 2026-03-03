# Design: Require All Three Votes Before Showing Results

**Date:** 2026-03-03
**Status:** Approved

## Problem

IPF rules require that all three judges' lights illuminate simultaneously. The current implementation shows results when all *connected* judges have locked in, meaning two votes from a three-judge panel can trigger the display if the third judge is disconnected.

## Rule Reference

> They must be wired or electronic/wireless in such a way that they light up together and not separately when activated by the three referees.
> — IPF Technical Rules

## Decision

Always require all three judge positions to have `locked=True` before showing results. No exceptions for practice or testing.

## Change

In `session.py`, `lock_vote()`:

```python
# Before
all_locked = all(j["locked"] for j in session["judges"].values() if j["connected"])

# After
all_locked = all(j["locked"] for j in session["judges"].values())
```

## Behavior

| Scenario | Result |
|---|---|
| All 3 judges lock | Results shown |
| 3rd judge disconnects before voting, other 2 lock | Wait indefinitely |
| 3rd judge disconnects after locking, other 2 lock | Results shown (`locked=True` persists in state) |
| Fewer than 3 judges (testing) | Wait indefinitely |

## No Other Changes Needed

- `show_results` payload already filters votes by `j["locked"]` (not `j["connected"]`) — correct
- Rejoin replay logic already replays locked votes to reconnecting judges — correct
- Timer freeze logic is unaffected

## Tests

- Update any existing test that asserts results show with fewer than 3 votes
- Add: judge disconnects before voting → other 2 lock → assert results do NOT show
