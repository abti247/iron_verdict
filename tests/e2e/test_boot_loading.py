"""Boot state — until Alpine has started, only a loading indicator is visible.

Alpine is loaded late on purpose (after translations and fonts, see init.js).
Until it has started, nothing of the app may be visible — in particular not the
VPortal modal, a full-screen overlay. If Alpine never starts, a bilingual
"could not be loaded" message with a reload link replaces the indicator.

The Alpine script request is held (not slowed down by a sleep) with
``page.route`` so the boot state can be inspected for as long as needed.
"""

import re

from playwright.sync_api import expect

ALPINE = re.compile(r"/static/vendor/alpinejs-[^/]*\.js$")

# Records, on every rendered frame, which top-level elements of <body> are
# visible. Lets a test prove that no frame ever showed the wrong screen.
RECORD_VISIBLE_FRAMES = """
window.__frames = [];
(function sample() {
    if (document.body) {
        const visible = [...document.body.children]
            .filter(el => el.tagName !== 'SCRIPT' && el.getClientRects().length > 0)
            .map(el => el.className.split(' ')[0]);
        const key = visible.join('+');
        if (window.__frames[window.__frames.length - 1] !== key) window.__frames.push(key);
    }
    requestAnimationFrame(sample);
})();
"""


def _hold_alpine(page):
    """Hold every request for the Alpine script until the returned release()
    is called. A request that only reaches the handler after release() passes
    at once instead of being held forever."""
    held = []
    released = False

    def handle(route):
        if released:
            route.continue_()
        else:
            held.append(route)

    page.route(ALPINE, handle)

    def release():
        nonlocal released
        assert held, "Alpine request was never made"
        released = True
        for route in held:
            route.continue_()

    return release


def _expect_only_boot_indicator(page):
    expect(page.locator(".boot-screen")).to_be_visible()
    expect(page.locator(".boot-loading")).to_be_visible()
    expect(page.get_by_text("Loading …")).to_be_visible()
    expect(page.locator(".boot-fallback")).to_be_hidden()
    expect(page.locator(".vportal-modal-backdrop")).to_be_hidden()
    expect(page.locator(".landing-wrap").first).to_be_hidden()
    visible = page.evaluate(
        """() => [...document.body.children]
                .filter(el => el.tagName !== 'SCRIPT' && el.getClientRects().length > 0)
                .map(el => el.className)"""
    )
    assert visible == ["boot-screen"], visible


def test_only_loading_indicator_visible_while_alpine_loads(competition):
    """Alpine script held → only the loading indicator is visible, never the
    VPortal modal or a screen → Alpine released → the landing screen appears
    and the indicator is gone. Every rendered frame showed either only the
    indicator or only the landing screen (no flicker of another element)."""
    page = competition.new_context().new_page()
    page.add_init_script(RECORD_VISIBLE_FRAMES)
    release = _hold_alpine(page)

    with page.expect_request(ALPINE):
        page.goto(competition.url, wait_until="commit")
    _expect_only_boot_indicator(page)

    release()
    expect(page.get_by_role("button", name="Create New Session")).to_be_visible()
    expect(page.locator(".boot-screen")).to_be_hidden()
    expect(page.locator(".vportal-modal-backdrop")).to_be_hidden()

    frames = page.evaluate("window.__frames")
    assert set(frames) <= {"", "boot-screen", "landing-wrap"}, frames
    assert frames[-1] == "landing-wrap", frames


def test_fallback_shown_immediately_when_alpine_fails_to_load(competition):
    """Alpine script request fails → the bilingual "could not be loaded"
    message appears right away (well before the 10 s timeout), the loading
    indicator is gone → the reload link reloads the page and, with the script
    reachable again, the app starts normally."""
    page = competition.new_context().new_page()
    page.route(ALPINE, lambda route: route.abort("internetdisconnected"))

    page.goto(competition.url)
    expect(page.locator(".boot-fallback")).to_be_visible(timeout=3000)
    expect(page.get_by_text("App konnte nicht geladen werden")).to_be_visible()
    expect(page.get_by_text("App could not be loaded")).to_be_visible()
    expect(page.locator(".boot-loading")).to_be_hidden()
    expect(page.locator(".vportal-modal-backdrop")).to_be_hidden()

    page.unroute(ALPINE)
    page.get_by_role("link", name="Neu laden / Reload").click()
    expect(page.get_by_role("button", name="Create New Session")).to_be_visible()
    expect(page.locator(".boot-screen")).to_be_hidden()


def test_fallback_shown_after_timeout_when_alpine_hangs(competition):
    """Alpine script request never answers → loading indicator first → after
    the 10 s timeout the "could not be loaded" message replaces it → Alpine
    finally arrives → the app starts and the message disappears."""
    page = competition.new_context().new_page()
    release = _hold_alpine(page)

    with page.expect_request(ALPINE):
        page.goto(competition.url, wait_until="commit")
    _expect_only_boot_indicator(page)

    expect(page.locator(".boot-fallback")).to_be_visible(timeout=15000)
    expect(page.get_by_text("App could not be loaded")).to_be_visible()
    expect(page.locator(".boot-loading")).to_be_hidden()

    release()
    expect(page.get_by_role("button", name="Create New Session")).to_be_visible()
    expect(page.locator(".boot-screen")).to_be_hidden()


def test_judge_reload_shows_only_loading_indicator_until_rejoined(competition):
    """Judge in a running session reloads while the Alpine script is held →
    only the loading indicator is visible (no VPortal modal, no landing
    screen) → Alpine released → the judge is back on the judge screen and can
    vote."""
    competition.join_all_judges()
    left = competition.pages["left_judge"]
    release = _hold_alpine(left)

    with left.expect_request(ALPINE):
        left.reload(wait_until="commit")
    _expect_only_boot_indicator(left)

    release()
    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".boot-screen")).to_be_hidden()
    expect(left.locator(".vportal-modal-backdrop")).to_be_hidden()
    competition.vote_all_white()
