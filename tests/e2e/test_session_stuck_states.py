"""Session stuck states — session must never get stuck during competition."""

import re
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


def test_judge_disconnect_mid_vote_blocks_results_and_next_lift_continues(competition):
    """Head judge votes, the left judge disconnects without voting, the right
    judge votes → results must not appear (IPF rule) → Next Lift still resets
    the head judge, who can vote again."""
    head, left, right = competition.join_all_judges()
    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    competition.vote_and_lock(head, "white")

    # Left judge closes browser without casting a vote
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    # The server marks the judge disconnected before it reports it, so the vote
    # below is counted against a disconnected non-voter
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    competition.vote_and_lock(right, "white")

    # A result would be sent right after the vote confirmation, so in practice it
    # would arrive before the timer start that the head judge sends afterwards.
    head.get_by_role("button", name="Start Timer").click()
    expect(right.locator(".judge-timer")).not_to_have_text("60")

    expect(head.locator(".head-section").last).not_to_be_visible()
    expect(right.locator(".head-section").last).not_to_be_visible()

    head.get_by_role("button", name="Next Lift").click()
    expect(head.locator(".locked-status")).not_to_be_visible()
    expect(head.locator(".vote-btn.vote-white")).to_be_enabled()


def test_judge_disconnected_after_locking_still_counts_in_result(competition):
    """The left judge locks white, then loses the connection (shown as disconnected
    at the head judge); centre white and right red lock → the display shows three
    lights and "Good Lift", and so does the head judge's result view (#229)."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    competition.vote_and_lock(left, "white")

    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "red")

    expected = (r"\bwhite\b", r"\bwhite\b", r"\bred\b")
    display_orbs = display.locator(".display-full .display-orb-wrap .display-orb")
    expect(display_orbs).to_have_count(3)
    for orb, cls in zip(display_orbs.all(), expected):
        expect(orb).to_have_class(re.compile(cls))
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    expect(head.locator(".head-section").last).to_be_visible()
    head_orbs = head.locator(".judge-result-orb-wrap .display-orb")
    expect(head_orbs).to_have_count(3)
    for orb, cls in zip(head_orbs.all(), expected):
        expect(orb).to_have_class(re.compile(cls))


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
        for color in ("white", "red", "blue", "yellow"):
            expect(p.locator(f".vote-btn.vote-{color}")).to_be_enabled()
