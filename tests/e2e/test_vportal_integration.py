"""End-to-end VPortal flow against the fake VPortal server."""

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
    expect(page.locator(".vportal-corner-left")).to_contain_text("MARIA SCHNEIDER", timeout=10000)
    expect(page.locator(".vportal-corner-left")).to_contain_text("SV Eisenkraft")
    expect(page.locator(".vportal-corner-right")).to_contain_text("215")
    expect(page.locator(".vportal-corner-right")).to_contain_text("SQUAT")
