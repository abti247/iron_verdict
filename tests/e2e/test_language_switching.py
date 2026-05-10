"""Language switching — UI toggle changes strings; localStorage persists the choice across reloads."""

from playwright.sync_api import expect


def test_language_switches_and_persists(page, server_url):
    """Clicking DE changes button text to German; reloading the page preserves the language via localStorage."""
    page.goto(server_url)

    # Baseline: page loads in English (navigator.language = 'en-US', no localStorage entry)
    expect(page.get_by_role('button', name='Create New Session')).to_be_visible()

    # Switch to German via the language option on the landing page
    # The landing page renders t('language.de') = 'Deutsch' for the German option
    page.locator('.lang-option', has_text='Deutsch').click()

    # Strings update immediately
    expect(page.get_by_role('button', name='Neue Sitzung erstellen')).to_be_visible()

    # Reload — localStorage now holds 'de', so the page should still be in German
    page.reload()
    expect(page.get_by_role('button', name='Neue Sitzung erstellen')).to_be_visible()
