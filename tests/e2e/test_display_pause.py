"""Display pause (#163).

From the settings panel of any display (gear or "S") an operator starts a
pause for the whole session: by minutes (the displays count down) or until a
time of day (the displays show the end time), optionally with the next lift
type. Every display of the session shows the pause instead of timer, lights,
verdict and VPortal lifter. It ends on every display when the head judge
starts the timer, when its time is up (decided by the server) or with "End
break" on any display; afterwards the displays show the real state again.
A past time is rejected. The pause survives reload, connection loss and a
server restart. It is a layout block of its own; the editor has a lift view
and a pause view, and the stream overlay hides the pause block by default.
"""

import asyncio
import datetime
import re
import tempfile
import time
from zoneinfo import ZoneInfo

import httpx
from playwright.sync_api import expect

from iron_verdict import main as main_module
from iron_verdict.main import session_manager
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_display_layout import block_pos, drag, open_editor, save
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


def server_loop():
    """The event loop of the in-process server, taken from a running pause end."""
    return next(iter(main_module._pause_end_tasks.values())).get_loop()


def test_minutes_pause_shows_on_every_display_and_end_brings_back_the_result(competition):
    """Three judges give a good lift; two displays show it. Display A starts a
    10-minute pause with "next: bench press": both displays show the countdown
    and the next lift instead of timer, lights and verdict, and A's panel
    closes. Display B ends the pause: both show the (not yet advanced) good
    lift again."""
    head, left, right = competition.join_all_judges()
    display_a = competition.join_as("display")
    ctx = competition.new_context()
    display_b = ctx.new_page()
    display_b.goto(competition.url)
    display_b.get_by_test_id("join-code-input").fill(competition.session_code)
    display_b.get_by_role("button", name="Join Session").click()
    display_b.locator(".role-btn", has_text="Display Screen").click()
    display_b.locator(ROOT).wait_for(state="visible")
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
    # The judges' screens are unchanged.
    expect(head.locator(".judge-wrap")).to_be_visible()

    end_pause(display_b)
    for display in (display_a, display_b):
        expect_not_paused(display)
        expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\bvalid\b"))
    assert session_manager.sessions[competition.session_code]["pause"] is None


def test_head_judge_timer_start_ends_the_pause(competition):
    """A pause is running; the head judge starts the timer: the pause
    disappears at once and the display shows the running timer."""
    head = competition.create_session_and_join_head()
    display = competition.join_as("display")
    start_pause(display, minutes=5)
    expect_paused(display)

    head.get_by_role("button", name="Start Timer").click()

    expect_not_paused(display)
    expect(display.locator(".display-timer-big")).to_have_text(re.compile(r"^(60|59|58)$"))


def midday_timezone():
    """A fixed-offset time zone where it is about noon now, so "in 30 minutes"
    and "5 minutes ago" are on the same day whenever the test runs."""
    offset = 12 - datetime.datetime.now(datetime.timezone.utc).hour  # -11 .. 12
    return f"Etc/GMT{-offset:+d}"  # Etc/GMT-2 is UTC+2


def test_until_time_uses_server_clock_and_rejects_a_past_time(competition):
    """A display whose clock is two hours fast starts a pause until 30 minutes
    from now (its time zone): the server computes the end with its own clock,
    so the display shows "until HH:MM" and the end lies 30 minutes ahead. A
    time 5 minutes ago is rejected with "Time is in the past"."""
    competition.create_session_and_join_head()
    tz = midday_timezone()
    ctx = competition.new_context(timezone_id=tz)
    ctx.add_init_script("""(() => {
        const realNow = Date.now;
        Date.now = () => realNow() + 2 * 60 * 60 * 1000;
    })();""")
    display = ctx.new_page()
    display.goto(competition.url)
    display.get_by_test_id("join-code-input").fill(competition.session_code)
    display.get_by_role("button", name="Join Session").click()
    display.locator(".role-btn", has_text="Display Screen").click()
    display.locator(ROOT).wait_for(state="visible")

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
    """A display whose clock is an hour fast shows the same countdown as the
    server (about 10:00 for a 10-minute pause), not 0:00."""
    competition.create_session_and_join_head()
    ctx = competition.new_context()
    ctx.add_init_script("""(() => {
        const realNow = Date.now;
        Date.now = () => realNow() + 60 * 60 * 1000;
    })();""")
    display = ctx.new_page()
    display.goto(competition.url)
    display.get_by_test_id("join-code-input").fill(competition.session_code)
    display.get_by_role("button", name="Join Session").click()
    display.locator(".role-btn", has_text="Display Screen").click()
    display.locator(ROOT).wait_for(state="visible")

    start_pause(display, minutes=10)

    expect_paused(display)
    expect(display.get_by_test_id("display-pause-time")).to_have_text(re.compile(r"^(10:00|9:5\d) left$"))


