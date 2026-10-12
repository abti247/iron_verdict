"""Reload recovery — a reloaded judge, display or role-select page shows a
"Connecting…" state until the right screen is back; the landing screen never
appears in between.

A recorder (init script, runs before the app) notes every screen that becomes
visible — on each MutationObserver callback and each rendered frame — so a test
can prove that no frame ever showed the landing screen.
"""

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH, join_with_network_switch

RECORD_SCREENS = """
window.__screens = [];
(function () {
    function record() {
        if (!document.body) return;
        for (const el of document.body.children) {
            const show = el.getAttribute('x-show');
            if (!show || el.getClientRects().length === 0) continue;
            const m = show.match(/screen === '([^']+)'/);
            const name = m ? m[1] : show;
            if (window.__screens[window.__screens.length - 1] !== name) window.__screens.push(name);
        }
    }
    new MutationObserver(record).observe(document, {
        subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class'],
    });
    (function sample() { record(); requestAnimationFrame(sample); })();
})();
"""

LANDING = '.landing-wrap[x-show="screen === \'landing\'"]'
RECONNECTING = '.landing-wrap[x-show="screen === \'reconnecting\'"]'


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
    page.locator('[x-model="joinCode"]').fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    if role:
        page.locator(".role-btn", has_text=competition.ROLE_LABELS[role]).click()


def _screens(page):
    return page.evaluate("window.__screens")


def test_judge_reload_never_shows_landing(competition):
    """A judge reloads mid-competition: no frame shows the landing screen, the
    judge screen comes back and the judge can still vote."""
    head = competition.create_session_and_join_head()
    left = _recorded_page(competition)
    _join(competition, left, "left_judge")
    left.locator(".judge-wrap").wait_for(state="visible")
    competition.pages["left_judge"] = left
    competition.join_as("right_judge")

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")

    assert "landing" not in _screens(left), _screens(left)
    competition.vote_all_white()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(head.locator(".locked-status")).to_be_visible()


def test_display_reload_never_shows_landing(competition):
    """A display reloads: no frame shows the landing screen, results arrive."""
    competition.join_all_judges()
    display = _recorded_page(competition)
    _join(competition, display, "display")
    display.locator(".display-full").wait_for(state="visible")

    display.reload()
    display.locator(".display-full").wait_for(state="visible")

    assert "landing" not in _screens(display), _screens(display)
    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")


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

    reconnecting = left.locator(RECONNECTING)
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
    expect(left.locator(RECONNECTING)).to_be_visible()

    left.locator(RECONNECTING).get_by_role("button", name="Cancel").click()

    expect(left.locator(LANDING)).to_be_visible()
    assert left.evaluate("sessionStorage.getItem('iv_session')") is None
    left.evaluate("window.__ivRestoreNetwork()")
    left.reload()
    expect(left.locator(LANDING)).to_be_visible()
    expect(left.locator(".judge-wrap")).not_to_be_visible()


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

    expect(left.locator(LANDING)).to_be_visible()
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

    expect(page.locator(LANDING)).to_be_visible()
    expect(page.locator(".join-error")).to_contain_text("has ended or expired")
    assert page.evaluate("sessionStorage.getItem('iv_session')") is None
