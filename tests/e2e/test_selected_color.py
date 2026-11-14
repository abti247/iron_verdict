"""The selected colour is clearly marked on the judge screen (issue #258).

Feedback from a competition: a judge could not tell that White was selected.
The old mark — a white border on the light White button — was practically
invisible. A selected colour field now has a thick green border (the colour of
the LOCK IN button) and reads "✓ SELECTED" (German "✓ AUSGEWÄHLT"), so the
selection is visible without telling colours apart. The German text is pinned
in ``tests/js/i18n.test.js``. Only White stays on the
colour step after the tap; the other colours switch to the reason step, so
those are checked via "Back".
"""

from playwright.sync_api import expect

GREEN = "rgb(34, 197, 94)"  # --success, the LOCK IN button's colour


def _mark(page, color):
    return page.locator(f".vote-btn.vote-{color}").get_by_test_id("vote-selected-mark")


def test_selected_white_is_marked_and_mark_moves_and_clears(competition):
    """Side judge taps White → "✓ SELECTED" and a thick green border on White,
    on no other field; Red, then Back → only Red is marked; White again, locked,
    head judge clicks Next Lift → no field is marked."""
    head = competition.create_session_and_join_head()
    left = competition.join_as("left_judge")

    white = left.locator(".vote-btn.vote-white")
    expect(_mark(left, "white")).not_to_be_visible()

    white.click()
    expect(_mark(left, "white")).to_be_visible()
    expect(_mark(left, "white")).to_have_text("✓ SELECTED")
    expect(white).to_have_css("border-top-color", GREEN)
    expect(white).to_have_css("border-top-width", "4px")
    for color in ("red", "blue", "yellow"):
        expect(_mark(left, color)).not_to_be_visible()

    left.locator(".vote-btn.vote-red").click()
    left.get_by_role("button", name="back").click()
    expect(_mark(left, "red")).to_be_visible()
    expect(_mark(left, "white")).not_to_be_visible()
    expect(white).not_to_have_css("border-top-color", GREEN)

    competition.vote_and_lock(left, "white")
    expect(_mark(left, "white")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(white).to_be_enabled()
    expect(left.get_by_test_id("vote-selected-mark")).to_have_count(4)
    for color in ("white", "red", "blue", "yellow"):
        expect(_mark(left, color)).not_to_be_visible()
    expect(white).not_to_have_css("border-top-color", GREEN)

