"""VPortal state shared across screens (Alpine.store('vportal'), issue #65).

The connect button and dialog (role-select) and the lifter overlay (display)
read one VPortal state that is separate from the main app component. These
tests cover the paths where both sides meet: leaving the display and coming
back to role-select, and a dropped display connection.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH
from tests.e2e.test_vportal_integration import _connect_and_open_display


def test_connection_shown_on_role_select_after_display_and_disconnect(competition, server_url, fake_vportal_url):
    """Connect to (fake) VPortal → open the display → overlay shows → back to
    role-select with the browser back button → the connect button still says
    "Connected to BVDK · Platform 1" → reopening the dialog shows the connected
    step → disconnect → the button offers connecting again."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    expect(page.locator(".vportal-corner-left")).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")

    button = page.locator(".vportal-connect-btn")
    expect(button).to_have_text("Connected to BVDK · Platform 1")
    expect(button).to_have_class(re.compile(r"\bconnected\b"))

    button.click()
    expect(page.locator(".vportal-step-connected")).to_be_visible()
    expect(page.locator(".vportal-step-connected")).to_contain_text("BVDK")
    expect(page.locator(".vportal-step-connected")).to_contain_text("Platform 1")
    expect(page.locator(".vportal-step-federation")).to_be_hidden()

    page.locator(".vportal-step-connected .btn-blood-primary").click()
    expect(page.locator(".vportal-modal")).to_be_hidden()
    expect(button).to_have_text("Connect to comp software")
    expect(button).not_to_have_class(re.compile(r"\bconnected\b"))


def test_display_connection_loss_keeps_overlay_and_recovers(competition, server_url, fake_vportal_url):
    """Display with the VPortal overlay loses its WebSocket → the connection dot
    shows reconnecting while the overlay keeps the current lifter (VPortal
    polling runs over HTTP, independent of the socket) → network back → the dot
    is connected again and the overlay is unchanged → reload → the overlay is
    filled again."""
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    dot = page.locator(".display-tag .conn-dot")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(dot).to_have_class(re.compile(r"\bconnected\b"))

    page.evaluate("window.__ivCutNetwork()")
    expect(dot).to_have_class(re.compile(r"\breconnecting\b"))
    expect(corner).to_contain_text("MARIA SCHNEIDER", ignore_case=True)
    expect(page.locator(".vportal-disconnected-banner")).to_be_hidden()

    page.evaluate("window.__ivRestoreNetwork()")
    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=10000)
    expect(corner).to_contain_text("MARIA SCHNEIDER", ignore_case=True)

    page.reload()
    page.locator(".display-full").wait_for(state="visible")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(page.locator(".vportal-disconnected-banner")).to_be_hidden()


def test_display_reload_with_failing_session_lookup_recovers_without_reload(competition, server_url, fake_vportal_url):
    """VPortal-connected display is reloaded while the session lookup
    (GET /api/sessions/{code}) fails at the network level → the display rejoins
    and shows the "VPortal disconnected" banner instead of silently empty
    corners → the lookup works again → without another reload the banner goes
    away and the lifter overlay appears (issue #112)."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    banner = page.locator(".vportal-disconnected-banner")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.route("**/api/sessions/*", lambda route: route.abort())
    page.reload()
    page.locator(".display-full").wait_for(state="visible")
    expect(banner).to_be_visible(timeout=10000)
    expect(corner).to_be_hidden()
    expect(page.locator(".display-tag .conn-dot")).to_have_class(re.compile(r"\bconnected\b"), timeout=10000)

    page.unroute("**/api/sessions/*")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(banner).to_be_hidden()


def test_display_role_select_round_trips_leave_one_poller(competition, server_url, fake_vportal_url):
    """VPortal-connected display → role-select → display → role-select →
    display. On role-select no VPortal polling runs; back on the display exactly
    one poller runs. Measured by counting poll ticks (one active-group query
    each): with the 3 s interval one poller makes at most 3 in 6.5 s, while the
    two leftover pollers of the old behavior would at least double that. Fixed
    waits are unavoidable here because the test measures a request rate."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    polls = []
    page.on(
        "request",
        lambda req: polls.append(req.url)
        if "/api/vportal/graphql" in req.url and "competitionGroupList" in (req.post_data or "")
        else None,
    )

    for _ in range(2):
        page.go_back()
        page.locator(".role-wrap").wait_for(state="visible")
        polls.clear()
        page.wait_for_timeout(3500)
        assert polls == [], "VPortal polling must stop when the display is left"
        page.locator(".role-btn", has_text="Display Screen").click()
        page.locator(".display-full").wait_for(state="visible")
        expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    polls.clear()
    page.wait_for_timeout(6500)
    assert 1 <= len(polls) <= 3, f"expected one poller, saw {len(polls)} poll ticks in 6.5 s"
