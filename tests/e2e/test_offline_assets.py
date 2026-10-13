"""Offline venue — the app must run with every request to a foreign host blocked.

Venue Wi-Fi often has no (or very slow) internet. Alpine.js, the QR library and
the fonts are served by the app itself; these tests block every request that
does not go to the test server and check that a full competition still works.
"""

import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

# Analytics stays external on purpose (deferred, not on the critical path): it
# may be attempted and blocked, but nothing else may leave the app's origin.
ALLOWED_EXTERNAL_ATTEMPTS = {"umami-production-ca4a.up.railway.app"}


@pytest.fixture()
def offline(competition, server_url):
    """Make every context the competition opens abort requests to foreign
    hosts. Returns the list of hosts that were attempted (and blocked)."""
    origin = urlsplit(server_url).netloc
    blocked = []

    def handle(route):
        host = urlsplit(route.request.url).netloc
        if host == origin:
            route.continue_()
        else:
            blocked.append(host)
            route.abort("internetdisconnected")

    factory = competition._new_context_factory

    def offline_context(**kwargs):
        ctx = factory(**kwargs)
        ctx.route("**/*", handle)
        return ctx

    competition._new_context_factory = offline_context
    return blocked


def _fonts_loaded(page):
    return page.evaluate(
        """() => ['1em "Bebas Neue"', '400 1em "Rajdhani"', '600 1em "Rajdhani"',
                  '700 1em "Rajdhani"'].every(f => document.fonts.check(f))
                && [...document.fonts].some(f => f.family.includes('Rajdhani') && f.status === 'loaded')
                && [...document.fonts].some(f => f.family.includes('Bebas Neue') && f.status === 'loaded')"""
    )


def test_full_competition_with_external_hosts_blocked(competition, offline):
    """All foreign hosts blocked → create session (role select shows the QR
    code) → 3 judges + display join → vote → display verdict → judge reloads
    and rejoins → next lift → vote → end session. Fonts are the real faces,
    not a fallback, and no request went to a CDN or font host."""
    head = competition.create_session_and_join_head("Offline Meet")
    assert _fonts_loaded(head)

    left = competition.join_as("left_judge")
    right = competition.join_as("right_judge")

    # QR code on the role selection screen (rendered by the vendored library).
    qr_ctx = competition.new_context()
    qr_page = qr_ctx.new_page()
    qr_page.goto(competition.url)
    qr_page.get_by_test_id("join-code-input").fill(competition.session_code)
    qr_page.get_by_role("button", name="Join Session").click()
    qr_page.locator(".role-wrap").wait_for(state="visible")
    expect(qr_page.locator("#qrcode canvas")).to_have_count(1)
    expect(qr_page.locator("#qrcode img")).to_have_attribute("src", re.compile(r"^data:image/png;base64,."))

    display = competition.join_as("display")
    assert _fonts_loaded(display)

    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    # A reload must not need the internet either.
    left.reload()
    expect(left.locator(".judge-wrap")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()
    expect(left.locator(".vote-btn.vote-white")).to_be_enabled()
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "red")
    competition.vote_and_lock(right, "red")
    expect(display.locator(".verdict-stamp")).to_have_text("No Lift")

    head.get_by_role("button", name="End Session").click()
    for p in (head, left, right, display):
        expect(p.get_by_role("button", name="Create New Session")).to_be_visible(timeout=5000)

    # The analytics script is always attempted, so seeing it proves the block
    # was active — otherwise the assertion below would prove nothing.
    assert ALLOWED_EXTERNAL_ATTEMPTS & set(offline), "foreign-host block never applied"
    assert set(offline) <= ALLOWED_EXTERNAL_ATTEMPTS, offline
