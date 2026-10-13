"""Reload recovery — a reloaded judge, display or role-select page shows a
"Connecting…" state until the right screen is back; the landing screen never
appears in between.

A recorder (init script, runs before the app) notes every screen that becomes
visible — on each MutationObserver callback and each rendered frame — so a test
can prove that no frame ever showed the landing screen.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH, join_with_network_switch
from tests.e2e.test_vportal_integration import _connect_and_open_display

RECORD_SCREENS = """
window.__screens = [];
(function () {
    function record() {
        if (!document.body) return;
        for (const el of document.body.children) {
            const testId = el.getAttribute('data-testid');
            if (!testId || el.getClientRects().length === 0) continue;
            const name = testId.replace(/-screen$/, '');
            if (window.__screens[window.__screens.length - 1] !== name) window.__screens.push(name);
        }
    }
    new MutationObserver(record).observe(document, {
        subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class'],
    });
    (function sample() { record(); requestAnimationFrame(sample); })();
})();
"""

LANDING = "landing-screen"
RECONNECTING = "reconnecting-screen"


def _recorded_page(competition, *init_scripts):
    ctx = competition.new_context()
    for script in init_scripts:
        ctx.add_init_script(script)
    ctx.add_init_script(RECORD_SCREENS)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    return page


def _join(competition, page, role):
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    if role:
        page.locator(".role-btn", has_text=competition.ROLE_LABELS[role]).click()


def _screens(page):
    return page.evaluate("window.__screens")


def test_judge_reload_never_shows_landing(competition):
    """A judge reloads mid-competition: no frame shows the landing screen, the
    judge screen comes back. (Voting after a reload: test_judge_reconnection.py.)"""
    competition.create_session_and_join_head()
    left = _recorded_page(competition)
    _join(competition, left, "left_judge")
    left.locator(".judge-wrap").wait_for(state="visible")

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")

    assert "landing" not in _screens(left), _screens(left)


def test_display_reload_never_shows_landing(competition):
    """A display reloads: no frame shows the landing screen, the display screen
    comes back. (Results after a reload: test_display_resilience.py.)"""
    competition.create_session_and_join_head()
    display = _recorded_page(competition)
    _join(competition, display, "display")
    display.locator(".display-full").wait_for(state="visible")

    display.reload()
    display.locator(".display-full").wait_for(state="visible")

    assert "landing" not in _screens(display), _screens(display)


def test_vportal_display_reload_restarts_polling(competition, server_url, fake_vportal_url):
    """A display connected to (fake) VPortal reloads: no frame shows the landing
    screen or the VPortal login dialog, and the lifter overlay is filled again by
    the polling that restarts after the rejoin."""
    page = _recorded_page(competition)
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.reload()
    page.locator(".display-full").wait_for(state="visible")

    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    assert "landing" not in _screens(page), _screens(page)
    assert "vportalModalOpen" not in _screens(page), _screens(page)


def test_role_select_reload_never_shows_landing(competition):
    """Reloading on role-select (session code stored, no role yet) shows the
    connecting state, then role-select — never the landing screen."""
    competition.create_session_and_join_head()
    page = _recorded_page(competition)
    _join(competition, page, None)

    page.reload()
    page.locator(".role-wrap").wait_for(state="visible")

    assert "landing" not in _screens(page), _screens(page)


def test_reconnecting_state_shown_while_server_unreachable(competition):
    """The judge reloads while the connection is down: the "Connecting…" state
    with the session code stays visible (not the landing screen) until the
    connection is back, then the judge screen appears and the judge can vote."""
    competition.create_session_and_join_head()
    competition.join_as("right_judge")
    left = join_with_network_switch(competition, "left_judge")
    left.context.add_init_script(RECORD_SCREENS)

    left.evaluate("window.__ivCutNetwork()")
    left.reload()

    reconnecting = left.get_by_test_id(RECONNECTING)
    expect(reconnecting).to_be_visible()
    expect(reconnecting).to_contain_text(competition.session_code)
    # Several failed attempts later the page still waits — no fallback to landing.
    left.wait_for_function("window.__ivSocketCount() >= 3", timeout=10000)
    expect(reconnecting).to_be_visible()

    left.evaluate("window.__ivRestoreNetwork()")
    left.locator(".judge-wrap").wait_for(state="visible", timeout=8000)

    assert "landing" not in _screens(left), _screens(left)
    competition.vote_all_white()
    expect(left.locator(".locked-status")).to_be_visible()


def test_cancel_reconnecting_returns_to_landing_and_forgets_session(competition):
    """While "Connecting…" is shown, Cancel leads to the landing screen and
    removes the stored session, so a further reload stays on landing."""
    competition.create_session_and_join_head()
    left = _recorded_page(competition, NETWORK_SWITCH)
    _join(competition, left, "left_judge")
    left.locator(".judge-wrap").wait_for(state="visible")

    left.evaluate("window.__ivCutNetwork()")
    left.reload()
    expect(left.get_by_test_id(RECONNECTING)).to_be_visible()

    left.get_by_test_id(RECONNECTING).get_by_role("button", name="Cancel").click()

    expect(left.get_by_test_id(LANDING)).to_be_visible()
    assert left.evaluate("sessionStorage.getItem('iv_session')") is None
    left.evaluate("window.__ivRestoreNetwork()")
    left.reload()
    expect(left.get_by_test_id(LANDING)).to_be_visible()
    expect(left.locator(".judge-wrap")).not_to_be_visible()


def test_cancel_during_role_select_lookup_is_not_undone(competition):
    """Reload on role-select; the session lookup hangs (slow venue Wi-Fi, held
    with page.route — no sleep) and the user presses Cancel. When the lookup
    answers afterwards, the page stays on landing and the session stays forgotten."""
    competition.create_session_and_join_head()
    page = _recorded_page(competition)
    _join(competition, page, None)

    lookup = re.compile(r"/api/sessions/[A-Z0-9]{8}$")
    held = []
    page.route(lookup, lambda route: held.append(route))
    with page.expect_request(lookup):
        page.reload()
    expect(page.get_by_test_id(RECONNECTING)).to_be_visible()
    assert held, "session lookup was not held"

    page.get_by_test_id(RECONNECTING).get_by_role("button", name="Cancel").click()
    expect(page.get_by_test_id(LANDING)).to_be_visible()

    held[0].continue_()
    # joinChecking is reset only after the lookup result has been handled.
    page.wait_for_function("!Alpine.$data(document.body).joinChecking")

    expect(page.get_by_test_id(LANDING)).to_be_visible()
    expect(page.locator(".join-error")).to_be_hidden()
    expect(page.locator(".role-wrap")).not_to_be_visible()
    assert page.evaluate("sessionStorage.getItem('iv_session')") is None


def test_reload_into_ended_session_shows_landing_with_message(competition):
    """The judge's page is gone while the head judge ends the session. Opening
    the app again in the same tab tries to restore the session and then shows
    the landing screen with an inline message — no popup."""
    head = competition.create_session_and_join_head()
    left = _recorded_page(competition)
    dialogs = []
    left.on("dialog", lambda d: dialogs.append(d.message))
    _join(competition, left, "left_judge")
    left.locator(".judge-wrap").wait_for(state="visible")

    left.goto("about:blank")
    head.get_by_role("button", name="End Session").click()
    expect(head.get_by_role("button", name="Create New Session")).to_be_visible()

    left.goto(competition.url)

    expect(left.get_by_test_id(LANDING)).to_be_visible()
    expect(left.locator(".join-error")).to_contain_text("has ended or expired")
    expect(left.locator(".join-error")).to_contain_text(competition.session_code)
    assert left.evaluate("sessionStorage.getItem('iv_session')") is None
    assert dialogs == []
    assert _screens(left)[0] == "reconnecting", _screens(left)


def test_reload_on_role_select_into_ended_session_shows_landing_with_message(competition):
    """Same as above for a stored session without a role (role-select)."""
    head = competition.create_session_and_join_head()
    page = _recorded_page(competition)
    _join(competition, page, None)

    page.goto("about:blank")
    head.get_by_role("button", name="End Session").click()
    expect(head.get_by_role("button", name="Create New Session")).to_be_visible()

    page.goto(competition.url)

    expect(page.get_by_test_id(LANDING)).to_be_visible()
    expect(page.locator(".join-error")).to_contain_text("has ended or expired")
    assert page.evaluate("sessionStorage.getItem('iv_session')") is None
