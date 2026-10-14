"""Competition flow — happy path: full lift cycles, reasons, timer."""

import re
from playwright.sync_api import expect


def test_full_lift_cycle(competition):
    """Create → 3 judges join → all vote white → results → next lift → vote again
    (one blue vote: red light with blue card on the display) → end session."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    # -- Round 1: all white --------------------------------------------------
    competition.vote_all_white()

    # Results visible on judge screens
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".head-section").last).to_be_visible()

    # Display shows 3 white orbs and "Good Lift"
    for orb in display.locator(".display-orb").all():
        expect(orb).to_have_class(re.compile(r"\bwhite\b"))
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\bvalid\b"))

    # -- Next Lift ------------------------------------------------------------
    head.get_by_role("button", name="Next Lift").click()

    # All judges can vote again (lock button hidden means not yet voted)
    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()

    # Display resets — verdict parent uses visibility:hidden (not display:none)
    expect(display.locator(".display-verdict-inline")).to_have_css(
        "visibility", "hidden"
    )

    # -- Round 2: mixed votes ------------------------------------------------
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "blue")
    competition.vote_and_lock(right, "white")

    # 2 white + 1 blue = "Good Lift" (majority white)
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    # Blue vote: red light with a blue card below; no card under white lights
    left_wrap, center_wrap = display.locator(".display-full .display-orb-wrap").all()[:2]
    expect(left_wrap.locator(".display-orb")).to_have_class(re.compile(r"\bred\b"))
    expect(left_wrap.locator(".display-orb-card")).to_have_class(re.compile(r"\bblue\b"))
    expect(left_wrap.locator(".display-orb-card")).to_be_visible()
    expect(center_wrap.locator(".display-orb-card")).to_be_hidden()

    # -- End Session ---------------------------------------------------------
    head.get_by_role("button", name="End Session").click()
    for p in (head, left, right, display):
        expect(
            p.get_by_role("button", name="Create New Session")
        ).to_be_visible(timeout=5000)


def test_lift_cycle_with_required_reasons(competition):
    """Head judge enables require_reasons → judges must pick reason for non-white."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    # "Show reasons on display" is on by default; enable required reasons
    expect(head.get_by_test_id("show-explanations-checkbox")).to_be_checked()
    head.get_by_test_id("require-reasons-checkbox").check()

    # White vote locks without reason
    competition.vote_and_lock(head, "white")

    # Red vote requires reason
    left.locator(".vote-btn.vote-red").click()
    # Lock button should NOT be visible until reason selected
    expect(left.locator(".lock-btn")).not_to_be_visible()
    left.locator(".reason-item").first.click()
    left.locator(".lock-btn").click()
    left.locator(".locked-status").wait_for(state="visible")

    competition.vote_and_lock(right, "white")

    # Display shows reason for the red vote (scope to .display-full to avoid
    # matching the hidden judge-results panel which also has .display-orb-reason)
    expect(
        display.locator(".display-full .display-orb-reason").first
    ).to_be_visible()


def test_timer_flow(competition):
    """Head judge starts/resets 60s timer, visible on all screens."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    head.get_by_role("button", name="Start Timer").click()

    # Timer visible and counting on all screens
    for p in (head, left, right):
        expect(p.locator(".judge-timer")).not_to_have_text("60")
    expect(display.locator(".display-timer-big")).not_to_have_text("")

    # Reset
    head.get_by_role("button", name="Reset Timer").click()
    expect(head.locator(".judge-timer")).to_have_text("60")
