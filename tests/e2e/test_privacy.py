"""Privacy & legal notice screen — navigate via footer link, verify content in
both languages, return to landing; the language choice survives a reload."""

from playwright.sync_api import expect


def _wait_for_i18n(page):
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )


def test_privacy_and_legal_notice_in_english_and_german(page, server_url):
    """The landing page loads in English. Click the discreet "Privacy & Legal
    Notice" footer link and verify the English notice (the 'Railway' hosting
    reference unique to this screen, the Grafana Labs log copy without IP
    addresses, headings, no-parcels note, mailto: link); "Back" returns to the
    landing screen. Switch to German: the page changes at once and stays German
    after a reload (choice kept in localStorage). Open "Datenschutz &
    Impressum" and verify the German headings, the Grafana Labs log entry,
    name, postal address, the no-parcels note and the e-mail address as a
    mailto: link; "Zurück" returns to the landing screen."""
    page.goto(server_url)
    _wait_for_i18n(page)

    # Baseline: English (navigator.language = 'en-US', no localStorage entry)
    expect(page.get_by_role("button", name="Create New Session")).to_be_visible()
    privacy_link = page.locator(".privacy-link")
    expect(privacy_link).to_have_text("Privacy & Legal Notice")

    # English
    privacy_link.click()

    # Unique content only on the privacy screen
    screen = page.get_by_test_id("privacy-screen")
    notice = screen.get_by_test_id("legal-notice")
    expect(page.locator(".privacy-list")).to_be_visible()
    expect(page.get_by_text("Railway")).to_be_visible()
    expect(page.get_by_text("without IP addresses is stored for up to 14 days with Grafana Labs")).to_be_visible()
    expect(screen.locator(".brand-iron")).to_have_text("Privacy & Legal Notice")
    expect(screen.locator(".legal-heading")).to_have_text(["Privacy", "Legal Notice"])
    expect(notice).to_contain_text("Please do not send parcels or packages to this address.")
    expect(notice.locator("a[href='mailto:iron.verdict.judging@gmail.com']")).to_be_visible()

    # Back button must return to the landing screen
    # Scope to the visible privacy screen container to avoid strict-mode violations
    # (multiple "Back" buttons exist across all screens in the DOM)
    screen.locator("button", has_text="Back").click()
    expect(page.get_by_test_id("session-name-input")).to_be_visible()

    # German: strings update immediately and survive a reload
    page.locator(".lang-option", has_text="Deutsch").click()
    expect(page.get_by_role("button", name="Neue Sitzung erstellen")).to_be_visible()
    expect(privacy_link).to_have_text("Datenschutz & Impressum")

    page.reload()
    _wait_for_i18n(page)
    expect(page.get_by_role("button", name="Neue Sitzung erstellen")).to_be_visible()
    expect(privacy_link).to_have_text("Datenschutz & Impressum")

    privacy_link.click()

    expect(screen.locator(".brand-iron")).to_have_text("Datenschutz & Impressum")
    expect(screen.locator(".legal-heading")).to_have_text(["Datenschutz", "Impressum"])

    expect(screen.locator(".privacy-list")).to_contain_text("ohne IP-Adressen")
    expect(screen.locator(".privacy-list")).to_contain_text("Grafana Labs")

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