def test_pause_ends_by_itself_when_its_time_is_up(competition):
    """The server ends a pause when its time is up and every display drops it.
    The test moves the end of a running 1-minute pause 1 s ahead (as if the
    minute had passed) and lets the server re-arm its end."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    start_pause(display, minutes=1)
    expect_paused(display)

    code = competition.session_code
    session_manager.sessions[code]["pause"]["end_at"] = time.time() + 1
    server_loop().call_soon_threadsafe(main_module.schedule_pause_end, code)

    expect_not_paused(display)
    assert session_manager.sessions[code]["pause"] is None


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


def test_pause_survives_a_server_restart(competition):
    """A pause is running when the server restarts (snapshot written, sessions
    reloaded from it, every connection dropped): the display reconnects and
    still shows the pause, and its end is armed again."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    start_pause(display, minutes=10, next_lift="squat")
    expect_paused(display)
    code = competition.session_code
    loop = server_loop()

    async def restart(path):
        conns = main_module.connection_manager
        for session_code in list(conns.active_connections):
            await conns.broadcast_to_session(session_code, {"type": "server_restarting"})
        session_manager.save_snapshot(path)
        for task in list(main_module._pause_end_tasks.values()):
            task.cancel()
        session_manager.sessions.clear()
        for session_code, roles in list(conns.active_connections.items()):
            for role, ws in list(roles.items()):
                await conns.remove_connection(session_code, role)
                await ws.close(code=1012)
        session_manager.load_snapshot(path)
        main_module.restore_pause_timers()

    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run_coroutine_threadsafe(restart(f"{tmp}/sessions.json"), loop).result(timeout=5)

    expect(display.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))
    expect_paused(display)
    expect(display.get_by_test_id("display-pause-next")).to_have_text("Next: Squat")
    assert code in main_module._pause_end_tasks


def test_pause_hides_the_vportal_lifter_and_brings_it_back(page, server_url, fake_vportal_url):
    """A VPortal display shows the current lifter. During a pause the lifter
    and attempt are hidden while VPortal polling continues; after the pause
    the lifter shows again."""
    _connect_and_open_display(page, server_url, fake_vportal_url)
    lifter = page.locator(".vportal-corner-left")
    expect(lifter).to_be_visible(timeout=10000)

    start_pause(page, minutes=10)
    expect_paused(page)
    expect(lifter).to_be_hidden()
    expect(page.locator(".vportal-corner-right")).to_be_hidden()

    end_pause(page)
    expect(lifter).to_be_visible()
    expect(lifter).to_contain_text("MARIA SCHNEIDER", ignore_case=True)
    httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_layout_editor_has_a_pause_view_and_places_the_pause_block(competition):
    """The editor starts in the lift view (pause block invisible). Its view
    switch shows the pause block (a sample) without the lift blocks; the
    pause block is dragged and saved. A started pause then shows there."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    display.set_viewport_size({"width": 1920, "height": 1080})
    open_editor(display)
    expect(pause_block(display)).to_have_css("visibility", "hidden")
    expect(display.locator(f"{ROOT} .display-lights")).to_have_css("visibility", "visible")

    display.get_by_test_id("layout-view-toggle").click()
    expect(display.get_by_test_id("layout-view-toggle")).to_have_text("View: break")
    expect(pause_block(display)).to_have_css("visibility", "visible")
    expect(pause_block(display)).to_have_class(re.compile(r"\blayout-sample\b"))
    expect(display.get_by_test_id("display-pause-time")).to_have_text("10:00 left")
    expect(display.locator(f"{ROOT} .display-lights")).to_have_css("visibility", "hidden")
    x0, y0, _, _ = block_pos(display, "pause")
    drag(display, pause_block(display), 0, 216)  # 20 % of 1080 px
    save(display)

    start_pause(display, minutes=3)
    expect_paused(display)
    x1, y1, _, _ = block_pos(display, "pause")
    assert abs(y1 - (y0 + 20)) <= 1.5
    assert abs(x1 - x0) <= 1.5


def test_editor_opens_in_the_pause_view_while_a_pause_runs(competition):
    """During a pause the editor starts with the pause view (what the hall
    sees now); its blocks show and can be switched to the lift view."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    start_pause(display, minutes=3)
    expect_paused(display)
    open_editor(display)
    expect(display.get_by_test_id("layout-view-toggle")).to_have_text("View: break")
    expect(pause_block(display)).to_have_css("visibility", "visible")
    expect(pause_block(display)).not_to_have_class(re.compile(r"\blayout-sample\b"))
    display.get_by_test_id("layout-view-toggle").click()
    expect(display.locator(f"{ROOT} .display-lights")).to_be_visible()
    expect(display.locator(f"{ROOT} .display-lights")).to_have_css("visibility", "visible")


def test_stream_overlay_hides_the_pause_by_default_and_editor_shows_it(competition):
    """A hall display starts a pause. The stream overlay hides lights, timer
    and verdict like every display, but its pause block is hidden by default
    (the stream shows other content). In the overlay's editor the pause view
    offers it faded with "Show"; shown and saved, the overlay shows the pause."""
    competition.create_session_and_join_head()
    hall = competition.join_as("display")
    overlay, dialogs = open_overlay(competition)

    start_pause(hall, minutes=10)
    expect_paused(hall)
    expect(pause_block(overlay)).to_be_hidden()
    expect(overlay.locator(f"{ROOT} .display-lights")).to_be_hidden()

    overlay.keyboard.press("s")
    overlay.get_by_test_id("display-layout-edit").click()
    expect(overlay.get_by_test_id("layout-view-toggle")).to_have_text("View: break")
    expect(pause_block(overlay)).to_have_class(re.compile(r"\blayout-hidden\b"))
    overlay.get_by_test_id("layout-hide-pause").click()
    expect(overlay.get_by_test_id("layout-hide-pause")).to_have_text("Hide")
    overlay.get_by_test_id("layout-save").click()

    expect(pause_block(overlay)).to_be_visible()
    expect(overlay.get_by_test_id("display-pause-time")).to_have_text(re.compile(r"left$"))
    assert dialogs == []
