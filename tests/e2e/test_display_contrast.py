"""Display contrast mode for bright halls (#105).

A switch in the display settings panel (gear or "S") turns on a high-contrast
look: full colours instead of gradients on the lights, a clear border around
them, pure white and bolder texts. The background stays black. The setting is
stored per device like the zoom and survives reload and reconnection. Without
it the display looks exactly as before.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from tests.e2e.test_vportal_integration import _connect_and_open_display

TOGGLE = "display-contrast-toggle"
CONTRAST_CLASS = re.compile(r"\bdisplay-contrast\b")

# WCAG contrast ratio of an element's text against what is behind it: its own
# background if opaque, otherwise the display background. Semi-transparent
# text colours are blended onto that background first.
CONTRAST_RATIO_JS = """(el) => {
    const parse = (c) => {
        const m = c.match(/rgba?\\(([^)]+)\\)/);
        const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number);
        return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    };
    const lum = ({ r, g, b }) => {
        const ch = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
    };
    const blend = (fg, bg) => ({
        r: fg.r * fg.a + bg.r * (1 - fg.a),
        g: fg.g * fg.a + bg.g * (1 - fg.a),
        b: fg.b * fg.a + bg.b * (1 - fg.a),
    });
    const style = getComputedStyle(el);
    const screenBg = parse(getComputedStyle(document.documentElement).getPropertyValue('--bg-void').trim()
        .replace(/^#(..)(..)(..)$/, (_, r, g, b) => `rgb(${parseInt(r, 16)}, ${parseInt(g, 16)}, ${parseInt(b, 16)})`));
    const ownBg = parse(style.backgroundColor);
    const bg = ownBg.a === 1 ? ownBg : screenBg;
    const fg = blend(parse(style.color), bg);
    const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    return (hi + 0.05) / (lo + 0.05);
}"""


def open_settings(page):
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()


def turn_contrast_on(page):
    open_settings(page)
    toggle = page.get_by_test_id(TOGGLE)
    expect(toggle).to_have_attribute("aria-pressed", "false")
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".display-full")).to_have_class(CONTRAST_CLASS)
    page.locator("body").press("Escape")


def vote(page, color, with_reason=False):
    page.locator(f".vote-btn.vote-{color}").click()
    if with_reason:
        page.locator(".reason-item").first.click()
    page.locator(".lock-btn").click()
    page.locator(".locked-status").wait_for(state="visible")


def contrast_of(locator):
    return locator.evaluate(CONTRAST_RATIO_JS)


def expect_red_light_with_reason_left(display):
    wrap = display.locator(".display-full .display-orb-wrap").first
    expect(wrap.locator(".display-orb")).to_have_class(re.compile(r"\bred\b"))
    expect(wrap.locator(".display-orb-card")).to_have_class(re.compile(r"\bblue\b"))
    expect(wrap.locator(".display-orb-reason")).to_be_visible()
    expect(wrap.locator(".display-orb-reason")).not_to_be_empty()


def test_contrast_mode_is_off_by_default_and_display_unchanged(competition):
    """A fresh display has the switch off, no contrast class, and the same
    colours as before the feature: dimmed reasons, grey waiting text and
    gradient lights."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    expect(display.locator(".display-full")).not_to_have_class(CONTRAST_CLASS)
    open_settings(display)
    expect(display.get_by_test_id(TOGGLE)).to_have_attribute("aria-pressed", "false")

    status = display.locator(".display-status")
    expect(status).to_have_css("color", "rgb(107, 107, 107)")
    expect(display.locator(".display-timer-big")).to_have_css("color", "rgb(212, 212, 212)")
    expect(display.locator(".display-full .display-orb").first).to_have_css("border-top-width", "3px")


def test_contrast_mode_survives_reload_and_shows_lights_and_reasons(competition):
    """Turn contrast on → reload the display → still on (switch and look);
    then a lift with a blue card and a reason, white and yellow: the display
    shows the red light with the card and reason and "No Lift" as usual."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    turn_contrast_on(display)

    display.reload()
    display.locator(".display-full").wait_for(state="visible", timeout=10000)
    expect(display.locator(".display-full")).to_have_class(CONTRAST_CLASS)
    open_settings(display)
    expect(display.get_by_test_id(TOGGLE)).to_have_attribute("aria-pressed", "true")
    display.locator("body").press("Escape")

    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "yellow")

    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")
    expect_red_light_with_reason_left(display)
    # Lights get full colours and a clear border.
    red_orb = display.locator(".display-full .display-orb.red").first
    expect(red_orb).to_have_css("background-image", "none")
    assert float(red_orb.evaluate("el => parseFloat(getComputedStyle(el).borderTopWidth)")) > 3


def test_contrast_mode_can_be_turned_off_again(competition):
    """On → off: the class is gone and stays gone after a reload."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")
    turn_contrast_on(display)
    open_settings(display)
    display.get_by_test_id(TOGGLE).click()
    expect(display.get_by_test_id(TOGGLE)).to_have_attribute("aria-pressed", "false")
    expect(display.locator(".display-full")).not_to_have_class(CONTRAST_CLASS)

    display.reload()
    display.locator(".display-full").wait_for(state="visible", timeout=10000)
    expect(display.locator(".display-full")).not_to_have_class(CONTRAST_CLASS)


