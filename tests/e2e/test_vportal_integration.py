"""End-to-end VPortal flow against the fake VPortal server."""

import socket

import httpx
from playwright.sync_api import expect


def test_full_connect_flow_shows_lifter_on_display(page, server_url, fake_vportal_url):
    page.goto(server_url + "/vportal")
    page.get_by_test_id("session-name-input").fill("VP Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    # Open modal
    page.locator(".vportal-connect-btn").click()
    page.locator(".vportal-modal").wait_for(state="visible")

    # Step 1: Inject the fake VPortal URL as a global test override; pick any federation.
    page.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
    page.get_by_test_id("vportal-federation-select").select_option("BVDK")
    page.locator(".vportal-step-federation .vportal-next-btn").click()

    # Step 2: Credentials
    page.get_by_test_id("vportal-identity-input").fill("u")
    page.get_by_test_id("vportal-credential-input").fill("p")
    page.locator(".vportal-step-credentials .vportal-next-btn").click()

    # Step 3: Stage picker
    page.locator(".vportal-step-stage").wait_for(state="visible")
    page.get_by_test_id("vportal-stage-select").select_option("STAGE-1")
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
    page.get_by_test_id("session-name-input").fill("VP Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".vportal-connect-btn").click()
    page.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
    page.get_by_test_id("vportal-federation-select").select_option("BVDK")
    page.locator(".vportal-step-federation .vportal-next-btn").click()
    page.get_by_test_id("vportal-identity-input").fill("u")
    page.get_by_test_id("vportal-credential-input").fill("p")
    page.locator(".vportal-step-credentials .vportal-next-btn").click()
    page.locator(".vportal-step-stage").wait_for(state="visible")
    page.get_by_test_id("vportal-stage-select").select_option("STAGE-1")
    page.locator(".vportal-step-stage .vportal-next-btn").click()
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")


def test_token_expiry_hides_overlay_and_shows_banner(page, server_url, fake_vportal_url):
    _connect_and_open_display(page, server_url, fake_vportal_url)
    expect(page.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    # Force fake VPortal to start rejecting tokens
    httpx.post(f"http://{fake_vportal_url}/_control/force_token_invalid")
    expect(page.locator(".vportal-corner-left")).not_to_be_visible(timeout=10000)
    # Hall display: reconnect happens on role-select (the overlay's text differs, #173)
    expect(page.locator(".vportal-disconnected-banner")).to_have_text(
        "VPortal disconnected — open Select Role to reconnect."
    )
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


def test_rejoin_via_qr_keeps_connect_button_visible(browser, server_url, fake_vportal_url):
    # Device A creates the session
    ctx_a = browser.new_context(locale="en-US")
    page_a = ctx_a.new_page()
    page_a.goto(server_url + "/vportal")
    page_a.get_by_test_id("session-name-input").fill("Rejoin Test")
    page_a.get_by_role("button", name="Create New Session").click()
    page_a.locator(".role-wrap").wait_for(state="visible")
    session_code = page_a.locator(".session-tag .code").text_content()

    # Device B opens the session via the join flow
    ctx_b = browser.new_context(locale="en-US")
    page_b = ctx_b.new_page()
    page_b.goto(server_url + "/")
    page_b.get_by_test_id("join-code-input").fill(session_code)
    page_b.get_by_role("button", name="Join Session").click()
    page_b.locator(".role-wrap").wait_for(state="visible")

    from playwright.sync_api import expect
    # Connect button visible on device B even though it joined via plain /
    expect(page_b.locator(".vportal-connect-btn")).to_be_visible()

    ctx_a.close()
    ctx_b.close()


def _open_credentials_step(page, server_url, vportal_host):
    """Helper: create a VPortal session and fill the login form against `vportal_host`."""
    page.goto(server_url + "/vportal")
    page.get_by_test_id("session-name-input").fill("VP Error Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".vportal-connect-btn").click()
    page.evaluate(f"() => {{ window._testVportalHost = '{vportal_host}'; }}")
    page.get_by_test_id("vportal-federation-select").select_option("BVDK")
    page.locator(".vportal-step-federation .vportal-next-btn").click()
    page.get_by_test_id("vportal-identity-input").fill("u")
    page.get_by_test_id("vportal-credential-input").fill("p")


def test_login_with_vportal_unreachable_shows_cause_in_dialog(page, server_url, fake_vportal_url):
    """VPortal host refuses connections (venue network or VPortal down).

    The operator presses "Log in" and the dialog must say that VPortal is not
    reachable — not a raw proxy status — and stay on the credentials step.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        closed_port = s.getsockname()[1]
    _open_credentials_step(page, server_url, f"127.0.0.1:{closed_port}")
    page.locator(".vportal-step-credentials .vportal-next-btn").click()

    error = page.locator(".vportal-step-credentials .vportal-error")
    expect(error).to_have_text("VPortal is not reachable. Check the internet connection and try again.")
    expect(page.locator(".vportal-step-credentials")).to_be_visible()


def test_login_without_session_cookie_shows_cause_in_dialog(page, server_url, fake_vportal_url):
    """VPortal answers the login form without a session cookie (seen at staging, issue #100).

    The proxy reports this as 424 (Cloudflare would replace a 502 body); the
    dialog must name the cause instead of "vportal-proxy-error:502".
    """
    httpx.post(f"http://{fake_vportal_url}/_control/unreachable")
    try:
        _open_credentials_step(page, server_url, fake_vportal_url)
        page.locator(".vportal-step-credentials .vportal-next-btn").click()
        expect(page.locator(".vportal-step-credentials .vportal-error")).to_have_text(
            "VPortal did not return a session. Try again; if it keeps failing, "
            "check the account directly on the VPortal website."
        )
    finally:
        httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_stage_list_failure_after_login_shows_error_in_stage_step(page, server_url, fake_vportal_url):
    """Login succeeds but loading the stage list fails (VPortal or venue network hiccup).

    Previously the error landed on the hidden credentials step and the stage
    step showed "Loading stages…" forever. Now the stage step shows the error
    and no longer claims to be loading.
    """
    httpx.post(f"http://{fake_vportal_url}/_control/reset")
    page.route("**/api/vportal/graphql", lambda route: route.fulfill(status=502, body="Bad gateway"))
    _open_credentials_step(page, server_url, fake_vportal_url)
    page.locator(".vportal-step-credentials .vportal-next-btn").click()

    stage_step = page.locator(".vportal-step-stage")
    expect(stage_step).to_be_visible()
    expect(stage_step.locator(".vportal-error")).to_have_text(
        "Could not load the stages from VPortal. Cancel and connect again."
    )
    expect(stage_step.locator(".vportal-loading")).not_to_be_visible()


def test_reconnect_with_failing_stage_list_shows_no_stale_stages(page, server_url, fake_vportal_url):
    """Operator connects, disconnects, connects again, and the stage list now fails.

    The stage step must not offer the stages from the first connect next to the
    error — no options, confirm button disabled.
    """
    httpx.post(f"http://{fake_vportal_url}/_control/reset")
    _open_credentials_step(page, server_url, fake_vportal_url)
    page.locator(".vportal-step-credentials .vportal-next-btn").click()
    page.get_by_test_id("vportal-stage-select").select_option("STAGE-1")
    page.locator(".vportal-step-stage .vportal-next-btn").click()
    page.locator(".vportal-modal").wait_for(state="hidden")

    page.locator(".vportal-connect-btn").click()
    page.locator(".vportal-step-connected").get_by_role("button", name="Disconnect").click()
    page.locator(".vportal-modal").wait_for(state="hidden")

    page.route("**/api/vportal/graphql", lambda route: route.fulfill(status=502, body="Bad gateway"))
    page.locator(".vportal-connect-btn").click()
    page.locator(".vportal-step-federation .vportal-next-btn").click()
    page.locator(".vportal-step-credentials .vportal-next-btn").click()

    stage_step = page.locator(".vportal-step-stage")
    expect(stage_step.locator(".vportal-error")).to_be_visible()
    expect(stage_step.get_by_test_id("vportal-stage-select").locator("option")).to_have_count(0)
    expect(stage_step.locator(".vportal-next-btn")).to_be_disabled()
