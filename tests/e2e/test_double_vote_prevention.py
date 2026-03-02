"""Double-vote prevention — locked votes must survive refresh and block re-voting."""

from playwright.sync_api import expect


def test_locked_vote_persists_after_refresh(competition):
    """Lock vote → refresh → vote still locked."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "red")
    left.reload()

    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".locked-status")).to_contain_text("RED")


def test_cannot_vote_twice(competition):
    """After locking, vote buttons are disabled and lock button is hidden."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "white")

    for color in ("white", "red", "blue", "yellow"):
        expect(left.locator(f".vote-btn.vote-{color}")).to_be_disabled()

    expect(left.locator(".lock-btn")).not_to_be_visible()


def test_vote_clears_after_next_lift(competition):
    """Full cycle → next lift → all judges can vote fresh."""
    head, left, right = competition.join_all_judges()

    competition.vote_all_white()

    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()

    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()
