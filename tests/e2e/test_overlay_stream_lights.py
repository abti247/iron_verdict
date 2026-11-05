"""Stream overlay: lights only after the decision (#216).

In the stream overlay the lights (with cards, reasons and verdict) are
invisible until a decision arrives live; then they show for a duration
chosen in the overlay's panel ("S", 5 s by default, 3–15 s or "always",
kept on the device) and fade out. The next lift and the start of a pause hide
them earlier. A result that only comes back with the restored state after a
reload or reconnect is not shown again. Both lights views (BVDK and Classic,
whose lights come on one after another); the hall display and the layout
editor always show the lights. Network-related: what a device shows after
reconnecting changes, so a connection-loss and a reload test.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH, cut_network, restore_network
from tests.e2e.test_display_overlay import CLASSIC_LIGHTS, VIEWPORT, overlay_url, wait_joined
from tests.e2e.test_display_pause import end_pause, expect_not_paused, expect_paused, start_pause

BOX = '[data-testid="bvdk-lights"]'
ORB_WRAPS = ".display-lights .display-orb-wrap"
STAMP = ".display-verdict-inline .verdict-stamp"
DURATION_KEY = "iron-verdict:overlay-lights-duration"


def open_overlay(competition, duration=None, classic=False, network_switch=False, **context_args):
    """The overlay URL in a new 1920×1080 context, as OBS opens it. duration:
    stored before the page loads (seconds or "always")."""
    ctx = competition.new_context(viewport=VIEWPORT, **context_args)
    if network_switch:
        ctx.add_init_script(NETWORK_SWITCH)
    if classic:
        ctx.add_init_script(CLASSIC_LIGHTS)
    if duration is not None:
        # Only on the first load: a reload must keep what the panel stored.
        ctx.add_init_script(f"""if (!sessionStorage.getItem('durationSet')) {{
            localStorage.setItem('{DURATION_KEY}', '{duration}');
            sessionStorage.setItem('durationSet', '1');
        }}""")
    page = ctx.new_page()
    page.goto(overlay_url(competition))
    expect(page.get_by_test_id("display-screen")).to_be_visible()
    wait_joined(page)
    return page


def classic_opacities(page):
    """Opacity of the three lights (with card and reason) and of the verdict."""
    return page.evaluate(f"""() => [...document.querySelectorAll('{ORB_WRAPS}'),
        document.querySelector('{STAMP}')].map((el) => parseFloat(getComputedStyle(el).opacity))""")


def expect_classic_shown(page):
    page.wait_for_function(f"""() => [...document.querySelectorAll('{ORB_WRAPS}'), document.querySelector('{STAMP}')]
        .every((el) => getComputedStyle(el).opacity === '1') && document.getAnimations().length === 0""")


def expect_classic_hidden(page, timeout=2000):
    page.wait_for_function(f"""() => [...document.querySelectorAll('{ORB_WRAPS}'), document.querySelector('{STAMP}')]
        .every((el) => getComputedStyle(el).opacity === '0')""", timeout=timeout)


def head_next_lift(competition):
    competition.pages["center_judge"].get_by_role("button", name="Next Lift").click()


def decide(competition):
    head, left, right = (competition.pages[r] for r in ("center_judge", "left_judge", "right_judge"))
    competition.vote_and_lock(left, "red", reason="Depth")
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")


def record_opacity_frames(page, selector):
    """Opacity of selector in every frame (requestAnimationFrame) until stop_frames."""
    page.evaluate(f"""() => {{
        window._frames = [];
        window._stopFrames = false;
        const tick = () => {{
            window._frames.push(parseFloat(getComputedStyle(document.querySelector('{selector}')).opacity));
            if (!window._stopFrames) requestAnimationFrame(tick);
        }};
        tick();
    }}""")


def stop_frames(page):
    return page.evaluate("() => { window._stopFrames = true; return window._frames; }")


def test_classic_lights_come_on_one_after_another_and_fade_out_after_the_duration(competition):
    """Classic: before the decision lights and verdict are invisible in the
    stream (the hall display shows its empty lights). The panel offers 5 s by
    default; with 3 s chosen, the decision brings the lights one after
    another, card and reason after them, the verdict last, all within 1 s.
    After 3 s they fade out (frames between 0 and 1) while the hall display
    still shows the result."""
    competition.join_all_judges()
    overlay = open_overlay(competition, classic=True)
    hall = competition.join_as("display")

    assert classic_opacities(overlay) == [0, 0, 0, 0]
    expect(hall.locator(".display-lights .display-orb").first).to_be_visible()

    overlay.keyboard.press("s")
    select = overlay.get_by_test_id("overlay-lights-duration")
    expect(select).to_have_value("5")
    expect(select.locator("option")).to_have_count(14)
    expect(select.locator("option").first).to_have_text("Always (until next lift)")
    select.select_option("3")
    overlay.keyboard.press("Escape")

    decide(competition)
    expect(overlay.locator(STAMP)).to_have_text("Good Lift")
    timings = overlay.evaluate("""() => document.getAnimations()
        .filter((a) => a instanceof CSSAnimation && a.effect.target.closest('.display-lights, .display-verdict-inline'))
        .map((a) => [a.effect.target.className, a.effect.getComputedTiming().endTime,
                     parseFloat(getComputedStyle(a.effect.target).animationDelay) * 1000])""")
    orbs = [delay for cls, _, delay in timings if cls.startswith("display-orb ")]
    cards = [delay for cls, _, delay in timings if cls.startswith("display-orb-card")]
    stamp = [delay for cls, _, delay in timings if cls.startswith("verdict-stamp")]
    assert orbs == sorted(orbs) and len(set(orbs)) == 3, timings
    assert min(cards) > max(orbs) and stamp[0] > min(cards), timings
    assert max(end for _, end, _ in timings) < 1000, timings
    expect_classic_shown(overlay)

    record_opacity_frames(overlay, STAMP)
    expect_classic_hidden(overlay, timeout=5000)
    frames = stop_frames(overlay)
    assert any(0 < f < 1 for f in frames), frames
    expect(hall.locator(".display-verdict-inline .verdict-stamp")).to_be_visible()
    expect(hall.locator(".display-verdict-inline .verdict-stamp")).to_have_text("Good Lift")


def test_bvdk_box_goes_after_the_duration_and_earlier_with_the_next_lift(competition):
    """BVDK view, 3 s: the box (and the verdict) shows with the decision and
    is gone after 3 s. The next result shows it again; Next Lift before the
    3 s removes it at once (that the old duration does not cut the next result short is
    pinned with fake timers in tests/js/streamLights.test.js)."""
    competition.join_all_judges()
    overlay = open_overlay(competition, duration=3)
    box = overlay.locator(BOX)
    expect(box).to_be_hidden()

    decide(competition)
    expect(box).to_be_visible()
    expect(overlay.locator(STAMP)).to_have_css("opacity", "1")
    expect(box).to_be_hidden(timeout=5000)
    expect(overlay.locator(STAMP)).to_have_css("opacity", "0")

    head_next_lift(competition)
    decide(competition)
    expect(box).to_be_visible()
    head_next_lift(competition)
    expect(box).to_be_hidden(timeout=1000)


def test_pause_start_hides_the_lights_and_they_do_not_come_back(competition):
    """A pause starts while the box shows: the overlay shows the pause; when
    it ends, the box stays away although the result is still there (the hall
    display shows it again)."""
    competition.join_all_judges()
    hall = competition.join_as("display")
    overlay = open_overlay(competition, duration=15)

    decide(competition)
    expect(overlay.locator(BOX)).to_be_visible()
    start_pause(hall, minutes=10)
    expect_paused(overlay)
    end_pause(hall)
    expect_not_paused(overlay)
    expect(hall.locator(".display-verdict-inline .verdict-stamp")).to_have_text("Good Lift")
    expect(overlay.locator(BOX)).to_be_hidden()
    expect(overlay.locator(STAMP)).to_have_css("opacity", "0")


def test_restored_result_is_not_shown_again_after_reload_or_reconnect(competition):
    """BVDK view, default 5 s. A shown result is not shown again after a
    reload, nor after the connection dropped and came back; a result decided
    while the connection was down does not show either. The next live
    decision shows again. With "always" chosen in the panel the choice
    survives a reload and the restored result shows, as on the hall display."""
    competition.join_all_judges()
    overlay = open_overlay(competition, network_switch=True)
    box = overlay.locator(BOX)

    decide(competition)
    expect(box).to_be_visible()
    overlay.reload()
    wait_joined(overlay)
    overlay.wait_for_function("Alpine.store('display').phase === 'votes'")
    expect(box).to_be_hidden()

    # Decided while the overlay's connection is down.
    head_next_lift(competition)
    overlay.wait_for_function("Alpine.store('display').phase === 'idle'")
    cut_network(overlay, conn_dot=".display-tag .conn-dot")
    decide(competition)
    restore_network(overlay)
    expect(overlay.get_by_test_id("display-tag")).to_be_hidden(timeout=10000)
    overlay.wait_for_function("Alpine.store('display').phase === 'votes'")
    expect(box).to_be_hidden()

    # Connection drops and comes back while a live result shows.
    head_next_lift(competition)
    decide(competition)
    expect(box).to_be_visible()
    cut_network(overlay, conn_dot=".display-tag .conn-dot")
    restore_network(overlay)
    expect(overlay.get_by_test_id("display-tag")).to_be_hidden(timeout=10000)
    # Not shown again, and still hidden in the end (that the duration is not
    # restarted is pinned in tests/js/streamLights.test.js).
    expect(box).to_be_hidden(timeout=6000)

    head_next_lift(competition)
    decide(competition)
    expect(box).to_be_visible()

    overlay.keyboard.press("s")
    overlay.get_by_test_id("overlay-lights-duration").select_option("always")
    overlay.keyboard.press("Escape")
    overlay.reload()
    wait_joined(overlay)
    expect(box).to_be_visible()
    overlay.keyboard.press("s")
    expect(overlay.get_by_test_id("overlay-lights-duration")).to_have_value("always")


def test_classic_lights_are_not_shown_again_after_reload(competition):
    """Classic: after a reload the restored result stays invisible in the
    stream (the lights' colours are there, only not shown)."""
    competition.join_all_judges()
    overlay = open_overlay(competition, classic=True)
    decide(competition)
    expect_classic_shown(overlay)
    overlay.reload()
    wait_joined(overlay)
    expect(overlay.locator(".display-lights .display-orb").first).to_have_class(re.compile(r"\bred\b"))
    assert classic_opacities(overlay) == [0, 0, 0, 0]


def test_layout_editor_shows_the_classic_lights_without_a_shown_result(competition):
    """The lights must be placeable: in the layout editor they show without a
    result and after the duration hid one; after Cancel they are invisible
    again."""
    competition.join_all_judges()
    overlay = open_overlay(competition, classic=True, duration=3)
    overlay.keyboard.press("s")
    overlay.get_by_test_id("display-layout-edit").click()
    expect_classic_shown(overlay)
    overlay.get_by_test_id("layout-cancel").click()
    expect_classic_hidden(overlay)

    decide(competition)
    expect_classic_shown(overlay)
    expect_classic_hidden(overlay, timeout=5000)
    overlay.keyboard.press("s")
    overlay.get_by_test_id("display-layout-edit").click()
    expect_classic_shown(overlay)


def test_classic_lights_only_fade_with_reduced_motion(competition):
    """With "reduce motion" the Classic lights and the verdict only fade in
    briefly (no staggered parts)."""
    competition.join_all_judges()
    overlay = open_overlay(competition, classic=True, reduced_motion="reduce")
    decide(competition)
    expect(overlay.locator(STAMP)).to_have_text("Good Lift")
    animations = overlay.evaluate("""() => document.getAnimations()
        .filter((a) => a instanceof CSSAnimation && a.effect.target.closest('.display-lights, .display-verdict-inline'))
        .map((a) => [a.animationName, a.effect.getComputedTiming().endTime])""")
    assert animations, "no fade at all"
    assert {name for name, _ in animations} == {"bvdk-fade"}, animations
    assert max(end for _, end in animations) <= 250, animations
    expect_classic_shown(overlay)


def test_duration_that_cannot_be_stored_says_so(competition):
    """If the device cannot store the duration (site data blocked), the panel
    says it will be lost after a reload; the choice still applies."""
    competition.create_session_and_join_head()
    overlay = open_overlay(competition)
    overlay.evaluate("() => { Storage.prototype.setItem = () => { throw new Error('blocked'); }; }")
    overlay.keyboard.press("s")
    overlay.get_by_test_id("overlay-lights-duration").select_option("always")
    expect(overlay.get_by_test_id("overlay-lights-duration-save-error")).to_be_visible()
    expect(overlay.get_by_test_id("overlay-lights-duration")).to_have_value("always")
