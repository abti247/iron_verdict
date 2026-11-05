"""Stream overlay lights: BVDK view and Iron Verdict Classic (#215).

A new stream overlay shows the lights in the BVDK view: a box with the head
"REFEREES" and the discipline (always English), three square lights and one
row per invalid vote (which judge, card colour, reason), in a narrow font the
app serves itself. The box only appears with the result (a wipe of under a
second, a short fade with "reduce motion") and goes with the next lift. The
operator switches to Classic (the round lights of the hall display) in the
overlay's panel ("S"); the choice stays on the device (localStorage), so the
test is a reload, not a connection loss. Both views share the overlay's
layout: the box sits in the "Lights" block, at the bottom right by default.
The hall display is unchanged.
"""

import re

from playwright.sync_api import expect

from tests.e2e.test_display_overlay import VIEWPORT, overlay_url, wait_joined

VIEW_KEY = "iron-verdict:overlay-lights-view"
BOX = '[data-testid="bvdk-lights"]'
ROWS = '[data-testid="bvdk-row"]'

GERMAN_LONGEST = {
    "left": "Unter­stützung am Ober­schenkel",
    "center": "Arme nicht gestreckt bei Abschluss",
    "right": "Hantel­kontakt mit Hantel­ständern",
}


def open_overlay(competition, **context_args):
    ctx = competition.new_context(viewport=VIEWPORT, **context_args)
    page = ctx.new_page()
    page.goto(overlay_url(competition))
    expect(page.get_by_test_id("display-screen")).to_be_visible()
    wait_joined(page)
    return page


def show_results(page, votes, reasons, lift_type="squat"):
    """Write a result into the display store as show_results does (handlers.js),
    for texts no single lift can produce (e.g. the longest German reasons)."""
    page.evaluate(
        "([votes, reasons, liftType]) => Alpine.store('display').showResults("
        "{votes, reasons, showExplanations: true, liftType})",
        [votes, reasons, lift_type],
    )


def lights_state(page):
    return page.evaluate(
        f"""() => [...document.querySelectorAll('{BOX} .bvdk-light')]
            .map((el) => el.classList.contains('red') ? 'red' : 'white')"""
    )


def row_markers(page):
    """Per row: index of the highlighted square (which judge) and the card colour."""
    return page.evaluate(
        f"""() => [...document.querySelectorAll('{ROWS}')].map((row) => [
            [...row.querySelectorAll('.bvdk-pos i')].findIndex((i) => i.classList.contains('on')),
            ['red', 'blue', 'yellow'].find((c) => row.querySelector('.bvdk-card').classList.contains(c)),
        ])"""
    )


def assert_reasons_fully_readable(page):
    """Every reason lies on screen, is not cut off (no overflow), and no word
    breaks inside except at a soft hyphen of de.json."""
    result = page.evaluate(f"""() => {{
        const problems = [];
        for (const el of document.querySelectorAll('{ROWS} .bvdk-reason')) {{
            const r = el.getBoundingClientRect();
            if (r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth) problems.push(['off screen', el.textContent]);
            if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) problems.push(['cut off', el.textContent]);
            const node = el.firstChild;
            const re = /[^\\s\\u00ad-]+/g;
            let m;
            while ((m = re.exec(node.data))) {{
                const lines = new Set();
                for (let i = m.index; i < m.index + m[0].length; i++) {{
                    const range = document.createRange();
                    range.setStart(node, i);
                    range.setEnd(node, i + 1);
                    const rects = range.getClientRects();
                    lines.add(Math.round(rects[rects.length - 1].top));
                }}
                if (lines.size > 1) problems.push(['word broken', m[0]]);
            }}
        }}
        return problems;
    }}""")
    assert result == [], result


