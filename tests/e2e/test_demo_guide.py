"""Demo guide — audience terms are translated and the rulebook link follows the language."""

from playwright.sync_api import expect

BVDK_RULES_URL = "https://bvdk.de/regelwerk"
IPF_RULES_URL = "https://www.powerlifting.sport/rules/codes/info/technical-rules"


def _assert_rulebook_link(link, href):
    expect(link).to_have_attribute('href', href)
    expect(link).to_have_attribute('target', '_blank')
    expect(link).to_have_attribute('rel', 'noopener noreferrer')


def test_demo_guide_translates_terms_and_links_rulebook(page, server_url):
    """Switch the landing page to German and open the demo guide: the "Why Iron
    Verdict?" terms are German and the rulebook link opens bvdk.de in a new tab.
    Go back, switch to English and reopen the guide: the terms are English and
    the link opens the IPF technical rules page."""
    page.goto(server_url)
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )
    screen = page.get_by_test_id('demo-intro-screen')
    terms = screen.locator('.demo-guide-list .text-em')

    page.locator('.lang-option', has_text='Deutsch').click()
    page.get_by_role('button', name='Demo starten').click()
    expect(screen).to_be_visible()

    expect(terms).to_have_text(['Athlet:innen', 'Publikum', 'Kampfrichter:innen', 'Jury'])
    _assert_rulebook_link(
        screen.get_by_role('link', name='technischen Regelwerk der IPF'), BVDK_RULES_URL
    )
    expect(screen.locator('.demo-guide-text')).to_contain_text('gültig ab 1. März 2026')

    page.get_by_role('button', name='Zurück zum Start').click()
    page.locator('.lang-option', has_text='English').click()
    page.get_by_role('button', name='Start Demo').click()
    expect(screen).to_be_visible()

    expect(terms).to_have_text(['Athletes', 'Audience', 'Judges', 'Jury'])
    _assert_rulebook_link(
        screen.get_by_role('link', name='IPF technical rulebook'), IPF_RULES_URL
    )
    expect(screen.locator('.demo-guide-text')).to_contain_text('effective 1 March 2026')
