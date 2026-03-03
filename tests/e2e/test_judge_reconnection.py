"""Judge reconnection — refresh/navigate-away must not break the session."""

from playwright.sync_api import expect


def test_reconnect_before_voting(competition):
    """Judge refreshes before voting → returns to judge screen, can vote."""
    head, left, right = competition.join_all_judges()

    left.reload()
    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_enabled()

    # Verify full flow still works
    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()


def test_reconnect_after_voting(competition):
    """Judge refreshes after locking vote → vote restored, cannot re-vote."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "white")
    left.reload()

    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_disabled()


def test_reconnect_via_role_select(competition):
    """Judge clicks session code → role-select → re-selects role → session continues."""
    head, left, right = competition.join_all_judges()

    left.locator(".code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    left.locator(".role-btn", has_text="Left").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()


def test_all_judges_reconnect_simultaneously(competition):
    """All 3 judges refresh at the same time → all reconnect, session continues."""
    head, left, right = competition.join_all_judges()

    head.reload()
    left.reload()
    right.reload()

    for p in (head, left, right):
        expect(p.locator(".judge-wrap")).to_be_visible()

    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()


def test_timer_frozen_after_all_votes_locked_and_rejoin(competition):
    """After all votes lock (timer running), a judge who leaves and rejoins sees
    the frozen timer, their locked vote, and the results — no countdown resumes."""
    from playwright.sync_api import expect
    import time as _time

    head, left, right = competition.join_all_judges()

    head.get_by_role("button", name="Start Timer").click()
    # Wait for timer to start ticking (it won't show "60" anymore)
    expect(head.locator(".judge-timer")).not_to_have_text("60")

    competition.vote_all_white()

    # Results should be visible on left judge's screen
    expect(left.locator(".head-section").last).to_be_visible()

    # Capture the frozen timer value on left's screen
    frozen_display = left.locator(".judge-timer").text_content()
    assert frozen_display != "60", "Expected timer to have ticked before votes locked"

    # Left judge navigates back to role selection
    left.locator(".code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    # Left judge rejoins
    left.locator(".role-btn", has_text="Left").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    # Timer must not be counting down: wait 1.5s and verify it hasn't changed
    timer_val_before = left.locator(".judge-timer").text_content()
    _time.sleep(1.5)
    timer_val_after = left.locator(".judge-timer").text_content()
    assert timer_val_before == timer_val_after, (
        f"Timer should be frozen but changed from {timer_val_before} to {timer_val_after}"
    )

    # Vote must still be locked
    expect(left.locator(".locked-status")).to_be_visible()

    # Results must be visible
    expect(left.locator(".head-section").last).to_be_visible()
