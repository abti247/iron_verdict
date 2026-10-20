"""Display layout editor (#106).

From the display settings (gear or "S") the operator opens an edit mode: the
blocks of the display (timer, lights, cards + reasons under the lights,
verdict, lifter info, attempt info) get a frame and can be dragged (mouse and
touch) and scaled at a handle, snapping to 1 % of the screen. Each block is
anchored where its content grows from (lifter: left edge, attempt: right
edge, the others: centre), so longer content never pushes it off screen. The cards block
follows the lights and is only dragged up or down (its gap to the lights).
The gap between the three lights is set at a handle on the side of the
lights block (#154).
Every block can be hidden. "Save" stores the layout on this device, "Cancel"
drops the changes, "Reset" brings back the default. A layout can be copied to
another device as a code. Without a saved layout the display looks as before.
While editing, the display keeps showing votes, timer and VPortal data.
"""

import json
import re

import httpx
import pytest
from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_vportal_integration import _connect_and_open_display

LAYOUT_KEY = "iron-verdict:display-layout"
ROOT = ".display-full"
CUSTOM = re.compile(r"\bdisplay-layout-custom\b")
EDITING = re.compile(r"\bdisplay-layout-editing\b")


def block(page, block_id):
    return page.locator(f'{ROOT} [data-layout-block="{block_id}"]')


ANCHORS = {"timer": "center", "lights": "center", "verdict": "center", "lifter": "left", "attempt": "right"}


