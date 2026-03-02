"""Session stuck states — session must never get stuck during competition."""

from playwright.sync_api import expect


def test_next_lift_when_not_all_voted(competition):
    """Only 2/3 vote → head judge clicks Next Lift (with confirm) → all reset."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "white")

    # Next Lift shows confirm dialog (results not shown yet) — auto-accepted
    head.get_by_role("button", name="Next Lift").click()

    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()


def test_continue_after_judge_disconnect_mid_vote(competition):
    """Judge disconnects after partial voting → remaining judges still work."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(head, "white")

    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    competition.vote_and_lock(right, "white")

    head.get_by_role("button", name="Next Lift").click()
    expect(head.locator(".locked-status")).not_to_be_visible()
    expect(head.locator(".vote-btn.vote-white")).to_be_enabled()


def test_next_lift_resets_all_state(competition):
    """Full cycle → Next Lift → voteLocked false, selectedVote cleared, resultsShown false."""
    head, left, right = competition.join_all_judges()

    competition.vote_all_white()

    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()

    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-grid")).to_be_visible()
        expect(p.locator(".vote-btn.selected")).not_to_be_visible()
