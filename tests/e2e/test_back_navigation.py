"""Back navigation — clickable display header, browser back, swipe-back."""

from playwright.sync_api import expect


def test_display_session_name_is_clickable_returns_to_role_select(competition):
    """Clicking the session name on the display screen returns to role-select."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")

    display.locator(".display-tag .code-link").click()

    expect(display.locator(".role-wrap")).to_be_visible()
    expect(display.locator(".display-full")).not_to_be_visible()


def test_judge_browser_back_returns_to_role_select(competition):
    """Pressing the browser back button on the judge screen returns to role-select."""
    head = competition.create_session_and_join_head()

    head.go_back()

    expect(head.locator(".role-wrap")).to_be_visible()
    expect(head.locator(".judge-wrap")).not_to_be_visible()
