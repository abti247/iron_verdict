"""End session — the head judge ends it, all get redirected, the code is gone."""

from playwright.sync_api import expect


def test_end_redirects_all_and_session_is_gone(competition):
    """Head judge ends session → all participants return to landing; joining
    with the old code afterwards shows an inline error on landing."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    code = competition.session_code

    # End session — confirmEndSession() shows confirm dialog (auto-accepted)
    # handleSessionEnded shows alert (auto-accepted)
    head.get_by_role("button", name="End Session").click()

    # All screens return to landing — check for a unique landing-screen element
    # since there are multiple .landing-wrap divs (landing, contact, demo-intro)
    for p in (head, left, right, display):
        expect(
            p.get_by_role("button", name="Create New Session")
        ).to_be_visible(timeout=5000)

    # Try to join ended session in a fresh context
    ctx = competition.new_context()
    page = ctx.new_page()
    page.goto(competition.url)

    page.get_by_test_id("join-code-input").fill(code)
    page.get_by_role("button", name="Join Session").click()

    # Lookup returns 404 → inline error shown, no navigation to role-select
    expect(page.locator(".join-error")).to_be_visible()
    expect(page.locator(".join-error")).to_contain_text("Session not found")
    expect(page.locator(".role-wrap")).not_to_be_visible()
    expect(page.locator(".judge-wrap")).not_to_be_visible()
