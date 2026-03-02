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
