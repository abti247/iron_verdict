"""Session code on role select as a link (#212) — open more judges in new tabs."""

import re
from playwright.sync_api import expect


def _create_session(competition):
    """Create a session in a fresh context and stay on role select. Returns page."""
    ctx = competition.new_context()
    page = ctx.new_page()
    page.goto(competition.url)
    page.get_by_test_id("session-name-input").fill("Link Session")
    page.get_by_role("button", name="Create New Session").click()
    expect(page.get_by_test_id("role-select-screen")).to_be_visible()
    competition.session_code = page.locator(".session-tag .code").text_content()
    assert competition.session_code
    return page


def _expect_role_select_of(page, code):
    # No URL check: the app replaces ?session=… with / once it has started.
    expect(page.get_by_test_id("role-select-screen")).to_be_visible()
    expect(page.locator(".session-tag .code")).to_have_text(code)


def test_ctrl_click_opens_role_select_in_new_tab(competition):
    """Ctrl/Cmd+click on the code opens role select of the same session in a new tab.

    The link points to the QR code's URL. In the new tab the free left judge
    can be chosen while the first tab stays chief referee and sees L connected.
    """
    first = _create_session(competition)
    code = competition.session_code
    expect(first.locator(".session-tag .code")).to_have_attribute(
        "href", competition.url.rstrip("/") + "/?session=" + code
    )

    with first.context.expect_page() as new_tab_info:
        first.locator(".session-tag .code").click(modifiers=["ControlOrMeta"])
    second = new_tab_info.value
    _expect_role_select_of(second, code)

    first.on("dialog", lambda d: d.accept())
    first.locator(".role-btn", has_text="Chief Referee").click()
    expect(first.get_by_test_id("judge-screen")).to_be_visible()

    second.locator(".role-btn", has_text="Left").click()
    expect(second.get_by_test_id("judge-screen")).to_be_visible()

    expect(first.locator(".connectivity-dot", has_text="L")).to_have_class(
        re.compile(r"status-connected")
    )
    expect(first.get_by_role("button", name="Next Lift")).to_be_visible()


def test_plain_click_does_nothing_middle_click_opens_tab(competition):
    """A plain click on the code neither navigates nor opens a tab; a middle click opens one.

    The marker on ``window`` would be gone after a reload of role select; the
    click waits for any navigation it started, so checking right after it is safe.
    """
    first = _create_session(competition)
    code = competition.session_code
    first.evaluate("window.__beforeClick = true")

    first.locator(".session-tag .code").click()
    assert first.evaluate("window.__beforeClick === true")
    expect(first.get_by_test_id("role-select-screen")).to_be_visible()
    assert "session=" not in first.url

    with first.context.expect_page() as new_tab_info:
        first.locator(".session-tag .code").click(button="middle")
    _expect_role_select_of(new_tab_info.value, code)

    # Only the tab of the middle click was opened, not one from the plain click.
    assert len(first.context.pages) == 2
