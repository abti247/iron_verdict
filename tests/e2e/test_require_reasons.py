"""requireReasons = true — dedicated tests for the lock-blocking mechanism.

test_competition_flow.py exercises requireReasons as part of a full lift cycle.
These tests focus on the gate behaviour in isolation: red/blue votes blocked,
white votes always allowed through immediately.
"""

from playwright.sync_api import expect


def test_lock_blocked_without_reason(competition):
    """requireReasons enabled → red vote blocks lock-in until a reason is selected."""
    head, left, _right = competition.join_all_judges()

    # Enable both settings (showExplanations makes reason items visible in judge UI)
    head.locator('[x-model="showExplanations"]').check()
    head.locator('[x-model="requireReasons"]').check()

    left.locator('.vote-btn.vote-red').click()

    # Lock button must be absent before a reason is chosen
    expect(left.locator('.lock-btn')).not_to_be_visible()

    left.locator('.reason-item').first.click()

    # Lock button must appear after a reason is chosen
    expect(left.locator('.lock-btn')).to_be_visible()

    left.locator('.lock-btn').click()
    expect(left.locator('.locked-status')).to_be_visible()


def test_white_vote_locks_without_reason_when_require_reasons_enabled(competition):
    """requireReasons enabled → white vote locks in immediately without needing a reason."""
    head, left, _right = competition.join_all_judges()

    head.locator('[x-model="showExplanations"]').check()
    head.locator('[x-model="requireReasons"]').check()

    left.locator('.vote-btn.vote-white').click()

    # White vote: lock button must be immediately visible (no reason required)
    expect(left.locator('.lock-btn')).to_be_visible()

    left.locator('.lock-btn').click()
    expect(left.locator('.locked-status')).to_be_visible()
