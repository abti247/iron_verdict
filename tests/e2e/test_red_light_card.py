"""Red light with card — a light is only white or red; under a red light a
rectangle in the judge's card colour (red, blue, yellow) shows why (#115).

Applies to the display and to the judges' result panel. The vote buttons keep
their four colours. The rectangle always has its place in the layout, so the
lights never move when it appears.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

DISPLAY_WRAPS = ".display-full .display-orb-wrap"
JUDGE_WRAPS = ".judge-results-orbs .judge-result-orb-wrap"
POSITIONS = ("left", "center", "right")


def vote(page, color, with_reason=False):
    page.locator(f".vote-btn.vote-{color}").click()
    if with_reason:
        page.locator(".reason-item").first.click()
    page.locator(".lock-btn").click()
    page.locator(".locked-status").wait_for(state="visible")


def expect_lights(page, wraps, expected):
    """expected: {position: (light, card or None, reason shown)}."""
    for i, pos in enumerate(POSITIONS):
        light, card, reason_shown = expected[pos]
        wrap = page.locator(wraps).nth(i)
        orb = wrap.locator(".display-orb")
        expect(orb).to_have_class(re.compile(rf"\b{light}\b"))
        for other in {"white", "red", "blue", "yellow"} - {light}:
            expect(orb).not_to_have_class(re.compile(rf"\b{other}\b"))
        card_el = wrap.locator(".display-orb-card")
        if card:
            expect(card_el).to_have_class(re.compile(rf"\b{card}\b"))
            expect(card_el).to_be_visible()
        else:
            expect(card_el).to_be_hidden()
        reason = wrap.locator(".display-orb-reason")
        if reason_shown:
            expect(reason).to_be_visible()
        else:
            expect(reason).to_be_hidden()


def orb_tops(page, wraps):
    return [page.locator(wraps).nth(i).locator(".display-orb").bounding_box()["y"] for i in range(3)]


def test_lights_are_white_or_red_with_card_below(competition):
    """Lift 1: chief referee white, left blue with a reason, right yellow
    without one → display and every judge's result panel show white, red, red;
    a blue card under the left light (reason below it) and a yellow card under
    the right one; nothing under the white light. The lights stay where they
    were before the result.

    Lift 2: the chief referee turns "Show reasons on display" off; left votes
    red with a reason → red light with red card on the display, no reason text.
    """
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    tops_before = orb_tops(display, DISPLAY_WRAPS)

    # -- Lift 1: white / blue + reason / yellow -------------------------------
    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "yellow")

    expected = {
        "left": ("red", "blue", True),
        "center": ("white", None, False),
        "right": ("red", "yellow", False),
    }
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")
    expect_lights(display, DISPLAY_WRAPS, expected)
    assert orb_tops(display, DISPLAY_WRAPS) == tops_before
    for judge in (head, left, right):
        expect_lights(judge, JUDGE_WRAPS, expected)

    # Vote buttons keep their four colours
    for color in ("white", "red", "blue", "yellow"):
        expect(left.locator(f".vote-btn.vote-{color}")).to_be_visible()

    # -- Lift 2: reasons off, red + reason ------------------------------------
    head.get_by_test_id("show-explanations-checkbox").uncheck()
    head.get_by_role("button", name="Next Lift").click()
    vote(head, "white")
    vote(left, "red", with_reason=True)
    vote(right, "white")

    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect_lights(display, DISPLAY_WRAPS, {
        "left": ("red", "red", False),
        "center": ("white", None, False),
        "right": ("white", None, False),
    })


def test_light_and_card_survive_display_reload_and_reconnect(competition):
    """The display reloads after a result → same lights, card and reason.

    Then its connection drops; the next lift is voted while it is offline
    (left yellow with a reason). After the connection returns, the display
    shows the new result: red light, yellow card, reason.
    """
    head, left, right = competition.join_all_judges()
    display = join_with_network_switch(competition, "display")

    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "white")
    expected = {
        "left": ("red", "blue", True),
        "center": ("white", None, False),
        "right": ("white", None, False),
    }
    expect_lights(display, DISPLAY_WRAPS, expected)

    # -- Reload ----------------------------------------------------------------
    display.reload()
    display.locator(".display-full").wait_for(state="visible")
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect_lights(display, DISPLAY_WRAPS, expected)

    # -- Connection loss: next lift voted while offline -------------------------
    cut_network(display, conn_dot=".display-tag .conn-dot")
    head.get_by_role("button", name="Next Lift").click()
    vote(head, "white")
    vote(left, "yellow", with_reason=True)
    vote(right, "red")
    restore_network(display)

    expect(display.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")
    expect_lights(display, DISPLAY_WRAPS, {
        "left": ("red", "yellow", True),
        "center": ("white", None, False),
        "right": ("red", "red", False),
    })
