"""E2E: invalid/unknown session codes surface as inline errors on landing, not at role-select."""

from playwright.sync_api import expect


def test_code_length_gate_unknown_code_error_cleared_by_typing(page, server_url):
    """Length gate: the button stays disabled below 8 chars and enables exactly
    at 8. An 8-char code for a nonexistent session shows an inline error with
    no navigation to role-select; typing again clears the error."""
    page.goto(server_url)

    join_btn = page.get_by_role("button", name="Join Session")
    join_input = page.get_by_test_id("join-code-input")

    expect(join_btn).to_be_disabled()

    join_input.fill("ABCDEFG")  # 7 chars
    expect(join_btn).to_be_disabled()

    join_input.fill("ABCDEFGH")  # 8 chars
    expect(join_btn).to_be_enabled()

    join_input.fill("ZZZZZZZZ")
    join_btn.click()

    expect(page.locator(".join-error")).to_be_visible()
    expect(page.locator(".join-error")).to_contain_text("Session not found")
    expect(page.locator(".role-wrap")).not_to_be_visible()

    join_input.fill("A")
    expect(page.locator(".join-error")).not_to_be_visible()


def test_stale_qr_code_lands_on_landing_with_error(page, server_url):
    """Scanned QR with a stale session code: pre-fill input, show inline error, no role-select."""
    page.goto(f"{server_url}/?session=YYYYYYYY")

    expect(page.get_by_role("button", name="Create New Session")).to_be_visible()
    expect(page.get_by_test_id("join-code-input")).to_have_value("YYYYYYYY")
    expect(page.locator(".join-error")).to_be_visible()
    expect(page.locator(".role-wrap")).not_to_be_visible()
