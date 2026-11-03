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

Its size and place (#190): 26 / 15 / 6 vmin in the middle by default; in the
layout editor's "Break preview" it is moved, scaled and hidden like the other
blocks, stored per device with the layout and in its code, and never larger
than the screen.
"""

import base64
import datetime
import json
import re
import time
from zoneinfo import ZoneInfo

import httpx
import pytest
from playwright.sync_api import expect

from iron_verdict.main import session_manager
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_display_contrast import contrast_of, turn_contrast_on
from tests.e2e.test_display_layout import german_reload, open_editor, save, stored_layout
from tests.e2e.test_display_overlay import open_overlay, wait_joined
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


# ===== Pause size and zoom (#190) =====
# Default 26 / 15 / 6 vmin (title / time / "Next: …") in the middle; the layout
# editor's pause preview edits it like the other blocks, stored per device.

SIZES = (26, 15, 6)
PAUSE_LINES = (".display-pause-title", ".display-pause-time", ".display-pause-next")


def pause_font_sizes(page):
    return page.evaluate(
        """(sels) => sels.map((s) => parseFloat(getComputedStyle(
            document.querySelector(`.display-full ${s}`)).fontSize))""",
        list(PAUSE_LINES),
    )


def expect_pause_size(page, zoom=1):
    vmin = min(page.viewport_size["width"], page.viewport_size["height"]) / 100
    sizes = pause_font_sizes(page)
    for size, units in zip(sizes, SIZES):
        assert abs(size - units * vmin * zoom) <= 0.5, (sizes, zoom)


def pause_center(page):
    box = pause_block(page).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def assert_pause_centred(page):
    size = page.viewport_size
    x, y = pause_center(page)
    assert abs(x - size["width"] / 2) <= 2 and abs(y - size["height"] / 2) <= 2, (x, y)


def drag_by(page, locator, dx, dy):
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=4)
    page.mouse.up()


def open_pause_preview(page):
    open_editor(page)
    page.get_by_test_id("layout-pause-preview").click()
    expect(page.get_by_test_id("layout-pause-preview")).to_have_attribute("aria-pressed", "true")
    expect(pause_block(page)).to_be_visible()


def scale_handle(page):
    return page.get_by_test_id("layout-pause-scale-handle")


def test_pause_is_bigger_by_default_on_display_and_overlay(competition):
    """Without a saved layout the pause shows at 26 / 15 / 6 vmin (title,
    time, next lift) in the middle of the hall display and of the stream
    overlay."""
    competition.create_session_and_join_head()
    hall = competition.join_as("display")
    overlay, _ = open_overlay(competition)

    start_pause(hall, minutes=10, next_lift="bench")

    for page in (hall, overlay):
        expect_paused(page)
        expect_pause_size(page)
        assert_pause_centred(page)


def test_pause_is_edited_like_a_block_in_the_editor_preview_and_survives_save_and_reload(competition):
    """In the layout editor, "Break preview" shows the pause with sample text
    instead of the other blocks. Its corner scales it from the middle; dragged,
    it moves. Cancel drops both; Save keeps them (the other blocks stay where
    they were) and puts them into the layout code; after a reload a real pause
    shows at that size and place. "Reset to default" and Save bring back the
    default size in the middle."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    size = display.viewport_size
    timer = display.locator(f"{ROOT} .layout-block--timer")
    timer_box = timer.bounding_box()

    open_pause_preview(display)
    expect(display.get_by_test_id("display-pause-time")).to_have_text("10:00 left")
    expect(display.get_by_test_id("display-pause-next")).to_have_text("Next: Bench Press")
    expect(pause_block(display).locator(".layout-frame-label")).to_contain_text("Break · sample")
    expect(display.get_by_test_id("layout-hint")).to_contain_text("Drag the break to move it")
    # Transparent, not removed (still measured when the layout is created).
    for block_id in ("timer", "lights", "verdict"):
        expect(display.locator(f'{ROOT} [data-layout-block="{block_id}"]')).to_have_css("opacity", "0")
    expect_pause_size(display)

    drag_by(display, scale_handle(display), 140, 0)
    title_size = pause_font_sizes(display)[0]
    zoom = round(title_size / (26 * min(size.values()) / 100) / 0.05) * 0.05
    assert 1.3 <= zoom <= 1.6, zoom
    expect_pause_size(display, zoom)
    assert_pause_centred(display)
    drag_by(display, display.locator(f"{ROOT} .display-pause-title"), 200, 100)
    x, y = pause_center(display)
    assert abs(x - (size["width"] / 2 + 200)) <= size["width"] / 100
    assert abs(y - (size["height"] / 2 + 100)) <= size["height"] / 100

    display.get_by_test_id("layout-cancel").click()
    assert stored_layout(display) is None
    open_pause_preview(display)
    expect_pause_size(display)
    assert_pause_centred(display)

    # Downwards this time: the pause grows both ways, so the handle moves by
    # half the height change.
    half_height = pause_block(display).bounding_box()["height"] / 2
    drag_by(display, scale_handle(display), 0, (zoom - 1) * half_height)
    expect_pause_size(display, zoom)
    assert_pause_centred(display)
    drag_by(display, display.locator(f"{ROOT} .display-pause-title"), 200, 100)
    moved = pause_center(display)
    display.get_by_test_id("layout-code-toggle").click()
    code = display.get_by_test_id("layout-code-export").input_value()
    pause = decode_code(code)["blocks"]["pause"]
    assert pause["s"] == zoom and pause["x"] > 50 and pause["y"] > 50 and pause["hidden"] is False
    save(display)
    assert stored_layout(display)["blocks"]["pause"] == pause
    expect(pause_block(display)).to_be_hidden()
    expect(timer).to_be_visible()
    expect(timer).to_have_css("opacity", "1")
    new_box = timer.bounding_box()
    assert abs(new_box["x"] - timer_box["x"]) <= 2 and abs(new_box["y"] - timer_box["y"]) <= 2

    display.reload()
    display.locator(ROOT).wait_for(state="visible")
    start_pause(display, minutes=10)
    expect_paused(display)
    expect_pause_size(display, zoom)
    x, y = pause_center(display)
    assert abs(x - moved[0]) <= 2 and abs(y - moved[1]) <= 2

    open_editor(display)
    display.get_by_test_id("layout-reset").click()
    save(display)
    assert stored_layout(display) is None
    expect_paused(display)
    expect_pause_size(display)
    assert_pause_centred(display)


def test_hidden_pause_shows_nothing_on_this_display_only(competition):
    """Display A (German, the longest toolbar hint) hides the pause in the
    editor's preview (faded there, so it can be shown again; its hide button
    is not covered by the toolbar) and saves. During a pause A shows nothing (no pause,
    no timer, no lights), display B shows the pause as usual. Shown again on
    A, the pause is back."""
    competition.create_session_and_join_head()
    display_a = competition.join_as("display")
    display_b = competition.join_as("display")
    german_reload(display_a)
    display_a.locator(ROOT).wait_for(state="visible")

    open_pause_preview(display_a)
    display_a.get_by_test_id("layout-hide-pause").click()
    expect(display_a.locator(f"{ROOT} .display-pause-title")).to_have_css("opacity", "0.3")
    save(display_a)
    assert stored_layout(display_a)["blocks"]["pause"]["hidden"] is True

    start_pause(display_b, minutes=10)
    expect_paused(display_b)
    expect(pause_block(display_a)).to_be_hidden()
    expect(display_a.locator(f"{ROOT} .layout-block--timer")).to_be_hidden()
    expect(display_a.locator(f"{ROOT} .display-lights")).to_be_hidden()

    open_editor(display_a)
    display_a.get_by_test_id("layout-pause-preview").click()
    display_a.get_by_test_id("layout-hide-pause").click()
    save(display_a)
    expect_paused(display_a)
    assert_pause_centred(display_a)


def layout_code_with_pause_zoom(zoom):
    blocks = {
        "timer": {"x": 50, "y": 5, "s": 1, "hidden": False},
        "lights": {"x": 50, "y": 35, "s": 1, "hidden": False, "gap": 1},
        "cards": {"gap": 0.1, "hidden": False},
        "verdict": {"x": 50, "y": 80, "s": 1, "hidden": False},
        "lifter": {"x": 2, "y": 88, "s": 1, "hidden": False},
        "attempt": {"x": 98, "y": 88, "s": 1, "hidden": False},
        "pause": {"x": 50, "y": 50, "s": zoom, "hidden": False},
    }
    raw = json.dumps({"v": 1, "blocks": blocks}).encode()
    return "IV1." + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_code(code):
    body = code.removeprefix("IV1.")
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def expect_whole_pause_on_screen(page, spread=0):
    """Pause block (plus the overlay panel's spread) and every line inside the viewport."""
    size = page.viewport_size
    blocks = [(pause_block(page), spread)] + [(page.locator(f"{ROOT} {s}"), 0) for s in PAUSE_LINES]
    for locator, pad in blocks:
        box = locator.bounding_box()
        assert box["x"] - pad >= 0 and box["y"] - pad >= 0, box
        assert box["x"] + box["width"] + pad <= size["width"], (box, size)
        assert box["y"] + box["height"] + pad <= size["height"], (box, size)


@pytest.mark.parametrize("size", [(1920, 1080), (1080, 1920)], ids=["16x9", "portrait"])
def test_longest_line_stays_on_screen_at_maximum_zoom(competition, size):
    """German hall display in contrast mode (bold text) and German stream
    overlay, each with the pause in the middle at maximum zoom (3; display:
    layout code pasted in the editor, overlay: code in its URL), on 16:9 and
    portrait: the pause with the longest line ("Weiter mit: Bankdrücken")
    stays whole and centred on screen, and the contrast mode still shows it in
    high-contrast text."""
    viewport = {"width": size[0], "height": size[1]}
    competition.create_session_and_join_head()
    display = join_display(competition.new_context(viewport=viewport), competition)
    german_reload(display)
    display.locator(ROOT).wait_for(state="visible")
    turn_contrast_on(display)

    code = layout_code_with_pause_zoom(3)
    open_editor(display)
    display.get_by_test_id("layout-code-toggle").click()
    display.get_by_test_id("layout-code-import").fill(code)
    display.get_by_test_id("layout-code-apply").click()
    save(display)
    assert stored_layout(display)["blocks"]["pause"]["s"] == 3

    overlay, _ = open_overlay(competition, layout_code=code)
    german_reload(overlay)
    wait_joined(overlay)
    overlay.set_viewport_size(viewport)

    start_pause(display, minutes=10, next_lift="bench", panel=True)
    for page in (display, overlay):
        expect_paused(page)
        expect(page.get_by_test_id("display-pause-next")).to_have_text("Weiter mit: Bankdrücken")
        spread = pause_font_sizes(page)[2] / 6 if page is overlay else 0
        expect_whole_pause_on_screen(page, spread)
        assert_pause_centred(page)
    # At maximum zoom the pause is still bigger than the default on both formats.
    vmin = min(size) / 100
    assert pause_font_sizes(display)[0] > 26 * vmin * 1.1
    next_line = display.get_by_test_id("display-pause-next")
    assert contrast_of(next_line) >= 7
    assert next_line.evaluate("el => getComputedStyle(el).fontWeight") == "700"
