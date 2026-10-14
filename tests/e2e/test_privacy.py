"""Privacy & legal notice screen — navigate via footer link, verify content, return to landing."""

from playwright.sync_api import expect


def _wait_for_i18n(page):
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )


def test_privacy_screen(page, server_url):
    """Click the discreet "Privacy & Legal Notice" footer link on the landing
    screen, verify the privacy notice content is shown (including the
    'Railway' hosting reference unique to this screen), then confirm the
    back button returns to the landing screen."""
    page.goto(server_url)
    _wait_for_i18n(page)

    # Privacy link must be present on the landing screen
    privacy_link = page.locator(".privacy-link")
    expect(privacy_link).to_have_text("Privacy & Legal Notice")

    # Navigate to the privacy screen
    privacy_link.click()

    # Unique content only on the privacy screen
    expect(page.locator(".privacy-list")).to_be_visible()
    expect(page.get_by_text("Railway")).to_be_visible()

    # Back button must return to the landing screen
    # Scope to the visible privacy screen container to avoid strict-mode violations
    # (multiple "Back" buttons exist across all screens in the DOM)
    privacy_screen = page.get_by_test_id("privacy-screen")
    privacy_screen.locator("button", has_text="Back").click()
    expect(page.get_by_test_id("session-name-input")).to_be_visible()


def test_legal_notice_in_german_and_english(page, server_url):
    """Switch the landing page to German, open "Datenschutz & Impressum" and
    verify the German headings, name, postal address, the no-parcels note and
    the e-mail address as a mailto: link. Go back, switch to English, reopen
    the screen and verify the English headings and note; "Back" returns to
    the landing screen."""
    page.goto(server_url)
    _wait_for_i18n(page)

    # German
    page.locator(".lang-option", has_text="Deutsch").click()
    privacy_link = page.locator(".privacy-link")
    expect(privacy_link).to_have_text("Datenschutz & Impressum")
    privacy_link.click()

    screen = page.get_by_test_id("privacy-screen")
    expect(screen.locator(".brand-iron")).to_have_text("Datenschutz & Impressum")
    expect(screen.locator(".legal-heading")).to_have_text(["Datenschutz", "Impressum"])

    notice = screen.get_by_test_id("legal-notice")
    expect(notice).to_contain_text("Alexander Becela")
    expect(notice).to_contain_text("c/o POSTFLEX PFX-294-418")
    expect(notice).to_contain_text("Emsdettener Straße 10")
    expect(notice).to_contain_text("48268 Greven")
    expect(notice).to_contain_text("Bitte keine Pakete oder Päckchen an diese Anschrift senden.")

    email = notice.locator("a", has_text="iron.verdict.judging@gmail.com")
    expect(email).to_be_visible()
    expect(email).to_have_attribute("href", "mailto:iron.verdict.judging@gmail.com")

    screen.locator("button", has_text="Zurück").click()
    expect(page.get_by_test_id("session-name-input")).to_be_visible()

    # English
    page.locator(".lang-option", has_text="English").click()
    expect(privacy_link).to_have_text("Privacy & Legal Notice")
    privacy_link.click()

    expect(screen.locator(".brand-iron")).to_have_text("Privacy & Legal Notice")
    expect(screen.locator(".legal-heading")).to_have_text(["Privacy", "Legal Notice"])
    expect(notice).to_contain_text("Please do not send parcels or packages to this address.")
    expect(notice.locator("a[href='mailto:iron.verdict.judging@gmail.com']")).to_be_visible()

    screen.locator("button", has_text="Back").click()
    expect(page.get_by_test_id("session-name-input")).to_be_visible()
