"""Display resilience — a display that joins mid-competition shows the result,
and a display or judge that missed messages while offline shows the server's
state after it reconnects or reloads (#232)."""

import re
import time

from playwright.sync_api import expect

from iron_verdict.main import session_manager
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

DISPLAY_DOT = ".display-tag .conn-dot"
CONNECTED = re.compile(r"\bconnected\b")
EXPIRED = re.compile(r"\bexpired\b")
LIT = re.compile(r"\b(white|red)\b")


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


def expect_waiting_for_next_lift(display):
    """Lights empty, no verdict, timer at 60 and not running."""
    orbs = display.locator(".display-lights .display-orb")
    expect(orbs).to_have_count(3)
    for i in range(3):
        expect(orbs.nth(i)).not_to_have_class(LIT)
    expect(display.locator(".verdict-stamp")).to_be_hidden()
    expect(display.locator(".display-status")).to_have_text("Waiting for judges...")
    expect(display.locator(".display-timer-big")).to_have_text("60")
    expect(display.locator(".display-timer-big")).not_to_have_class(EXPIRED)


def test_display_that_missed_next_lift_and_timer_reset_shows_server_state(competition):
    """The display shows a result and goes offline; meanwhile the head judge
    presses Next Lift. Back online it shows empty lights, no verdict and "60"
    — not the previous lifter's lights. Then the head judge starts the timer,
    the display goes offline again and the head judge resets the timer: back
    online, the display's countdown stops at "60" instead of counting on."""
    head, left, right = competition.join_all_judges()
    display = join_with_network_switch(competition, "display")

    competition.vote_and_lock(head, "red")
    competition.vote_and_lock(left, "red")
    competition.vote_and_lock(right, "white")
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")

    cut_network(display, conn_dot=DISPLAY_DOT)
    head.get_by_role("button", name="Next Lift").click()
    expect(head.locator(".locked-status")).to_be_hidden()
    # Still the last known state while offline; the connection dot shows the drop.
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")

    restore_network(display)
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)
    expect_waiting_for_next_lift(display)

    head.get_by_role("button", name="Start Timer").click()
    expect(display.locator(".display-timer-big")).to_have_text(re.compile(r"^(59|58|57)$"))
    cut_network(display, conn_dot=DISPLAY_DOT)
    head.get_by_role("button", name="Reset Timer").click()
    expect(head.locator(".judge-timer")).to_have_text("60")

    restore_network(display)
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)
    expect_waiting_for_next_lift(display)

    # A reload shows the same state.
    display.reload()
    display.locator(".display-full").wait_for(state="visible")
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)
    expect_waiting_for_next_lift(display)


def test_expired_timer_shows_expired_after_reload(competition, run_on_server):
    """The head judge starts the timer and it runs out. After a reload the
    display and a judge show "0", marked expired — not "60"."""
    head, left, _right = competition.join_all_judges()
    display = competition.join_as("display")
    head.get_by_role("button", name="Start Timer").click()
    expect(display.locator(".display-timer-big")).to_have_text(re.compile(r"^(59|58|57)$"))

    code = competition.session_code

    async def run_out_timer():
        # The server keeps only the start time; 61 s ago means it ran out.
        session_manager.sessions[code]["timer_started_at"] = time.time() - 61

    run_on_server(run_out_timer())

    for page, timer, root in (
        (display, ".display-timer-big", ".display-full"),
        (left, ".judge-timer", ".judge-wrap"),
    ):
        page.reload()
        page.locator(root).wait_for(state="visible")
        expect(page.locator(timer)).to_have_text("0")
        expect(page.locator(timer)).to_have_class(EXPIRED)
