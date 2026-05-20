"""Display screen size adjustment: gear/S key open panel, slider scales display."""

from playwright.sync_api import expect


def _open_display(page, server_url):
    page.goto(server_url + "/")
    page.locator('[x-model="newSessionName"]').fill("Sizing Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")


def _display_zoom_value(page) -> float:
    raw = page.evaluate("""() => getComputedStyle(
        document.querySelector('.display-full')
    ).getPropertyValue('--display-zoom').trim()""")
    return float(raw)


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


def test_slider_updates_display_zoom_variable(page, server_url):
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    page.locator(".display-settings-panel").wait_for(state="visible")

    slider = page.locator(".display-settings-slider")
    slider.evaluate("""(el) => {
        el.value = '1.3';
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }""")

    page.wait_for_function("""() => Math.abs(
        parseFloat(getComputedStyle(document.querySelector('.display-full'))
            .getPropertyValue('--display-zoom')) - 1.3
    ) < 0.001""")

    assert abs(_display_zoom_value(page) - 1.3) < 0.001


def test_reset_button_restores_zoom_to_default(page, server_url):
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    page.locator(".display-settings-panel").wait_for(state="visible")

    slider = page.locator(".display-settings-slider")
    slider.evaluate("""(el) => {
        el.value = '1.4';
        el.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_function("""() => Math.abs(
        parseFloat(getComputedStyle(document.querySelector('.display-full'))
            .getPropertyValue('--display-zoom')) - 1.4
    ) < 0.001""")

    page.locator(".display-settings-reset").click()
    page.wait_for_function("""() => Math.abs(
        parseFloat(getComputedStyle(document.querySelector('.display-full'))
            .getPropertyValue('--display-zoom')) - 0.8
    ) < 0.001""")

    assert abs(_display_zoom_value(page) - 0.8) < 0.001


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


def test_zoom_persists_across_reload(page, server_url):
    _open_display(page, server_url)
    page.locator(".display-settings-gear").click()
    page.locator(".display-settings-panel").wait_for(state="visible")

    slider = page.locator(".display-settings-slider")
    slider.evaluate("""(el) => {
        el.value = '1.25';
        el.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_function("""() => Math.abs(
        parseFloat(getComputedStyle(document.querySelector('.display-full'))
            .getPropertyValue('--display-zoom')) - 1.25
    ) < 0.001""")

    page.reload()
    page.locator(".display-full").wait_for(state="visible", timeout=10000)

    assert abs(_display_zoom_value(page) - 1.25) < 0.001


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
