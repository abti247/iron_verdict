"""Screen Wake Lock (#235) — the judge and display screens ask the browser to
keep the screen on, again after a reload, and give the lock back when the
device leaves the screen.

The real API cannot show a screen that stays on, so an init script (runs
before the app) replaces ``navigator.wakeLock`` with a recorder: ``requests``
counts calls to ``request('screen')``, ``held`` the locks not yet released.
When to re-request after a tab switch and the unsupported/refused cases are
pinned down in ``tests/js/wakeLock.test.js``.
"""

from playwright.sync_api import expect

STUB_WAKE_LOCK = """
window.__wakeLock = { requests: 0, held: 0 };
(function () {
    const state = window.__wakeLock;
    Object.defineProperty(navigator, 'wakeLock', {
        configurable: true,
        value: {
            request(type) {
                state.requests += 1;
                state.held += 1;
                const sentinel = new EventTarget();
                sentinel.type = type;
                sentinel.released = false;
                sentinel.release = async () => {
                    if (sentinel.released) return;
                    sentinel.released = true;
                    state.held -= 1;
                    sentinel.dispatchEvent(new Event('release'));
                };
                return Promise.resolve(sentinel);
            },
        },
    });
})();
"""


def _stubbed_page(competition):
    ctx = competition.new_context()
    ctx.add_init_script(STUB_WAKE_LOCK)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    return page


def _join(competition, page, role):
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text=competition.ROLE_LABELS[role]).click()


def _wake_lock(page):
    return page.evaluate("({ ...window.__wakeLock })")


def _expect_held(page, requests):
    page.wait_for_function(
        f"window.__wakeLock.held === 1 && window.__wakeLock.requests === {requests}"
    )


def test_judge_screen_keeps_screen_awake_across_reload(competition):
    """A side judge joins: the screen wake lock is requested and held. On the
    landing and role-select screens before, none was requested. After a reload
    the restored judge screen requests it again; tapping the session code back
    to role selection releases it."""
    competition.create_session_and_join_head()
    left = _stubbed_page(competition)
    left.goto(competition.url)
    left.get_by_test_id("join-code-input").fill(competition.session_code)
    left.get_by_role("button", name="Join Session").click()
    left.locator(".role-wrap").wait_for(state="visible")
    assert _wake_lock(left) == {"requests": 0, "held": 0}

    left.locator(".role-btn", has_text=competition.ROLE_LABELS["left_judge"]).click()
    left.locator(".judge-wrap").wait_for(state="visible")
    _expect_held(left, requests=1)

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")
    _expect_held(left, requests=1)  # counters restart with the reloaded page

    left.locator(".judge-wrap .code-link").click()
    left.locator(".role-wrap").wait_for(state="visible")
    left.wait_for_function("window.__wakeLock.held === 0")


def test_display_keeps_screen_awake_across_reload(competition):
    """A display joins: the screen wake lock is requested and held, again after
    a reload; going back to role selection via the session name releases it."""
    competition.create_session_and_join_head()
    display = _stubbed_page(competition)
    _join(competition, display, "display")
    display.locator(".display-full").wait_for(state="visible")
    _expect_held(display, requests=1)

    display.reload()
    display.locator(".display-full").wait_for(state="visible")
    _expect_held(display, requests=1)

    display.locator(".display-full .code-link").click()
    expect(display.locator(".role-wrap")).to_be_visible()
    display.wait_for_function("window.__wakeLock.held === 0")
