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


def test_settings_panel_opens_and_closes(page, server_url):
    """Gear opens the settings panel, Escape closes it; the S key opens it, a
    click outside (the timer) closes it; opened again, leaving the display via
    the session-name link and re-entering finds it closed."""
    _open_display(page, server_url)
    panel = page.locator(".display-settings-panel")
    expect(panel).to_be_hidden()

    page.locator(".display-settings-gear").click()
    expect(panel).to_be_visible()
    page.locator("body").press("Escape")
    expect(panel).to_be_hidden()

    page.locator("body").press("s")
    expect(panel).to_be_visible()
    # Click on the timer area (not the panel)
    page.locator(".display-timer-big").click()
    expect(panel).to_be_hidden()

    page.locator(".display-settings-gear").click()
    expect(panel).to_be_visible()
    page.locator(".display-tag .code-link").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")
    expect(panel).to_be_hidden()
