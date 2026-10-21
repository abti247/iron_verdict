"""Demo guide — audience terms are translated and the rulebook link follows the language."""

from urllib.parse import urlsplit

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


GUIDE_IMAGES = ("judge-reason", "result-reasons", "layout-editor")


def test_demo_guide_shows_screenshots_per_language_from_same_origin(page, server_url):
    """Open the demo guide in German: the three screenshots (chief referee
    picking a reason, display result with reasons, layout editor) are shown,
    loaded from the German image folder of the app itself, and the short notes
    on display customisation and the stream overlay point to the "?". Switch
    to English: the same images come from the English folder. No request
    leaves the app's origin."""
    origin = urlsplit(server_url).netloc
    foreign = []
    page.on("request", lambda r: urlsplit(r.url).netloc != origin and foreign.append(r.url))
    page.goto(server_url)
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )
    screen = page.get_by_test_id('demo-intro-screen')
    images = screen.locator('.demo-guide-figure img')

    for lang, button, note_texts in (
        ('Deutsch', 'Demo starten', ['Layout bearbeiten', 'Stream-Overlay (OBS)']),
        ('English', 'Start Demo', ['Edit layout', 'Stream overlay (OBS)']),
    ):
        page.locator('.lang-option', has_text=lang).click()
        page.get_by_role('button', name=button).click()
        expect(screen).to_be_visible()

        folder = 'de' if lang == 'Deutsch' else 'en'
        expect(images).to_have_count(len(GUIDE_IMAGES))
        for i, motif in enumerate(GUIDE_IMAGES):
            img = images.nth(i)
            expect(img).to_be_visible()
            expect(img).to_have_attribute('src', f'/static/img/guide/{folder}/{motif}.webp')
            expect(img).not_to_have_attribute('alt', '')
            img.scroll_into_view_if_needed()
            page.wait_for_function('(img) => img.complete && img.naturalWidth > 0', arg=img.element_handle())

        notes = screen.get_by_test_id('demo-guide-display-notes').locator('li')
        expect(notes).to_have_count(len(note_texts))
        for note, text in zip(notes.all(), note_texts):
            expect(note).to_contain_text(text)
            expect(note).to_contain_text('?')

        page.get_by_role('button', name='Zurück zum Start' if lang == 'Deutsch' else 'Back to Start').click()

    # Analytics is the only foreign host the app may try (deferred, see test_offline_assets).
    assert [u for u in foreign if 'umami' not in u] == []
