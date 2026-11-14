"""The selected colour is clearly marked on the judge screen (issue #258).

Feedback from a competition: a judge could not tell that White was selected.
The old mark — a white border on the light White button — was practically
invisible. A selected colour field now has a thick green border (the colour of
the LOCK IN button). Only White stays on the colour step after the tap; the
other colours switch to the reason step, so those are checked via "Back".
"""

from playwright.sync_api import expect

GREEN = "rgb(34, 197, 94)"  # --success, the LOCK IN button's colour
COLORS = ("white", "red", "blue", "yellow")


def _expect_only_marked(page, marked):
    """Exactly the colour field *marked* has the 4 px green border (none if None)."""
    for color in COLORS:
        field = page.locator(f".vote-btn.vote-{color}")
        if color == marked:
            expect(field).to_have_css("border-top-color", GREEN)
            expect(field).to_have_css("border-top-width", "4px")
        else:
            expect(field).not_to_have_css("border-top-color", GREEN)


def test_selected_white_is_marked_and_mark_moves_and_clears(competition):
    """Side judge taps White → thick green border on White, on no other field;
    Red, then Back → only Red is marked; White again, locked, head judge clicks
    Next Lift → no field is marked."""
    head = competition.create_session_and_join_head()
    left = competition.join_as("left_judge")
    _expect_only_marked(left, None)

    left.locator(".vote-btn.vote-white").click()
    _expect_only_marked(left, "white")

    left.locator(".vote-btn.vote-red").click()
    left.get_by_role("button", name="back").click()
    _expect_only_marked(left, "red")

    competition.vote_and_lock(left, "white")
    _expect_only_marked(left, "white")

    head.get_by_role("button", name="Next Lift").click()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_enabled()
    _expect_only_marked(left, None)