def test_new_overlay_shows_the_bvdk_box_only_with_the_result(competition):
    """Without a stored choice the overlay shows the BVDK view: nothing before
    the decision (no round lights either); with it the box with "REFEREES" and
    the English discipline, white/red square lights and one row per invalid
    vote (judge marker, card colour, reason) in the self-hosted narrow font;
    the next lift removes it. The hall display keeps its round lights."""
    head, left, right = competition.join_all_judges()
    head.get_by_test_id("lift-type-select").select_option("deadlift")
    overlay = open_overlay(competition)
    hall = competition.join_as("display")

    expect(overlay.locator(BOX)).to_be_hidden()
    expect(overlay.locator(".display-lights .display-orb").first).to_be_hidden()

    competition.vote_and_lock(left, "red", reason="Shoulders not behind bar")
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "blue", reason="Hitching")

    box = overlay.locator(BOX)
    expect(box).to_be_visible()
    expect(box.locator(".bvdk-head-title")).to_have_text("REFEREES")
    expect(box.locator(".bvdk-head-discipline")).to_have_text("DEADLIFT")
    assert lights_state(overlay) == ["red", "white", "red"]
    rows = overlay.locator(ROWS)
    expect(rows).to_have_count(2)
    expect(rows.nth(0).locator(".bvdk-reason")).to_have_text("Shoulders not behind bar")
    expect(rows.nth(1).locator(".bvdk-reason")).to_have_text("Hitching")
    assert row_markers(overlay) == [[0, "red"], [2, "blue"]]
    expect(overlay.locator(".display-lights .display-orb").first).to_be_hidden()
    assert_reasons_fully_readable(overlay)

    # The narrow font comes from the app itself, not from the internet.
    family = overlay.evaluate(f"getComputedStyle(document.querySelector('{BOX} .bvdk-reason')).fontFamily")
    assert family.startswith('"Barlow Condensed"'), family
    assert overlay.evaluate("""() => document.fonts.check('700 1em "Barlow Condensed"')
        && [...document.fonts].some((f) => f.family.includes('Barlow Condensed') && f.status === 'loaded')""")
    font_urls = overlay.evaluate(
        "() => performance.getEntriesByType('resource').map((e) => e.name).filter((n) => n.includes('barlow'))"
    )
    assert font_urls and all(u.startswith(competition.url + "/static/fonts/") for u in font_urls), font_urls

    # The hall display is unchanged: round lights, no BVDK box.
    expect(hall.locator(".display-lights .display-orb").first).to_be_visible()
    expect(hall.locator(BOX)).to_be_hidden()

    head.get_by_role("button", name="Next Lift").click()
    expect(overlay.locator(BOX)).to_be_hidden()


def test_bvdk_box_sits_bottom_right_and_keeps_the_longest_reasons_readable(competition):
    """By default (no saved layout) the box sits at the bottom right. Three
    invalid votes with the longest German reasons: every reason lies fully
    on screen without a word broken inside, and the box grows upwards, so its
    bottom edge (on top of the broadcast graphics) stays where it was with
    one reason."""
    competition.create_session_and_join_head()
    overlay = open_overlay(competition)

    show_results(overlay, {"left": "white", "center": "white", "right": "red"},
                 {"left": None, "center": None, "right": "Knie nicht gestreckt"})
    box = overlay.locator(BOX)
    expect(box).to_be_visible()
    one = box.bounding_box()
    assert one["x"] + one["width"] > VIEWPORT["width"] * 0.85, one
    assert one["y"] + one["height"] > VIEWPORT["height"] * 0.7, one
    assert one["y"] + one["height"] < VIEWPORT["height"], one

    show_results(overlay, {"left": "blue", "center": "red", "right": "yellow"}, GERMAN_LONGEST, "bench")
    expect(overlay.locator(ROWS)).to_have_count(3)
    three = box.bounding_box()
    assert abs((three["y"] + three["height"]) - (one["y"] + one["height"])) < 1, (one, three)
    assert three["height"] > one["height"]
    assert_reasons_fully_readable(overlay)


def test_lights_view_switches_to_classic_and_back_and_survives_reload(competition):
    """In the panel ("S") the BVDK view is selected; "Iron Verdict Classic"
    shows the round lights with card and reason instead of the box, also
    after a reload (the result is restored). Back to the BVDK view: the box
    shows the same result, again after a reload."""
    head, left, right = competition.join_all_judges()
    overlay = open_overlay(competition)

    overlay.keyboard.press("s")
    bvdk_btn = overlay.get_by_test_id("overlay-lights-bvdk")
    classic_btn = overlay.get_by_test_id("overlay-lights-classic")
    expect(bvdk_btn).to_have_attribute("aria-pressed", "true")
    expect(classic_btn).to_have_attribute("aria-pressed", "false")
    classic_btn.click()
    expect(classic_btn).to_have_attribute("aria-pressed", "true")
    overlay.keyboard.press("Escape")

    competition.vote_and_lock(left, "red", reason="Depth")
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")
    reason = overlay.locator(".display-lights .display-orb-wrap:nth-child(1) .display-orb-reason")
    expect(reason).to_have_text("Depth")
    expect(overlay.locator(BOX)).to_be_hidden()

    overlay.reload()
    wait_joined(overlay)
    expect(reason).to_have_text("Depth")
    expect(overlay.locator(".display-lights .display-orb").first).to_have_class(re.compile(r"\bred\b"))
    expect(overlay.locator(BOX)).to_be_hidden()
    assert overlay.evaluate(f"localStorage.getItem('{VIEW_KEY}')") == "classic"

    overlay.keyboard.press("s")
    expect(classic_btn).to_have_attribute("aria-pressed", "true")
    bvdk_btn.click()
    overlay.keyboard.press("Escape")
    expect(overlay.locator(BOX)).to_be_visible()
    expect(overlay.locator(f"{ROWS} .bvdk-reason")).to_have_text(["Depth"])
    expect(reason).to_be_hidden()

    overlay.reload()
    wait_joined(overlay)
    expect(overlay.locator(BOX)).to_be_visible()
    expect(overlay.locator(f"{ROWS} .bvdk-reason")).to_have_text(["Depth"])


