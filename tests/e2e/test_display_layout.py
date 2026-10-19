"""Display layout editor (#106).

From the display settings (gear or "S") the operator opens an edit mode: the
blocks of the display (timer, lights, cards + reasons under the lights,
verdict, lifter info, attempt info) get a frame and can be dragged (mouse and
touch) and scaled at a handle, snapping to 1 % of the screen. The cards block
follows the lights and is only dragged up or down (its gap to the lights).
Every block can be hidden. "Save" stores the layout on this device, "Cancel"
drops the changes, "Reset" brings back the default. A layout can be copied to
another device as a code. Without a saved layout the display looks as before.
While editing, the display keeps showing votes, timer and VPortal data.
"""

import json
import re

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_vportal_integration import _connect_and_open_display

LAYOUT_KEY = "iron-verdict:display-layout"
ROOT = ".display-full"
CUSTOM = re.compile(r"\bdisplay-layout-custom\b")
EDITING = re.compile(r"\bdisplay-layout-editing\b")


def block(page, block_id):
    return page.locator(f'{ROOT} [data-layout-block="{block_id}"]')


def block_pos(page, block_id):
    """Top-left corner of a block in percent of the display."""
    return page.evaluate(
        """(id) => {
            const root = document.querySelector('.display-full').getBoundingClientRect();
            const r = document.querySelector(`.display-full [data-layout-block="${id}"]`).getBoundingClientRect();
            return [ (r.left - root.left) / root.width * 100, (r.top - root.top) / root.height * 100,
                     r.width, r.height ];
        }""",
        block_id,
    )


def stored_layout(page):
    raw = page.evaluate(f"localStorage.getItem('{LAYOUT_KEY}')")
    return json.loads(raw) if raw else None


def open_editor(page):
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()
    page.get_by_test_id("display-layout-edit").click()
    expect(page.locator(ROOT)).to_have_class(EDITING)
    expect(page.get_by_test_id("layout-toolbar")).to_be_visible()


def save(page):
    page.get_by_test_id("layout-save").click()
    expect(page.locator(ROOT)).not_to_have_class(EDITING)


def drag(page, locator, dx, dy, steps=4):
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=steps)
    page.mouse.up()


def drag_lights(page, dx, dy):
    """The lights block is grabbed at a light (its lower part is the cards frame)."""
    drag(page, block(page, "lights").locator(".display-orb").first, dx, dy)


