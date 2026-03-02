"""Smoke test — verify E2E infrastructure works."""

from playwright.sync_api import expect


def test_landing_page_loads(page, server_url):
    page.goto(server_url)
    expect(page.locator(".brand-iron").first).to_have_text("Iron Verdict")


def test_create_session_shows_role_select(page, server_url):
    page.goto(server_url)
    page.locator('[x-model="newSessionName"]').fill("Smoke Test")
    page.get_by_role("button", name="Create New Session").click()
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".session-tag .code")).not_to_be_empty()
