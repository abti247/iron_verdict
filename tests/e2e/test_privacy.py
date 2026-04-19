"""Privacy notice screen — navigate via footer link, verify content, return to landing."""

from playwright.sync_api import expect


def test_privacy_screen(page, server_url):
    """Click the discreet privacy footer link on the landing screen,
    verify the privacy notice content is shown (including the 'Railway'
    hosting reference unique to this screen), then confirm the back
    button returns to the landing screen."""
    page.goto(server_url)

    # Privacy link must be present on the landing screen
    privacy_link = page.locator(".privacy-link")
    expect(privacy_link).to_be_visible()

    # Navigate to the privacy screen
    privacy_link.click()

    # Unique content only on the privacy screen
    expect(page.locator(".privacy-list")).to_be_visible()
    expect(page.get_by_text("Railway")).to_be_visible()

    # Back button must return to the landing screen
    # Scope to the visible privacy screen container to avoid strict-mode violations
    # (multiple "Back" buttons exist across all screens in the DOM)
    privacy_screen = page.locator(".landing-wrap", has=page.locator(".privacy-list"))
    privacy_screen.locator("button", has_text="Back").click()
    expect(page.locator('[x-model="newSessionName"]')).to_be_visible()
