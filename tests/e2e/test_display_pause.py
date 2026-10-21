"""Display pause (#163).

From the settings panel of any display (gear or "S") an operator starts a
pause for the whole session: by minutes (the displays count down) or until a
time of day (the displays show the end time), optionally with the next lift
type. Every display of the session, the stream overlay included, shows the
pause big in the middle instead of timer, lights, verdict and VPortal lifter.
It ends on every display when the head judge starts the timer (see
test_competition_flow.py), when its time is up (decided by the server;
backend tests) or with "End break" on any display; afterwards the displays
show the real state again. A past time is rejected. The pause survives
reload and connection loss.
"""

import datetime
import re
import time
from zoneinfo import ZoneInfo

import httpx
from playwright.sync_api import expect

from iron_verdict.main import session_manager
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_display_overlay import open_overlay
from tests.e2e.test_vportal_integration import _connect_and_open_display

ROOT = ".display-full"


def pause_block(page):
    return page.get_by_test_id("display-pause")


def open_panel(page):
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()


def start_pause(page, minutes=None, until=None, next_lift=None, panel=True):
    if panel:
        open_panel(page)
    if minutes is not None:
        page.get_by_test_id("pause-mode-minutes").click()
        page.get_by_test_id("pause-minutes").fill(str(minutes))
    else:
        page.get_by_test_id("pause-mode-until").click()
        page.get_by_test_id("pause-until").fill(until)
    if next_lift:
        page.get_by_test_id("pause-next-lift").select_option(next_lift)
    page.get_by_test_id("pause-start").click()


def end_pause(page):
    open_panel(page)
    page.get_by_test_id("pause-end").click()


def expect_paused(page, time_text=None):
    expect(pause_block(page)).to_be_visible()
    if time_text:
        expect(page.get_by_test_id("display-pause-time")).to_have_text(time_text)
    expect(page.locator(f"{ROOT} .layout-block--timer")).to_be_hidden()
    expect(page.locator(f"{ROOT} .display-lights")).to_be_hidden()
    expect(page.locator(f"{ROOT} .display-verdict-inline")).to_be_hidden()


def expect_not_paused(page):
    expect(pause_block(page)).to_be_hidden()
    expect(page.locator(f"{ROOT} .layout-block--timer")).to_be_visible()
    expect(page.locator(f"{ROOT} .display-lights")).to_be_visible()


def vote_white(page):
    page.locator(".vote-btn.vote-white").click()
    page.locator(".lock-btn").click()
    page.locator(".locked-status").wait_for(state="visible")


def join_display(ctx, competition):
    """Join the session as display in a context of its own (time zone, clock)."""
    page = ctx.new_page()
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(ROOT).wait_for(state="visible")
    return page


def test_minutes_pause_shows_on_every_display_and_end_brings_back_the_result(competition):
    """Three judges give a good lift; two displays show it. Display A starts a
    10-minute pause with "next: bench press": both displays show the countdown
    and the next lift in the middle instead of timer, lights and verdict, and
    A's panel closes. Display B ends the pause: both show the (not yet advanced) good
    lift again."""
    head, left, right = competition.join_all_judges()
    display_a = competition.join_as("display")
    display_b = join_display(competition.new_context(), competition)
    for judge in (head, left, right):
        vote_white(judge)
    for display in (display_a, display_b):
        expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\bvalid\b"))

    start_pause(display_a, minutes=10, next_lift="bench")

    for display in (display_a, display_b):
        expect_paused(display)
        expect(display.get_by_test_id("display-pause-time")).to_have_text(re.compile(r"^(10:00|9:5\d) left$"))
        expect(display.get_by_test_id("display-pause-next")).to_have_text("Next: Bench Press")
    expect(display_a.locator(".display-settings-panel")).to_be_hidden()
    box, size = pause_block(display_a).bounding_box(), display_a.viewport_size
    assert abs(box["x"] + box["width"] / 2 - size["width"] / 2) <= 2
    assert abs(box["y"] + box["height"] / 2 - size["height"] / 2) <= 2
    # The judges' screens are unchanged.
    expect(head.locator(".judge-wrap")).to_be_visible()

    end_pause(display_b)
    for display in (display_a, display_b):
        expect_not_paused(display)
        expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\bvalid\b"))
    assert session_manager.sessions[competition.session_code]["pause"] is None


def midday_timezone():
    """A fixed-offset time zone where it is about noon now, so "in 30 minutes"
    and "5 minutes ago" are on the same day whenever the test runs."""
    offset = 12 - datetime.datetime.now(datetime.timezone.utc).hour  # -11 .. 12
    return f"Etc/GMT{-offset:+d}"  # Etc/GMT-2 is UTC+2