def test_lights_view_switch_is_offered_only_in_the_overlay(competition):
    """The hall display's panel has no lights view switch."""
    competition.create_session_and_join_head()
    hall = competition.join_as("display")
    hall.keyboard.press("s")
    expect(hall.locator(".display-settings-panel")).to_be_visible()
    expect(hall.get_by_test_id("overlay-lights-bvdk")).to_be_hidden()


def test_lights_view_that_cannot_be_stored_says_so(competition):
    """If the device cannot store the choice (site data blocked), the panel
    says it will be lost after a reload; the view still switches."""
    competition.create_session_and_join_head()
    overlay = open_overlay(competition)
    overlay.evaluate("() => { Storage.prototype.setItem = () => { throw new Error('blocked'); }; }")
    overlay.keyboard.press("s")
    overlay.get_by_test_id("overlay-lights-classic").click()
    expect(overlay.get_by_test_id("overlay-lights-save-error")).to_be_visible()
    expect(overlay.get_by_test_id("overlay-lights-classic")).to_have_attribute("aria-pressed", "true")


def animation_summary(page):
    """Names and end times (ms) of the running animations inside the box."""
    return page.evaluate(f"""() => document.getAnimations()
        .filter((a) => a.effect && a.effect.target && a.effect.target.closest('{BOX}'))
        .map((a) => [a.animationName, a.effect.getComputedTiming().endTime])""")


def test_bvdk_box_wipes_in_under_a_second(competition):
    """The box builds up with a wipe (head, body, lights, reason rows) that
    ends in under a second; the result itself is in the store at once."""
    competition.create_session_and_join_head()
    overlay = open_overlay(competition)
    show_results(overlay, {"left": "blue", "center": "red", "right": "yellow"}, GERMAN_LONGEST)
    expect(overlay.locator(BOX)).to_be_visible()
    animations = animation_summary(overlay)
    names = {name for name, _ in animations}
    assert {"bvdk-wipe-x", "bvdk-wipe-y", "bvdk-pop", "bvdk-slide-in"} <= names, animations
    assert max(end for _, end in animations) < 1000, animations


def test_bvdk_box_only_fades_with_reduced_motion(competition):
    """With "reduce motion" the box only fades in briefly, without wipes or
    staggered parts."""
    competition.create_session_and_join_head()
    overlay = open_overlay(competition, reduced_motion="reduce")
    show_results(overlay, {"left": "blue", "center": "red", "right": "yellow"}, GERMAN_LONGEST)
    expect(overlay.locator(BOX)).to_be_visible()
    animations = animation_summary(overlay)
    assert animations, "no fade at all"
    assert {name for name, _ in animations} == {"bvdk-fade"}, animations
    assert max(end for _, end in animations) <= 250, animations


def test_bvdk_box_is_placed_in_the_layout_editor_and_kept_after_reload(competition):
    """In the editor the "Lights" block shows a faded sample box (labelled as
    sample) at the bottom right, without the gap handle and the cards frame
    of the round lights. Dragged and saved, the real box shows at the new
    place after a reload."""
    head, left, right = competition.join_all_judges()
    overlay = open_overlay(competition)

    overlay.keyboard.press("s")
    overlay.get_by_test_id("display-layout-edit").click()
    box = overlay.locator(BOX)
    expect(box).to_be_visible()
    expect(box).to_have_class(re.compile(r"\blayout-sample\b"))
    expect(overlay.locator('[data-layout-block="lights"] .layout-frame-label').first).to_contain_text("Lights · sample")
    expect(overlay.get_by_test_id("layout-lights-gap-handle")).to_be_hidden()
    expect(overlay.locator('[data-layout-block="cards"]')).to_be_hidden()
    before = box.bounding_box()
    assert before["x"] + before["width"] > VIEWPORT["width"] * 0.85, before

    block = overlay.locator('[data-layout-block="lights"]')
    b = block.bounding_box()
    overlay.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    overlay.mouse.down()
    overlay.mouse.move(b["x"] + b["width"] / 2 - 600, b["y"] + b["height"] / 2 - 200, steps=5)
    overlay.mouse.up()
    overlay.get_by_test_id("layout-save").click()
    expect(box).to_be_hidden()

    overlay.reload()
    wait_joined(overlay)
    competition.vote_and_lock(left, "red", reason="Depth")
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")
    expect(box).to_be_visible()
    expect(box).not_to_have_class(re.compile(r"\blayout-sample\b"))
    after = box.bounding_box()
    # Moved by the drag (snapped to 1 %): left and up.
    assert after["x"] < before["x"] - 500, (before, after)
    assert after["y"] + after["height"] < before["y"] + before["height"] - 150, (before, after)
