"""requireReasons = true — dedicated tests for the lock-blocking mechanism.

test_competition_flow.py exercises requireReasons as part of a full lift cycle.
These tests focus on the gate behaviour in isolation: red/blue votes blocked,
white votes always allowed through immediately.
"""

from playwright.sync_api import expect


def _wait_until_left_requires_reasons(left):
    """Wait for the settings_update broadcast to reach the left judge, seen
    through the UI: a red vote shows the reason list and no lock button.
    Then step back so the test starts from the colour choice."""
    left.locator('.vote-btn.vote-red').click()
    expect(left.locator('.reason-item').first).to_be_visible()
    expect(left.locator('.lock-btn')).not_to_be_visible()
    left.locator('.back-btn').click()
    expect(left.locator('.vote-grid')).to_be_visible()


def test_lock_blocked_without_reason(competition):
    """requireReasons enabled → red vote blocks lock-in until a reason is selected."""
    head, left, _right = competition.join_all_judges()

    # Enable both settings (showExplanations makes reason items visible in judge UI)
    head.get_by_test_id("show-explanations-checkbox").check()
    head.get_by_test_id("require-reasons-checkbox").check()

    _wait_until_left_requires_reasons(left)

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

    head.get_by_test_id("show-explanations-checkbox").check()
    head.get_by_test_id("require-reasons-checkbox").check()

    _wait_until_left_requires_reasons(left)

    left.locator('.vote-btn.vote-white').click()

    # White vote: lock button must be immediately visible (no reason required)
    expect(left.locator('.lock-btn')).to_be_visible()

    left.locator('.lock-btn').click()
    expect(left.locator('.locked-status')).to_be_visible()
