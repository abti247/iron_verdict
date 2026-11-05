"""Demo guide — audience terms are translated and the rulebook link follows the language."""

from urllib.parse import urlsplit

from playwright.sync_api import expect

BVDK_RULES_URL = "https://bvdk.de/regelwerk"
IPF_RULES_URL = "https://www.powerlifting.sport/rules/codes/info/technical-rules"


def _assert_rulebook_link(link, href):
    expect(link).to_have_attribute('href', href)
    expect(link).to_have_attribute('target', '_blank')
    expect(link).to_have_attribute('rel', 'noopener noreferrer')


GUIDE_IMAGES = ("judge-reason", "result-reasons", "layout-editor")


def test_demo_guide_per_language(page, server_url):
    """Open the demo guide in German: the "Why Iron Verdict?" terms are German,
    the rulebook link opens bvdk.de in a new tab, the three screenshots (chief
    referee picking a reason, display result with reasons, layout editor) are
    shown, loaded from the German image folder of the app itself, and the
    short notes on display customisation, breaks and the stream overlay point
    to the "?". Go back, switch to English: the terms are English, the link
    opens the IPF technical rules page and the same images come from the
    English folder. No request leaves the app's origin."""
    origin = urlsplit(server_url).netloc
    foreign = []
    page.on("request", lambda r: urlsplit(r.url).netloc != origin and foreign.append(r.url))
    page.goto(server_url)
    page.wait_for_function(
        '() => typeof window.Alpine !== "undefined" && window.Alpine.store("i18n") != null'
    )
    screen = page.get_by_test_id('demo-intro-screen')
    terms = screen.locator('.demo-guide-list .text-em')
    images = screen.locator('.demo-guide-figure img')

    for lang, button, term_texts, link_name, link_href, effective, note_texts, back in (
        ('Deutsch', 'Demo starten', ['Athlet:innen', 'Publikum', 'Kampfrichter:innen', 'Jury'],
         'technischen Regelwerk der IPF', BVDK_RULES_URL, 'gültig ab 1. März 2026',
         ['Layout bearbeiten', 'Pause starten', 'Stream-Overlay (OBS)'], 'Zurück zum Start'),
        ('English', 'Start Demo', ['Athletes', 'Audience', 'Judges', 'Jury'],
         'IPF technical rulebook', IPF_RULES_URL, 'effective 1 March 2026',
         ['Edit layout', 'Start break', 'Stream overlay (OBS)'], 'Back to Start'),
    ):
        page.locator('.lang-option', has_text=lang).click()
        page.get_by_role('button', name=button).click()
        expect(screen).to_be_visible()

        expect(terms).to_have_text(term_texts)
        _assert_rulebook_link(screen.get_by_role('link', name=link_name), link_href)
        expect(screen.locator('.demo-guide-text')).to_contain_text(effective)

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

        page.get_by_role('button', name=back).click()

    # Analytics is the only foreign host the app may try (deferred, see test_offline_assets).
    assert [u for u in foreign if 'umami' not in u] == []
