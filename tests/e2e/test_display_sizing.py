"""Display settings panel: gear/S key open it, Escape, a click outside or
leaving the display close it. (Sizes are set per block in the layout editor,
see test_display_layout.py; the global zoom slider is gone, #106.)"""

from playwright.sync_api import expect


def _open_display(page, server_url):
    page.goto(server_url + "/")
    page.get_by_test_id("session-name-input").fill("Sizing Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")


def test_gear_icon_opens_settings_panel(page, server_url):
    _open_display(page, server_url)
    expect(page.locator(".display-settings-panel")).to_be_hidden()
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()


def test_s_key_opens_settings_panel(page, server_url):
    _open_display(page, server_url)
    expect(page.locator(".display-settings-panel")).to_be_hidden()
    page.locator("body").press("s")
    expect(page.locator(".display-settings-panel")).to_be_visible()


def test_escape_dismisses_panel(page, server_url):
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()
    page.locator("body").press("Escape")
    expect(page.locator(".display-settings-panel")).to_be_hidden()


def test_click_outside_dismisses_panel(page, server_url):
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    expect(page.locator(".display-settings-panel")).to_be_visible()
    # Click on the timer area (not the panel)
    page.locator(".display-timer-big").click()
    expect(page.locator(".display-settings-panel")).to_be_hidden()


def test_panel_closes_on_navigation_away_from_display(page, server_url):
    """Open panel → leave display via session-name link → re-enter → panel must be closed."""
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    page.locator(".display-settings-panel").wait_for(state="visible")

    page.locator(".display-tag .code-link").click()
    page.locator(".role-wrap").wait_for(state="visible")

    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")

    expect(page.locator(".display-settings-panel")).to_be_hidden()
