"""E2E: invalid/unknown session codes surface as inline errors on landing, not at role-select."""

from playwright.sync_api import expect


def test_join_button_disabled_until_eight_chars(page, server_url):
    """Length gate: button stays disabled below 8 chars and enables exactly at 8."""
    page.goto(server_url)

    join_btn = page.get_by_role("button", name="Join Session")
    join_input = page.locator('[x-model="joinCode"]')

    expect(join_btn).to_be_disabled()

    join_input.fill("ABCDEFG")  # 7 chars
    expect(join_btn).to_be_disabled()

    join_input.fill("ABCDEFGH")  # 8 chars
    expect(join_btn).to_be_enabled()


def test_unknown_code_shows_inline_error_and_stays_on_landing(page, server_url):
    """8-char code for a nonexistent session: inline error, no navigation to role-select."""
    page.goto(server_url)

    page.locator('[x-model="joinCode"]').fill("ZZZZZZZZ")
    page.get_by_role("button", name="Join Session").click()

    expect(page.locator(".join-error")).to_be_visible()
    expect(page.locator(".join-error")).to_contain_text("Session not found")
    expect(page.locator(".role-wrap")).not_to_be_visible()


def test_typing_clears_inline_error(page, server_url):
    """User retry: typing after a failed lookup clears the error."""
    page.goto(server_url)

    page.locator('[x-model="joinCode"]').fill("ZZZZZZZZ")
    page.get_by_role("button", name="Join Session").click()
    expect(page.locator(".join-error")).to_be_visible()

    page.locator('[x-model="joinCode"]').fill("A")
    expect(page.locator(".join-error")).not_to_be_visible()


def test_stale_qr_code_lands_on_landing_with_error(page, server_url):
    """Scanned QR with a stale session code: pre-fill input, show inline error, no role-select."""
    page.goto(f"{server_url}/?session=YYYYYYYY")

    expect(page.locator(".landing-wrap")).to_be_visible()
    expect(page.locator('[x-model="joinCode"]')).to_have_value("YYYYYYYY")
    expect(page.locator(".join-error")).to_be_visible()
    expect(page.locator(".role-wrap")).not_to_be_visible()
