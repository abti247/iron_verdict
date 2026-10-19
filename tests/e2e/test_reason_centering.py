"""Reasons under the lights stay centred, also for long words (issue #114).

Each check measures every light/reason pair: the centre of the rendered text
must sit under the centre of the light, no text may overflow its box, no word
may break mid-word or at a soft hyphen when it would fit unbroken, a box
may reach at most half the gap towards its neighbour nor leave the screen
(judge: the results row), and the lights must not move when reasons appear.
"""

import json
from pathlib import Path

from playwright.sync_api import expect

LOCALES = Path(__file__).resolve().parents[2] / "src" / "iron_verdict" / "static" / "locales"

# Display: the lights row; judge: the small results panel.
DISPLAY = ".display-lights"
JUDGE = ".judge-results-orbs"
# What a reason box must stay inside of: the display screen, the results row.
BOUNDS = {DISPLAY: ".display-full", JUDGE: JUDGE}

MEASURE_JS = """([container, bounds]) => {
    const root = document.querySelector(container);
    const gap = parseFloat(getComputedStyle(root).columnGap);
    const row = document.querySelector(bounds).getBoundingClientRect();
    // Light columns only: the display's lights block also holds the layout
    // editor frames (#106).
    return [...root.children].filter((wrap) => wrap.querySelector('.display-orb')).map((wrap) => {
        const orb = wrap.querySelector('.display-orb').getBoundingClientRect();
        const el = wrap.querySelector('.display-orb-reason');
        const shown = el && getComputedStyle(el).display !== 'none' && el.textContent;
        if (!shown) return { orbCenter: orb.left + orb.width / 2, gap };
        const box = el.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(el);
        const text = range.getBoundingClientRect();
        // Would any word overflow if it were not allowed to break mid-word?
        el.style.overflowWrap = 'normal';
        const wordOverflow = el.scrollWidth - el.clientWidth;
        el.style.overflowWrap = '';
        // Would the words fit unbroken? Then a soft-hyphen break is needless.
        const lines = el.offsetHeight;
        el.style.hyphens = 'none';
        const fitsUnhyphenated = el.scrollWidth <= el.clientWidth;
        const needlessHyphen = fitsUnhyphenated && el.offsetHeight < lines;
        el.style.hyphens = '';
        return {
            reason: el.textContent,
            gap,
            orbLeft: orb.left,
            orbRight: orb.right,
            orbCenter: orb.left + orb.width / 2,
            boxLeft: box.left,
            boxRight: box.right,
            textLeft: text.left,
            textRight: text.right,
            textCenter: text.left + text.width / 2,
            overflow: el.scrollWidth - el.clientWidth,
            wordOverflow,
            needlessHyphen,
            columnLeft: wrap.getBoundingClientRect().left,
            columnRight: wrap.getBoundingClientRect().right,
            rowLeft: Math.max(row.left, 0),
            rowRight: Math.min(row.right, document.documentElement.clientWidth),
        };
    });
}"""


def _all_reasons():
    """Every reason label of every discipline and card, German and English."""
    labels = set()
    for lang in ("de", "en"):
        catalog = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))
        for cards in catalog["reasons"].values():
            for reasons in cards.values():
                labels.update(reasons.values())
    return sorted(labels, key=len, reverse=True)


def _assert_centered(page, container, orb_centers_before=None):
    pairs = page.evaluate(MEASURE_JS, [container, BOUNDS[container]])
    for pair in pairs:
        if "reason" not in pair:
            continue
        name = f"{container} {pair['reason']!r}"
        assert abs(pair["textCenter"] - pair["orbCenter"]) <= 1.5, f"{name} off-centre: {pair}"
        assert pair["overflow"] <= 0, f"{name} overflows its box: {pair}"
        assert pair["wordOverflow"] <= 0, f"{name} breaks mid-word: {pair}"
        assert not pair["needlessHyphen"], f"{name} hyphenates a word that fits: {pair}"
        assert pair["textLeft"] >= pair["boxLeft"] - 0.5, f"{name} text outside box: {pair}"
        assert pair["textRight"] <= pair["boxRight"] + 0.5, f"{name} text outside box: {pair}"
        half_gap = pair["gap"] / 2
        assert pair["boxLeft"] >= pair["columnLeft"] - half_gap - 0.5, f"{name} too wide: {pair}"
        assert pair["boxRight"] <= pair["columnRight"] + half_gap + 0.5, f"{name} too wide: {pair}"
        assert pair["boxLeft"] >= pair["rowLeft"] - 0.5, f"{name} leaves the row/screen: {pair}"
        assert pair["boxRight"] <= pair["rowRight"] + 0.5, f"{name} leaves the row/screen: {pair}"
    if orb_centers_before is not None:
        after = [p["orbCenter"] for p in pairs]
        for before, now in zip(orb_centers_before, after):
            assert abs(before - now) <= 0.5, f"{container} lights moved: {orb_centers_before} -> {after}"


def _orb_centers(page, container):
    return [p["orbCenter"] for p in page.evaluate(MEASURE_JS, [container, BOUNDS[container]])]


