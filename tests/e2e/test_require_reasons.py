"""requireReasons = true — judges who vote non-white must select a reason before locking in."""

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
