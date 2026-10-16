"""Demo launch with blocked pop-ups (issue #96) and the clickable "DEMO" label in demo windows."""

import httpx
import pytest
from playwright.sync_api import expect

# Replaces window.open before the app loads. `modes` lists the result of each
# call in order: 'open' (a live window), 'null' (blocked, as Chrome/Firefox
# report it) or 'closed' (a window a blocker closed right away). Calls beyond
# the list open normally. No real pop-up is opened.
FAKE_WINDOW_OPEN = """
(modes) => {
    window.__openCalls = [];
    window.open = (url) => {
        window.__openCalls.push(url);
        const mode = modes[window.__openCalls.length - 1] || 'open';
        if (mode === 'null') return null;
        return { closed: mode === 'closed' };
    };
}
"""


def _open_demo_guide(page, server_url, modes, language='English'):
    page.add_init_script(f"({FAKE_WINDOW_OPEN})({modes!r})")
    page.on("dialog", lambda d: d.accept())
    page.goto(server_url)
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )
    page.locator('.lang-option', has_text=language).click()
    page.get_by_test_id('landing-screen').locator('.btn-blood-ghost').filter(
        has_text='Demo' if language == 'Deutsch' else 'Start Demo'
    ).click()
    screen = page.get_by_test_id('demo-intro-screen')
    expect(screen).to_be_visible()
    return screen


def test_demo_all_windows_open_shows_running_message(page, server_url):
    """All four window.open calls return a live window: the guide shows
    "Demo running" and no pop-up hint, as before the fix."""
    screen = _open_demo_guide(page, server_url, [])

    screen.get_by_role('button', name='Launch Demo').click()

    expect(screen.get_by_test_id('demo-running')).to_be_visible()
    expect(screen.get_by_test_id('demo-popups-blocked')).to_be_hidden()
    assert page.evaluate('window.__openCalls.length') == 4


def test_demo_partially_blocked_shows_both_ways_out(page, server_url):
    """Only the first window opens (window.open returns null from the second
    call on, like a pop-up blocker): no "Demo running" message; the hint names
    both ways out — allow pop-ups and relaunch, or click "DEMO" in the open
    window. The launch button stays usable; a relaunch with all four windows
    open replaces the hint with "Demo running"."""
    screen = _open_demo_guide(page, server_url, ['open', 'null', 'null', 'null'])

    screen.get_by_role('button', name='Launch Demo').click()

    hint = screen.get_by_test_id('demo-popups-blocked')
    expect(hint).to_be_visible()
    expect(hint).to_contain_text('allow pop-ups')
    expect(hint).to_contain_text('DEMO')
    expect(screen.get_by_test_id('demo-running')).to_be_hidden()

    page.evaluate("""() => {
        window.open = (url) => { window.__openCalls.push(url); return { closed: false }; };
    }""")
    screen.get_by_role('button', name='Launch Demo').click()
    expect(screen.get_by_test_id('demo-running')).to_be_visible()
    expect(hint).to_be_hidden()


def test_demo_all_blocked_shows_allow_popups_hint_in_german(page, server_url):
    """Every window.open returns null (German UI): the hint only asks to allow
    pop-ups and relaunch — there is no open window to click "DEMO" in — and the
    tab stays on the guide."""
    screen = _open_demo_guide(
        page, server_url, ['null', 'null', 'null', 'null'], language='Deutsch'
    )

    screen.get_by_role('button', name='Demo starten').click()

    hint = screen.get_by_test_id('demo-popups-blocked')
    expect(hint).to_be_visible()
    expect(hint).to_contain_text('Pop-ups für diese Seite erlauben')
    expect(hint).not_to_contain_text('DEMO')
    expect(screen.get_by_test_id('demo-running')).to_be_hidden()


def test_demo_window_closed_immediately_counts_as_blocked(page, server_url):
    """A blocker that returns a window object but has already closed it
    (win.closed === true) counts as blocked, same as null."""
    screen = _open_demo_guide(page, server_url, ['open', 'open', 'closed', 'open'])

    screen.get_by_role('button', name='Launch Demo').click()

    expect(screen.get_by_test_id('demo-popups-blocked')).to_contain_text('DEMO')
    expect(screen.get_by_test_id('demo-running')).to_be_hidden()


def _demo_session_code(server_url, created_sessions):
    response = httpx.post(f"{server_url}/api/sessions", json={"name": "Demo"})
    response.raise_for_status()
    code = response.json()["session_code"]
    created_sessions.append(code)
    return code


@pytest.mark.parametrize("role, screen_selector, label_selector", [
    ("left_judge", ".judge-wrap", ".judge-code .code-link"),
    ("display", ".display-full", ".display-tag .code-link"),
])
def test_demo_window_shows_clickable_demo_label(competition, server_url, created_sessions, role, screen_selector, label_selector):
    """A demo window (?code=…&demo=<role>) shows "DEMO" instead of the session
    code (judge) or session name (display), also after a reload. Clicking
    "DEMO" opens the role selection, which still shows the real code for a
    second device; after a reload there, picking another role shows "DEMO"
    again."""
    code = _demo_session_code(server_url, created_sessions)
    page = competition.new_context().new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(f"{server_url}/?code={code}&demo={role}")

    label = page.locator(label_selector)
    expect(page.locator(screen_selector)).to_be_visible()
    expect(label).to_have_text('DEMO')

    page.reload()
    expect(page.locator(screen_selector)).to_be_visible()
    expect(label).to_have_text('DEMO')

    label.click()
    expect(page.locator('.role-wrap')).to_be_visible()
    expect(page.locator('.session-tag .code')).to_have_text(code)

    page.reload()
    expect(page.locator('.role-wrap')).to_be_visible()
    page.locator('.role-btn', has_text='Right').click()
    expect(page.locator('.judge-wrap')).to_be_visible()
    expect(page.locator('.judge-code .code-link')).to_have_text('DEMO')


def test_regular_session_judge_still_shows_session_code(competition):
    """Outside the demo the judge screen keeps showing the session code."""
    head = competition.create_session_and_join_head()

    expect(head.locator('.judge-code .code-link')).to_have_text(competition.session_code)
