"""Display resilience — a display that joins mid-competition shows the result."""

from playwright.sync_api import expect


def test_display_joins_mid_competition(competition):
    """Display joins after votes already started → shows correct state."""
    head, left, right = competition.join_all_judges()

    # Two judges vote before display joins
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "white")

    display = competition.join_as("display")

    # Third judge votes → results shown on display
    competition.vote_and_lock(right, "white")

    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