def open_display(page, server_url, size=(1920, 1080)):
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto(server_url + "/")
    page.get_by_test_id("session-name-input").fill("Layout Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(ROOT).wait_for(state="visible")


def vote(page, color, with_reason=False):
    page.locator(f".vote-btn.vote-{color}").click()
    if with_reason:
        page.locator(".reason-item").first.click()
    page.locator(".lock-btn").click()
    page.locator(".locked-status").wait_for(state="visible")


def test_without_saved_layout_display_is_unchanged(page, server_url):
    """A display that never used the editor keeps the default flow layout: no
    custom positions, no frames, no zoom slider any more."""
    open_display(page, server_url)
    expect(page.locator(ROOT)).not_to_have_class(CUSTOM)
    expect(page.locator(ROOT)).not_to_have_class(EDITING)
    for block_id in ("timer", "lights", "verdict"):
        assert "left:" not in (block(page, block_id).get_attribute("style") or "")
    page.locator(".display-settings-gear").click()
    expect(page.get_by_test_id("display-layout-edit")).to_be_visible()
    expect(page.locator(".display-settings-slider")).to_have_count(0)
    assert stored_layout(page) is None


def test_entering_edit_mode_does_not_move_blocks(page, server_url):
    """Opening the editor and grabbing a block without moving it keeps every
    block exactly where the default layout put it."""
    open_display(page, server_url)
    before = {b: block_pos(page, b)[:2] for b in ("timer", "lights", "verdict")}
    open_editor(page)
    drag(page, block(page, "verdict"), 0, 0)
    expect(page.locator(ROOT)).to_have_class(CUSTOM)
    for b, (x, y) in before.items():
        nx, ny = block_pos(page, b)[:2]
        assert abs(nx - x) < 0.6 and abs(ny - y) < 0.6, (b, (x, y), (nx, ny))


def test_move_and_scale_then_save_survives_reload(page, server_url):
    """Drag the timer 10 % right and 5 % down, scale the lights up at their
    handle, save → positions snap to 1 %, are stored, and come back after a
    reload from the first frame on (no jump from the default layout)."""
    open_display(page, server_url)
    open_editor(page)
    timer_x, timer_y = block_pos(page, "timer")[:2]
    drag(page, block(page, "timer"), 192, 54)
    lights_w = block_pos(page, "lights")[2]
    drag(page, block(page, "lights").locator(".layout-scale-handle"), lights_w * 0.5, 0)
    save(page)

    layout = stored_layout(page)
    assert layout["blocks"]["timer"]["x"] == round(timer_x + 10)
    assert layout["blocks"]["timer"]["y"] == round(timer_y + 5)
    assert 1.4 <= layout["blocks"]["lights"]["s"] <= 1.6
    expect(page.locator(ROOT)).to_have_class(CUSTOM)
    x, y = block_pos(page, "timer")[:2]
    assert abs(x - layout["blocks"]["timer"]["x"]) < 0.1 and abs(y - layout["blocks"]["timer"]["y"]) < 0.1

    # Record every frame after the reload: the display must never be visible
    # without the saved layout.
    page.add_init_script("""
        window.__ivFrames = [];
        const tick = () => {
            const el = document.querySelector('.display-full');
            if (el && getComputedStyle(el).display !== 'none') {
                window.__ivFrames.push(el.classList.contains('display-layout-custom'));
            }
            requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    """)
    page.reload()
    page.locator(ROOT).wait_for(state="visible")
    expect(page.locator(ROOT)).to_have_class(CUSTOM)
    expect(page.locator(ROOT)).not_to_have_class(EDITING)
    frames = page.evaluate("window.__ivFrames")
    assert frames and all(frames), frames
    x, y = block_pos(page, "timer")[:2]
    assert abs(x - layout["blocks"]["timer"]["x"]) < 0.1 and abs(y - layout["blocks"]["timer"]["y"]) < 0.1
    expect(block(page, "lights")).to_have_attribute("style", re.compile(r"--display-zoom: 1\.[456]"))


def test_touch_drag_moves_block(page, server_url):
    """A block is dragged with a finger (real touch input) just like with the
    mouse."""
    open_display(page, server_url)
    open_editor(page)
    x0, y0 = block_pos(page, "verdict")[:2]
    box = block(page, "verdict").bounding_box()
    sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": sx, "y": sy}]})
    for i in range(1, 5):
        cdp.send("Input.dispatchTouchEvent",
                 {"type": "touchMove", "touchPoints": [{"x": sx - 96 * i, "y": sy - 27 * i}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    save(page)
    layout = stored_layout(page)
    assert layout["blocks"]["verdict"]["x"] == round(x0 - 20)
    assert layout["blocks"]["verdict"]["y"] == round(y0 - 10)


def test_cancel_discards_changes(page, server_url):
    """Changes are dropped with "Cancel": the saved layout and the positions
    on screen stay as before."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, block(page, "timer"), 192, 0)
    save(page)
    saved = stored_layout(page)
    x_saved = block_pos(page, "timer")[0]

    open_editor(page)
    drag(page, block(page, "timer"), 384, 108)
    page.get_by_test_id("layout-hide-timer").click()
    page.get_by_test_id("layout-cancel").click()
    expect(page.locator(ROOT)).not_to_have_class(EDITING)
    assert stored_layout(page) == saved
    assert abs(block_pos(page, "timer")[0] - x_saved) < 0.1
    expect(block(page, "timer")).to_be_visible()


def test_reset_restores_default_layout(page, server_url):
    """"Reset" in the editor shows the default layout; after "Save" no layout
    is stored and the display is the default flow layout again, also after a
    reload."""
    open_display(page, server_url)
    default_timer = block_pos(page, "timer")[:2]
    open_editor(page)
    drag(page, block(page, "timer"), 300, 200)
    save(page)
    assert stored_layout(page) is not None

    open_editor(page)
    page.get_by_test_id("layout-reset").click()
    expect(page.locator(ROOT)).not_to_have_class(CUSTOM)
    save(page)
    assert stored_layout(page) is None
    page.reload()
    page.locator(ROOT).wait_for(state="visible")
    expect(page.locator(ROOT)).not_to_have_class(CUSTOM)
    x, y = block_pos(page, "timer")[:2]
    assert abs(x - default_timer[0]) < 0.1 and abs(y - default_timer[1]) < 0.1


def test_hidden_blocks_stay_hidden_but_show_faded_in_editor(competition):
    """Hide the timer and the cards + reasons → after saving and a reload the
    timer is gone and a red light shows no card or reason; in the editor both
    are shown faded so they can be switched on again."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    open_editor(display)
    display.get_by_test_id("layout-hide-timer").click()
    display.get_by_test_id("layout-hide-cards").click()
    expect(display.get_by_test_id("layout-hide-timer")).to_have_attribute("aria-pressed", "true")
    expect(block(display, "timer")).to_be_visible()
    save(display)
    display.reload()
    display.locator(ROOT).wait_for(state="visible")
    expect(block(display, "timer")).to_be_hidden()

    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "white")
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    wrap = display.locator(f"{ROOT} .display-orb-wrap").first
    expect(wrap.locator(".display-orb")).to_have_class(re.compile(r"\bred\b"))
    expect(wrap.locator(".display-orb-card")).to_be_hidden()
    expect(wrap.locator(".display-orb-reason")).to_be_hidden()

    open_editor(display)
    expect(block(display, "timer")).to_be_visible()
    expect(wrap.locator(".display-orb-card")).to_be_visible()
    display.get_by_test_id("layout-hide-cards").click()
    save(display)
    expect(wrap.locator(".display-orb-card")).to_be_visible()
    expect(wrap.locator(".display-orb-reason")).to_be_visible()
    expect(block(display, "timer")).to_be_hidden()


def test_cards_follow_lights_and_only_change_their_gap(competition):
    """Dragging the cards block down (and sideways) only increases its gap to
    the lights; the card stays centred under its light, also after the lights
    are moved."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    display.set_viewport_size({"width": 1920, "height": 1080})
    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "white")
    wrap = display.locator(f"{ROOT} .display-orb-wrap").first
    orb, card = wrap.locator(".display-orb"), wrap.locator(".display-orb-card")
    expect(card).to_be_visible()

    def gap_and_offset():
        o, c = orb.bounding_box(), card.bounding_box()
        return c["y"] - (o["y"] + o["height"]), (c["x"] + c["width"] / 2) - (o["x"] + o["width"] / 2)

    gap_before, _ = gap_and_offset()
    open_editor(display)
    drag(display, block(display, "cards"), 300, 100)
    drag_lights(display, -200, -50)
    save(display)
    gap_after, offset = gap_and_offset()
    assert gap_after > gap_before + 60, (gap_before, gap_after)
    assert abs(offset) < 1, offset
    assert stored_layout(display)["blocks"]["cards"]["gap"] > 0


def test_layout_code_copies_layout_to_another_device(competition, page, server_url):
    """Display A exports its layout as a code; display B pastes it, sees the
    layout and saves it. A wrong code shows an error and changes nothing."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, block(page, "timer"), 192, 108)
    page.get_by_test_id("layout-hide-verdict").click()
    page.get_by_test_id("layout-code-toggle").click()
    code = page.get_by_test_id("layout-code-export").input_value()
    assert code.startswith("IV1.")
    save(page)
    layout_a = stored_layout(page)

    competition.create_session_and_join_head()
    other = competition.join_as("display")
    open_editor(other)
    other.get_by_test_id("layout-code-toggle").click()
    other.get_by_test_id("layout-code-import").fill("not a code")
    other.get_by_test_id("layout-code-apply").click()
    expect(other.get_by_test_id("layout-code-error")).to_be_visible()
    expect(other.locator(ROOT)).not_to_have_class(CUSTOM)

    other.get_by_test_id("layout-code-import").fill(code)
    other.get_by_test_id("layout-code-apply").click()
    expect(other.get_by_test_id("layout-code-error")).to_be_hidden()
    expect(other.locator(ROOT)).to_have_class(CUSTOM)
    save(other)
    assert stored_layout(other) == layout_a
    expect(block(other, "verdict")).to_be_hidden()


def test_layout_survives_connection_loss(competition):
    """Saved layout → the display's connection drops and comes back (the next
    lift is voted while offline) → the layout is still active and the result
    arrives in the moved lights."""
    head, left, right = competition.join_all_judges()
    display = join_with_network_switch(competition, "display")
    open_editor(display)
    drag_lights(display, 0, 150)
    save(display)
    saved = stored_layout(display)
    lights_y = block_pos(display, "lights")[1]

    cut_network(display, conn_dot=".display-tag .conn-dot")
    vote(head, "white")
    vote(left, "red")
    vote(right, "white")
    restore_network(display)
    expect(display.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"), timeout=15000)

    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect(display.locator(f"{ROOT} .display-orb").first).to_have_class(re.compile(r"\bred\b"))
    expect(display.locator(ROOT)).to_have_class(CUSTOM)
    assert stored_layout(display) == saved
    assert abs(block_pos(display, "lights")[1] - lights_y) < 0.1


def test_votes_timer_and_results_keep_running_while_editing(competition):
    """The editor is open (a block mid-drag) while the timer runs and the
    judges vote: the display shows the countdown and the result live; saving
    afterwards keeps both."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    open_editor(display)

    head.get_by_role("button", name="Start Timer").click()
    expect(display.locator(".display-timer-big")).to_have_text("60")
    expect(display.locator(".display-timer-big")).not_to_have_text("60", timeout=5000)

    box = block(display, "verdict").bounding_box()
    display.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    display.mouse.down()
    display.mouse.move(box["x"] + 50, box["y"] + 20, steps=2)
    vote(head, "white")
    vote(left, "yellow", with_reason=True)
    vote(right, "red")
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")
    expect(display.locator(f"{ROOT} .display-orb").first).to_have_class(re.compile(r"\bred\b"))
    expect(display.locator(f"{ROOT} .display-orb-card").first).to_have_class(re.compile(r"\byellow\b"))
    display.mouse.up()

    save(display)
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")
    expect(display.locator(f"{ROOT} .display-orb-reason").first).to_be_visible()


def test_lifter_and_attempt_blocks_placeable_without_vportal(page, server_url):
    """Without VPortal the lifter and attempt blocks only appear in the editor
    (with sample text) so they can be placed; outside it they stay hidden."""
    open_display(page, server_url)
    expect(page.locator(".vportal-corner-left")).to_be_hidden()
    open_editor(page)
    expect(page.locator(".vportal-corner-left")).to_be_visible()
    expect(page.locator(".vportal-corner-right")).to_be_visible()
    drag(page, page.locator(".vportal-corner-left"), 400, -300)
    save(page)
    expect(page.locator(".vportal-corner-left")).to_be_hidden()
    assert stored_layout(page)["blocks"]["lifter"]["y"] < 80


def test_vportal_lifter_shown_in_custom_layout(page, server_url, fake_vportal_url):
    """With VPortal connected, moved lifter and attempt blocks show the real
    lifter at their new place, also after a reload."""
    page.set_viewport_size({"width": 1920, "height": 1080})
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    open_editor(page)
    drag(page, corner, 0, -400)
    drag(page, page.locator(".vportal-corner-right"), -600, -400)
    save(page)
    layout = stored_layout(page)

    page.reload()
    page.locator(ROOT).wait_for(state="visible")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(page.locator(".vportal-corner-right")).to_contain_text("215")
    for block_id in ("lifter", "attempt"):
        x, y = block_pos(page, block_id)[:2]
        assert abs(x - layout["blocks"][block_id]["x"]) < 0.1, block_id
        assert abs(y - layout["blocks"][block_id]["y"]) < 0.1, block_id


def test_keys_do_not_end_edit_mode(page, server_url):
    """While editing, "S" and Escape neither open the settings panel nor drop
    or save the layout: only the toolbar buttons end the edit mode."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, block(page, "timer"), 192, 0)
    page.locator("body").press("s")
    page.locator("body").press("Escape")
    expect(page.locator(ROOT)).to_have_class(EDITING)
    expect(page.locator(".display-settings-panel")).to_be_hidden()
    assert stored_layout(page) is None
    save(page)
    assert stored_layout(page) is not None
