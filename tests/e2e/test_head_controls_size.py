"""Head judge control buttons are large enough to hit in portrait (issue #257).

Feedback from a competition (Android tablet, Chrome, portrait): Start Timer,
Reset Timer, Next Lift and End Session were only about 45 px high. They now
have a 72 px minimum height on every screen size and stay lower than the
colour fields, so the vote keeps visual priority.
"""

import pytest
from playwright.sync_api import expect

BUTTONS = ("Start Timer", "Reset Timer", "Next Lift", "End Session")
MIN_HEIGHT = 72


@pytest.mark.parametrize("size", [(800, 1280), (390, 844)], ids=["tablet", "phone"])
def test_head_controls_at_least_72px_and_lower_than_color_fields(competition, size):
    """Head judge in portrait (800×1280 tablet, 390×844 phone) → each of the four
    control buttons is at least 72 px high and lower than every colour field."""
    head = competition.create_session_and_join_head()
    head.set_viewport_size({"width": size[0], "height": size[1]})

    color_fields = head.locator(".vote-btn")
    expect(color_fields).to_have_count(4)
    smallest_color_field = min(
        color_fields.nth(i).bounding_box()["height"] for i in range(4)
    )

    for name in BUTTONS:
        button = head.get_by_role("button", name=name)
        expect(button).to_be_visible()
        height = button.bounding_box()["height"]
        assert height >= MIN_HEIGHT, f"{name}: {height} px < {MIN_HEIGHT} px"
        assert height < smallest_color_field, (
            f"{name}: {height} px not lower than colour field ({smallest_color_field} px)"
        )