def block_pos(page, block_id):
    """[anchor x, top] of a block in percent of the display (anchor: left
    edge, centre or right edge, see ANCHORS), plus its width and height in px."""
    return page.evaluate(
        """([id, anchor]) => {
            const root = document.querySelector('.display-full').getBoundingClientRect();
            const r = document.querySelector(`.display-full [data-layout-block="${id}"]`).getBoundingClientRect();
            const x = anchor === 'left' ? r.left : anchor === 'right' ? r.right : r.left + r.width / 2;
            return [ (x - root.left) / root.width * 100, (r.top - root.top) / root.height * 100,
                     r.width, r.height ];
        }""",
        [block_id, ANCHORS.get(block_id, "left")],
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


def lights_gap(page):
    """Gap between the lights in px (column-gap of the lights block)."""
    return page.evaluate(
        "parseFloat(getComputedStyle(document.querySelector('.display-full .display-lights')).columnGap)"
    )


def touch_drag(page, locator, dx, dy, steps=4):
    """Drag with real touch input (CDP), like a finger on a tablet."""
    box = locator.bounding_box()
    sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": sx, "y": sy}]})
    for i in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent",
                 {"type": "touchMove", "touchPoints": [{"x": sx + dx * i / steps, "y": sy + dy * i / steps}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


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
    # Lights are centred: the handle 1.5× as far from the centre → scale 1.5.
    drag(page, block(page, "lights").locator(".layout-scale-handle"), lights_w * 0.25, 0)
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
    touch_drag(page, block(page, "verdict"), -384, -108)
    save(page)
    layout = stored_layout(page)
    assert layout["blocks"]["verdict"]["x"] == round(x0 - 20)
    assert layout["blocks"]["verdict"]["y"] == round(y0 - 10)


def test_lights_gap_set_at_side_handle_with_mouse_and_touch_survives_reload(page, server_url):
    """Without a layout the lights stand 128 px apart (as before #154). In the
    editor the handle on the side of the lights narrows the gap with the mouse
    (−64 px → 0.5× in 5 % steps) and widens it with a finger (+32 px →
    0.75×); the lights stay centred where they were. It never goes below
    0.4× (reasons of neighbouring lights would touch). Saved, the gap comes
    back after a reload."""
    open_display(page, server_url)
    assert lights_gap(page) == 128
    centre_x = block_pos(page, "lights")[0]
    open_editor(page)
    handle = page.get_by_test_id("layout-lights-gap-handle")
    expect(handle).to_be_visible()

    drag(page, handle, -64, 0)
    assert lights_gap(page) == 64
    touch_drag(page, handle, 32, 0)
    assert lights_gap(page) == 96
    assert abs(block_pos(page, "lights")[0] - centre_x) < 0.6
    save(page)
    assert stored_layout(page)["blocks"]["lights"]["gap"] == 0.75

    page.reload()
    page.locator(ROOT).wait_for(state="visible")
    expect(page.locator(ROOT)).to_have_class(CUSTOM)
    assert lights_gap(page) == 96
    expect(page.get_by_test_id("layout-lights-gap-handle")).to_be_hidden()

    open_editor(page)
    drag(page, page.get_by_test_id("layout-lights-gap-handle"), -500, 0)
    assert lights_gap(page) == 128 * 0.4
    page.get_by_test_id("layout-cancel").click()
    assert lights_gap(page) == 96


def test_layout_without_lights_gap_keeps_default_gap(page, server_url):
    """A layout saved before #154 has no lights gap: it stays valid and the
    lights keep the gap of before (128 px)."""
    open_display(page, server_url)
    page.evaluate(f"""localStorage.setItem('{LAYOUT_KEY}', JSON.stringify({{v: 1, blocks: {{
        timer: {{x: 50, y: 5, s: 1, hidden: false}},
        lights: {{x: 50, y: 40, s: 0.8, hidden: false}},
        cards: {{gap: 0, hidden: false}},
        verdict: {{x: 50, y: 80, s: 1, hidden: false}},
        lifter: {{x: 2, y: 88, s: 1, hidden: false}},
        attempt: {{x: 98, y: 88, s: 1, hidden: false}}}}}}))""")
    page.reload()
    page.locator(ROOT).wait_for(state="visible")
    expect(page.locator(ROOT)).to_have_class(CUSTOM)
    expect(block(page, "lights")).to_have_attribute("style", re.compile(r"--display-zoom: 0\.8"))
    assert lights_gap(page) == 128


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
    """Display A exports its layout as a code (including a narrower gap
    between the lights); display B pastes it, sees the layout and saves
    it. A wrong code shows an error and changes nothing."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, block(page, "timer"), 192, 108)
    drag(page, page.get_by_test_id("layout-lights-gap-handle"), -64, 0)
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
    assert layout_a["blocks"]["lights"]["gap"] == 0.5
    expect(block(other, "verdict")).to_be_hidden()
    assert lights_gap(other) == 64


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
    (with faded sample text, labelled as a sample) so they can be placed;
    outside it they stay hidden."""
    open_display(page, server_url)
    expect(page.locator(".vportal-corner-left")).to_be_hidden()
    open_editor(page)
    for corner in (".vportal-corner-left", ".vportal-corner-right"):
        expect(page.locator(corner)).to_be_visible()
        expect(page.locator(corner)).to_have_class(re.compile(r"\blayout-sample\b"))
        expect(page.locator(f"{corner} .layout-frame-label")).to_contain_text("sample")
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


def test_attempt_and_verdict_stay_anchored_when_content_grows(page, server_url):
    """A layout saved with the sample attempt keeps the attempt block's right
    edge in place when a much wider attempt arrives (long discipline, decimal
    weight), so the weight is never cut off at the screen edge; the verdict
    stays centred whether it reads "Good Lift" or "No Lift"."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, page.locator(".vportal-corner-right"), -96, -216)
    save(page)
    right_edge = stored_layout(page)["blocks"]["attempt"]["x"]

    page.evaluate("""() => { Alpine.store('vportal').displayAttempt = {
        firstName: 'Maximiliane', lastName: 'Schneider-Wolkenstein', club: 'SV Eisenkraft',
        bodyWeightCategory: '-84 kg', ageCategory: 'Masters 1',
        discipline: 'Deadlift (Kreuzheben)', attempt: 3, weight: 312.5 }; }""")
    weight = page.locator(".vportal-corner-weight")
    expect(weight).to_have_text("312.5 KG")
    expect(page.locator(".vportal-corner-right")).to_be_visible()
    x = block_pos(page, "attempt")[0]
    assert abs(x - right_edge) < 0.1, (x, right_edge)
    root_right = page.locator(ROOT).bounding_box()["width"]
    box = weight.bounding_box()
    assert box["x"] + box["width"] <= root_right, box

    def verdict_center():
        b = page.locator(".verdict-stamp").bounding_box()
        return b["x"] + b["width"] / 2

    show = """(votes) => Alpine.store('display').showResults({ votes,
        reasons: { left: '', center: '', right: '' }, showExplanations: true, liftType: 'squat' })"""
    page.evaluate(show, {"left": "white", "center": "white", "right": "white"})
    expect(page.locator(".verdict-stamp")).to_have_text("Good Lift")
    good = verdict_center()
    page.evaluate(show, {"left": "red", "center": "red", "right": "white"})
    expect(page.locator(".verdict-stamp")).to_have_text("No Lift")
    assert abs(verdict_center() - good) < 1, (good, verdict_center())


def test_vportal_keeps_updating_while_editing(page, server_url, fake_vportal_url):
    """With VPortal connected and the editor open, the lifter changes on the
    VPortal side: no active attempt → the blocks show the faded sample; the
    attempt is back → the real lifter appears while still editing, and stays
    after saving."""
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    open_editor(page)
    expect(corner).not_to_have_class(re.compile(r"\blayout-sample\b"))

    httpx.post(f"http://{fake_vportal_url}/_control/clear_attempt")
    expect(corner).to_have_class(re.compile(r"\blayout-sample\b"), timeout=10000)
    expect(corner).not_to_contain_text("MARIA SCHNEIDER", ignore_case=True)

    httpx.post(f"http://{fake_vportal_url}/_control/restore_attempt")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(corner).not_to_have_class(re.compile(r"\blayout-sample\b"))
    expect(page.locator(ROOT)).to_have_class(EDITING)
    save(page)
    expect(corner).to_contain_text("MARIA SCHNEIDER", ignore_case=True)


def test_save_failure_is_shown_and_keeps_editor_open(page, server_url):
    """If this device cannot store the layout (browser storage blocked or
    full), "Save" says so and the editor stays open instead of pretending the
    layout was saved."""
    open_display(page, server_url)
    open_editor(page)
    drag(page, block(page, "timer"), 192, 0)
    page.evaluate("""() => { Storage.prototype.setItem = () => {
        throw new DOMException('full', 'QuotaExceededError'); }; }""")
    page.get_by_test_id("layout-save").click()
    expect(page.get_by_test_id("layout-save-error")).to_be_visible()
    expect(page.locator(ROOT)).to_have_class(EDITING)
    page.get_by_test_id("layout-cancel").click()
    expect(page.locator(ROOT)).not_to_have_class(EDITING)


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("size", [(1920, 1080), (1280, 720)])
def test_editor_labels_do_not_overlap_in_default_layout(competition, size, lang):
    """A no lift with reasons on a display in the default layout, editor open,
    in English and German (longer labels and verdict) (#162): no two block
    labels overlap, and every hide/show button lies fully on screen,
    uncovered by the toolbar or anything else, so it can be clicked. Before
    the fix the verdict label covered the label of the cards + reasons
    (under the cards frame), and at 1280×720 the toolbar covered the timer
    label and the attempt button stuck out on the right."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    display.set_viewport_size({"width": size[0], "height": size[1]})
    display.evaluate(f"localStorage.setItem('iron-verdict-lang', '{lang}')")
    display.reload()
    display.locator(ROOT).wait_for(state="visible")
    vote(head, "white")
    vote(left, "red", with_reason=True)
    vote(right, "blue", with_reason=True)
    expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\binvalid\b"))
    expect(display.locator(f"{ROOT} .display-orb-reason").first).to_be_visible()
    open_editor(display)
    expect(display.locator(ROOT)).not_to_have_class(CUSTOM)

    labels = display.evaluate(
        """() => [...document.querySelectorAll('.display-full .layout-frame-label')]
            .filter(el => el.getClientRects().length)
            .map(el => {
                const r = el.getBoundingClientRect();
                const button = el.querySelector('.layout-hide-toggle');
                const b = button.getBoundingClientRect();
                // Centre and the four corners (1px inside): nothing, e.g. the
                // toolbar or another label, covers any part of the button.
                const points = [[b.left + b.width / 2, b.top + b.height / 2],
                                [b.left + 1, b.top + 1], [b.right - 1, b.top + 1],
                                [b.left + 1, b.bottom - 1], [b.right - 1, b.bottom - 1]];
                return { id: el.closest('[data-layout-block]').dataset.layoutBlock,
                         rect: [r.left, r.top, r.right, r.bottom],
                         button: [b.left, b.top, b.right, b.bottom],
                         hit: points.every(([x, y]) => document.elementFromPoint(x, y) === button) };
            })"""
    )
    assert {lab["id"] for lab in labels} == {"timer", "lights", "cards", "verdict", "lifter", "attempt"}
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            ax0, ay0, ax1, ay1 = a["rect"]
            bx0, by0, bx1, by1 = b["rect"]
            overlap = ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
            assert not overlap, (a, b)
    for lab in labels:
        x0, y0, x1, y1 = lab["button"]
        assert x0 >= 0 and y0 >= 0 and x1 <= size[0] and y1 <= size[1], lab
        assert lab["hit"], lab