def test_contrast_mode_texts_reach_wcag_aaa(competition):
    """With contrast on, every display text reaches at least 7:1 against its
    background: session tag, timer (running and expired), waiting text,
    reasons, "Good Lift" and "No Lift"."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    turn_contrast_on(display)

    for selector in (".display-tag .code-link", ".display-timer-big", ".display-status"):
        assert contrast_of(display.locator(selector)) >= 7, selector

    vote(head, "white")
    vote(left, "white")
    vote(right, "white")
    stamp = display.locator(".verdict-stamp")
    expect(stamp).to_have_text("Good Lift")
    assert contrast_of(stamp) >= 7, "Good Lift"

    head.get_by_role("button", name="Next Lift").click()
    expect(display.locator(".display-status")).to_be_visible()

    vote(head, "red", with_reason=True)
    vote(left, "red", with_reason=True)
    vote(right, "white")
    expect(stamp).to_have_text("No Lift")
    assert contrast_of(stamp) >= 7, "No Lift"
    reason = display.locator(".display-full .display-orb-reason").first
    expect(reason).to_be_visible()
    assert contrast_of(reason) >= 7, "reason"

    display.locator(".display-timer-big").evaluate("el => el.classList.add('expired')")
    assert contrast_of(display.locator(".display-timer-big")) >= 7, "expired timer"


def test_contrast_mode_survives_connection_loss(competition):
    """Contrast on → the display's connection drops and comes back → still
    on, and the next lift's lights still arrive."""
    head, left, right = competition.join_all_judges()
    display = join_with_network_switch(competition, "display")
    turn_contrast_on(display)

    cut_network(display, conn_dot=".display-tag .conn-dot")
    expect(display.locator(".display-full")).to_have_class(CONTRAST_CLASS)
    restore_network(display)
    expect(display.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"), timeout=15000)
    expect(display.locator(".display-full")).to_have_class(CONTRAST_CLASS)

    vote(head, "white")
    vote(left, "blue", with_reason=True)
    vote(right, "white")
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect_red_light_with_reason_left(display)


def test_contrast_mode_vportal_corners_reach_wcag_aaa(page, server_url, fake_vportal_url):
    """With a VPortal lifter on the display and contrast on, name, club line,
    discipline/attempt and weight in the corners reach at least 7:1."""
    _connect_and_open_display(page, server_url, fake_vportal_url)
    expect(page.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    turn_contrast_on(page)
    for selector in (".vportal-corner-name", ".vportal-corner-meta",
                     ".vportal-corner-disc", ".vportal-corner-weight"):
        assert contrast_of(page.locator(selector)) >= 7, selector