def _sweep(page, container, store_js):
    """Show every reason (three at a time) via the store and measure each."""
    labels = _all_reasons()
    page.evaluate(store_js, ["", "", ""])  # lights shown, no reasons yet
    page.locator(f"{container} .display-orb").first.wait_for(state="visible")
    before = _orb_centers(page, container)
    for i in range(0, len(labels), 3):
        batch = (labels[i:i + 3] + labels[:3])[:3]
        page.evaluate(store_js, batch)
        page.wait_for_function(
            "([c, texts]) => JSON.stringify([...document.querySelectorAll(c + ' .display-orb-reason')]"
            ".map(el => getComputedStyle(el).display !== 'none' && el.textContent)) === JSON.stringify(texts)",
            arg=[container, batch],
        )
        _assert_centered(page, container, before)


SHOW_ON_DISPLAY = """([l, c, r]) => Alpine.store('display').showResults({
    votes: { left: 'red', center: 'blue', right: 'yellow' },
    reasons: { left: l, center: c, right: r },
    showExplanations: true,
    liftType: 'bench',
})"""

SHOW_ON_JUDGE = """([l, c, r]) => Alpine.store('judge').showResults(
    { left: 'red', center: 'blue', right: 'yellow' },
    { left: l, center: c, right: r },
)"""


def _scale_lights(page, scale):
    """Save a layout with the lights block scaled (the layout editor's scale,
    #106) and reload the display with it."""
    blocks = {b: {"x": 5, "y": 5, "s": 1, "hidden": False} for b in ("timer", "verdict", "lifter", "attempt")}
    blocks["lights"] = {"x": 8, "y": 20, "s": scale, "hidden": False}
    blocks["cards"] = {"gap": 0, "hidden": False}
    page.evaluate(
        "(l) => localStorage.setItem('iron-verdict:display-layout', JSON.stringify(l))",
        {"v": 1, "blocks": blocks},
    )
    page.reload()
    page.locator(".display-full").wait_for(state="visible")
    page.wait_for_function(
        """(s) => Math.abs(parseFloat(getComputedStyle(document.querySelector('.display-lights'))
            .getPropertyValue('--display-zoom')) - s) < 0.001""",
        arg=scale,
    )


def test_long_german_reasons_centered_on_display_and_judge_results(competition):
    """Bench press, German UI on all screens: the three judges lock in red,
    blue and yellow with the reasons containing the longest German words
    ("Ellenbogentiefe", "Abwärtsbewegung", "Hantelkontakt mit Hantelständern").
    On a 1920×1080 display and in every judge's results panel each reason is
    centred under its light, fits its box, and the lights do not shift."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    display.set_viewport_size({"width": 1920, "height": 1080})
    head.get_by_test_id("lift-type-select").select_option("bench")

    for page, ready in ((head, ".judge-wrap"), (left, ".judge-wrap"),
                        (right, ".judge-wrap"), (display, ".display-full")):
        page.evaluate("localStorage.setItem('iron-verdict-lang', 'de')")
        page.reload()
        page.locator(ready).wait_for(state="visible")
    expect(head.get_by_test_id("lift-type-select")).to_have_value("bench")

    before = _orb_centers(display, DISPLAY)
    competition.vote_and_lock(left, "red", "Ellenbogentiefe")
    competition.vote_and_lock(head, "blue", "Abwärtsbewegung")
    competition.vote_and_lock(right, "yellow", "Hantelkontakt mit Hantelständern")

    reasons = display.locator(f"{DISPLAY} .display-orb-reason")
    expect(reasons.filter(has_text="Hantelkontakt mit Hantelständern")).to_be_visible()
    expect(reasons.filter(has_text="Abwärtsbewegung")).to_be_visible()
    expect(reasons.filter(has_text="Ellenbogentiefe")).to_be_visible()
    _assert_centered(display, DISPLAY, before)

    for judge in (head, left, right):
        expect(judge.locator(f"{JUDGE} .display-orb-reason", has_text="Hantelständern")).to_be_visible()
        _assert_centered(judge, JUDGE)


def test_every_reason_centered_on_display(competition):
    """All reasons of all disciplines in German and English are shown on the
    display, three at a time, at 1920×1080 and 1280×720 in the default layout
    and at 1920×1080 with the lights scaled to 1.5 in a saved layout. Every
    reason is centred under its
    light, fits its box and stays within half the gap to its neighbour."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")

    for width, height, scale in ((1920, 1080, 1.0), (1280, 720, 1.0), (1920, 1080, 1.5)):
        display.set_viewport_size({"width": width, "height": height})
        if scale != 1.0:
            _scale_lights(display, scale)
        _sweep(display, DISPLAY, SHOW_ON_DISPLAY)


def test_every_reason_centered_in_judge_results_on_phones(competition):
    """All reasons of all disciplines in German and English are shown in the
    judge's results panel on 320, 375 and 412 px wide phones, three at a time.
    Every reason is centred under its light, fits its box, stays within half
    the gap to its neighbour, and long German words break only at their soft
    hyphens (so a new long reason without one fails here)."""
    head = competition.create_session_and_join_head()
    for width in (320, 375, 412):
        head.set_viewport_size({"width": width, "height": 800})
        _sweep(head, JUDGE, SHOW_ON_JUDGE)
