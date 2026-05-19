"""End-to-end VPortal flow against the fake VPortal server."""

import httpx
from playwright.sync_api import expect


def test_full_connect_flow_shows_lifter_on_display(page, server_url, fake_vportal_url):
    page.goto(server_url + "/vportal")
    page.locator('[x-model="newSessionName"]').fill("VP Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    # Open modal
    page.locator(".vportal-connect-btn").click()
    page.locator(".vportal-modal").wait_for(state="visible")

    # Step 1: Inject the fake VPortal URL as a global test override; pick any federation.
    page.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
    page.locator('[x-model="vportalFederation"]').select_option("BVDK")
    page.locator(".vportal-step-federation .vportal-next-btn").click()

    # Step 2: Credentials
    page.locator('[x-model="vportalIdentity"]').fill("u")
    page.locator('[x-model="vportalCredential"]').fill("p")
    page.locator(".vportal-step-credentials .vportal-next-btn").click()

    # Step 3: Stage picker
    page.locator(".vportal-step-stage").wait_for(state="visible")
    page.locator('[x-model="vportalSelectedStage"]').select_option("STAGE-1")
    page.locator(".vportal-step-stage .vportal-next-btn").click()

    # Modal closes
    page.locator(".vportal-modal").wait_for(state="hidden")

    # Open display
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")

    # Lifter corner appears within polling interval
    expect(page.locator(".vportal-corner-left")).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(page.locator(".vportal-corner-left")).to_contain_text("SV Eisenkraft")
    expect(page.locator(".vportal-corner-right")).to_contain_text("215")
    expect(page.locator(".vportal-corner-right")).to_contain_text("SQUAT", ignore_case=True)


def _connect_and_open_display(page, server_url, fake_vportal_url):
    """Helper: full connect flow up to display screen visible with overlay."""
    httpx.post(f"http://{fake_vportal_url}/_control/reset")
    httpx.post(f"http://{fake_vportal_url}/_control/restore_attempt")
    page.goto(server_url + "/vportal")
    page.locator('[x-model="newSessionName"]').fill("VP Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".vportal-connect-btn").click()
    page.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
    page.locator('[x-model="vportalFederation"]').select_option("BVDK")
    page.locator(".vportal-step-federation .vportal-next-btn").click()
    page.locator('[x-model="vportalIdentity"]').fill("u")
    page.locator('[x-model="vportalCredential"]').fill("p")
    page.locator(".vportal-step-credentials .vportal-next-btn").click()
    page.locator(".vportal-step-stage").wait_for(state="visible")
    page.locator('[x-model="vportalSelectedStage"]').select_option("STAGE-1")
    page.locator(".vportal-step-stage .vportal-next-btn").click()
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")


def test_token_expiry_hides_overlay_and_shows_banner(page, server_url, fake_vportal_url):
    _connect_and_open_display(page, server_url, fake_vportal_url)
    expect(page.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    # Force fake VPortal to start rejecting tokens
    httpx.post(f"http://{fake_vportal_url}/_control/force_token_invalid")
    expect(page.locator(".vportal-corner-left")).not_to_be_visible(timeout=10000)
    expect(page.locator(".vportal-disconnected-banner")).to_be_visible()
    # Cleanup
    httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_upstream_unreachable_after_three_failures_shows_banner(page, server_url, fake_vportal_url):
    _connect_and_open_display(page, server_url, fake_vportal_url)
    expect(page.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    httpx.post(f"http://{fake_vportal_url}/_control/unreachable")
    # Three poll cycles at 2000ms → wait up to ~15s for the banner
    expect(page.locator(".vportal-disconnected-banner")).to_be_visible(timeout=15000)
    httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_no_active_attempt_hides_overlay_without_banner(page, server_url, fake_vportal_url):
    _connect_and_open_display(page, server_url, fake_vportal_url)
    from playwright.sync_api import expect
    expect(page.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    httpx.post(f"http://{fake_vportal_url}/_control/clear_attempt")
    expect(page.locator(".vportal-corner-left")).not_to_be_visible(timeout=8000)
    # No disconnected banner — empty state is not an error
    expect(page.locator(".vportal-disconnected-banner")).not_to_be_visible()
    httpx.post(f"http://{fake_vportal_url}/_control/restore_attempt")