def test_until_time_shows_the_end_and_rejects_a_past_time(competition):
    """A display (time zone where it is about noon) enters a time 5 minutes
    ago: rejected with "Time is in the past". A time 30 minutes from now shows
    "until HH:MM", and the end lies 30 minutes ahead."""
    competition.create_session_and_join_head()
    tz = midday_timezone()
    display = join_display(competition.new_context(timezone_id=tz), competition)

    local_now = datetime.datetime.now(ZoneInfo(tz))
    past = (local_now - datetime.timedelta(minutes=5)).strftime("%H:%M")
    future = (local_now + datetime.timedelta(minutes=30)).strftime("%H:%M")

    start_pause(display, until=past)
    expect(display.get_by_test_id("pause-error")).to_have_text("Time is in the past")
    expect(pause_block(display)).to_be_hidden()
    assert session_manager.sessions[competition.session_code]["pause"] is None

    start_pause(display, until=future, panel=False)
    expect_paused(display, f"until {future}")
    end_at = session_manager.sessions[competition.session_code]["pause"]["end_at"]
    assert 28 * 60 < end_at - time.time() <= 30 * 60


def test_countdown_follows_the_server_clock_on_a_display_with_a_wrong_clock(competition):
    """A display whose clock is two hours fast shows the same countdown as
    the server (about 10:00 for a 10-minute pause), not 0:00."""
    competition.create_session_and_join_head()
    ctx = competition.new_context()
    ctx.add_init_script("""(() => {
        const realNow = Date.now;
        Date.now = () => realNow() + 2 * 60 * 60 * 1000;
    })();""")
    display = join_display(ctx, competition)

    start_pause(display, minutes=10)

    expect(display.get_by_test_id("display-pause-time")).to_have_text(re.compile(r"^(10:00|9:5\d) left$"))


def test_pause_is_right_after_connection_loss_and_reload(competition):
    """Display A loses its connection during a pause: its panel says so and
    cannot send. Meanwhile display B ends the pause; when A is back online it
    shows no pause (state from the server, not from before the drop). B
    starts a new pause; A reloads and shows it again."""
    competition.create_session_and_join_head()
    display_a = join_with_network_switch(competition, "display")
    display_b = competition.join_as("display")
    start_pause(display_b, minutes=10)
    expect_paused(display_a)

    cut_network(display_a, conn_dot=".display-tag .conn-dot")
    open_panel(display_a)
    expect(display_a.get_by_test_id("pause-offline")).to_be_visible()
    expect(display_a.get_by_test_id("pause-end")).to_be_disabled()
    display_a.keyboard.press("Escape")

    end_pause(display_b)
    expect_not_paused(display_b)
    expect_paused(display_a)  # still the last known state, connection dot shows the drop

    restore_network(display_a)
    expect(display_a.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))
    expect_not_paused(display_a)

    start_pause(display_b, minutes=7, next_lift="deadlift")
    expect_paused(display_a)
    display_a.reload()
    display_a.locator(ROOT).wait_for(state="visible")
    expect_paused(display_a)
    expect(display_a.get_by_test_id("display-pause-next")).to_have_text("Next: Deadlift")


def test_pause_hides_the_vportal_lifter_and_brings_it_back(page, server_url, fake_vportal_url):
    """A VPortal display shows the current lifter. During a pause the lifter
    and attempt are hidden while VPortal polling continues: VPortal drops the
    current attempt during the pause, so after the pause no lifter shows
    (not the one from before the pause); when VPortal has one again it shows."""
    _connect_and_open_display(page, server_url, fake_vportal_url)
    lifter = page.locator(".vportal-corner-left")
    expect(lifter).to_be_visible(timeout=10000)

    start_pause(page, minutes=10)
    expect_paused(page)
    expect(lifter).to_be_hidden()
    expect(page.locator(".vportal-corner-right")).to_be_hidden()

    httpx.post(f"http://{fake_vportal_url}/_control/clear_attempt")
    page.wait_for_function("Alpine.store('vportal').displayAttempt === null", timeout=10000)

    end_pause(page)
    expect_not_paused(page)
    expect(lifter).to_be_hidden()
    httpx.post(f"http://{fake_vportal_url}/_control/restore_attempt")
    expect(lifter).to_be_visible(timeout=10000)
    expect(lifter).to_contain_text("MARIA SCHNEIDER", ignore_case=True)
    httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_stream_overlay_shows_the_pause_in_the_middle(competition):
    """A hall display starts a pause: the stream overlay hides lights, timer
    and verdict and shows the pause in the middle, like every display, without
    a dialog."""
    competition.create_session_and_join_head()
    hall = competition.join_as("display")
    overlay, dialogs = open_overlay(competition)

    start_pause(hall, minutes=10)

    expect_paused(overlay)
    box, size = pause_block(overlay).bounding_box(), overlay.viewport_size
    assert abs(box["x"] + box["width"] / 2 - size["width"] / 2) <= 2
    assert dialogs == []
