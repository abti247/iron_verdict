"""Display resilience — display must recover from refresh and support multiples."""

import re
from playwright.sync_api import expect


def test_display_reconnects_after_refresh(competition):
    """Display refreshes → reconnects and shows current state."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    display.reload()
    expect(display.locator(".display-full")).to_be_visible()

    # Verify the display still works after refresh — run full vote
    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")


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


def test_multiple_displays_receive_results(competition):
    """Two displays join → both show identical results after all votes."""
    head, left, right = competition.join_all_judges()
    display1 = competition.join_as("display")

    # Second display — manual flow since "display" key gets reused in pages dict
    ctx = competition.browser.new_context()
    competition.contexts.append(ctx)
    display2 = ctx.new_page()
    display2.on("dialog", lambda d: d.accept())
    display2.goto(competition.url)
    display2.locator('[x-model="joinCode"]').fill(competition.session_code)
    display2.get_by_role("button", name="Join Session").click()
    display2.locator(".role-wrap").wait_for(state="visible")
    display2.locator(".role-btn", has_text="Display Screen").click()
    display2.locator(".display-full").wait_for(state="visible")

    competition.vote_all_white()

    for display in (display1, display2):
        expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
        for orb in display.locator(".display-orb").all():
            expect(orb).to_have_class(re.compile(r"\bwhite\b"))
