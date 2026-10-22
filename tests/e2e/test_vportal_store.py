"""VPortal state shared across screens (Alpine.store('vportal'), issue #65).

The connect button and dialog (role-select) and the lifter overlay (display)
read one VPortal state that is separate from the main app component. These
tests cover the paths where both sides meet: leaving the display and coming
back to role-select, a dropped display connection, and a login stored before
a reload or a session switch in the same tab (#172).
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH
from tests.e2e.test_vportal_integration import _connect_and_open_display


CONNECTED_TEXT = "Connected to BVDK · Platform 1"
CONNECT_TEXT = "Connect to comp software"


def _active_group_polls(page):
    """Record the VPortal poll ticks (one active-group query each) of a page."""
    polls = []
    page.on(
        "request",
        lambda req: polls.append(req.url)
        if "/api/vportal/graphql" in req.url and "competitionGroupList" in (req.post_data or "")
        else None,
    )
    return polls


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

    polls = _active_group_polls(page)

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


def test_reloaded_display_shows_stored_login_as_connected_and_disconnect_stops_polling(competition, server_url, fake_vportal_url):
    """Connect to (fake) VPortal → open the display → reload the display → the
    overlay runs with the stored login → browser back to role-select → the button says "Connected to BVDK · Platform 1" and the dialog opens
    on the connected step (issue #172) → reload on role-select → still connected
    → disconnect → the button offers connecting again and the stored login is
    gone → back on the display no VPortal polling runs and no lifter shows.
    Fixed wait: the test measures that no poll request is made."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    code = page.evaluate("Alpine.store('session').code")

    page.reload()
    page.locator(".display-full").wait_for(state="visible")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    button = page.locator(".vportal-connect-btn")
    expect(button).to_have_text(CONNECTED_TEXT)
    expect(button).to_have_class(re.compile(r"\bconnected\b"))

    page.reload()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(button).to_have_text(CONNECTED_TEXT)
    button.click()
    expect(page.locator(".vportal-step-connected")).to_be_visible()
    expect(page.locator(".vportal-step-connected")).to_contain_text("Platform 1")
    expect(page.locator(".vportal-step-federation")).to_be_hidden()

    page.locator(".vportal-step-connected .btn-blood-primary").click()
    expect(page.locator(".vportal-modal")).to_be_hidden()
    expect(button).to_have_text(CONNECT_TEXT)
    expect(button).not_to_have_class(re.compile(r"\bconnected\b"))
    assert page.evaluate(f"localStorage.getItem('vportal:{code}')") is None

    polls = _active_group_polls(page)
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")
    page.wait_for_timeout(3500)
    assert polls == [], "a disconnected display must not poll VPortal"
    expect(corner).to_be_hidden()


def test_display_reloaded_without_network_shows_stored_login_as_connected(competition, server_url, fake_vportal_url):
    """VPortal-connected display loses the network (WebSocket cut, session
    lookup failing) and is reloaded → the reconnecting screen shows → the
    WebSocket comes back while the session lookup still fails → the display
    shows the "VPortal disconnected" banner → the lookup works again → the
    lifter overlay returns without a new login → browser back to role-select →
    the button shows the stored login as connected."""
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.evaluate("window.__ivCutNetwork()")
    page.route("**/api/sessions/*", lambda route: route.abort())
    page.reload()
    expect(page.get_by_test_id("reconnecting-screen")).to_be_visible()

    page.evaluate("window.__ivRestoreNetwork()")
    page.locator(".display-full").wait_for(state="visible", timeout=15000)
    expect(page.locator(".vportal-disconnected-banner")).to_be_visible(timeout=10000)

    page.unroute("**/api/sessions/*")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    expect(page.locator(".vportal-disconnected-banner")).to_be_hidden()

    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(page.locator(".vportal-connect-btn")).to_have_text(CONNECTED_TEXT)


def test_switching_session_in_the_same_tab_shows_no_stale_connection(competition, server_url, fake_vportal_url):
    """Connect to (fake) VPortal in session A → back to start → create session B
    in the same tab → its button offers connecting and the dialog starts at the
    federation step (A's login is not shown) → back to start, join A by its code
    → A's stored login shows as connected again."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    code_a = page.evaluate("Alpine.store('session').code")
    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    button = page.locator(".vportal-connect-btn")
    expect(button).to_have_text(CONNECTED_TEXT)

    page.get_by_role("button", name="Back to start").click()
    page.get_by_test_id("session-name-input").fill("VP Test B")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(button).to_have_text(CONNECT_TEXT)
    expect(button).not_to_have_class(re.compile(r"\bconnected\b"))
    button.click()
    expect(page.locator(".vportal-step-federation")).to_be_visible()
    expect(page.locator(".vportal-step-connected")).to_be_hidden()
    page.locator(".vportal-step-federation .btn-blood-ghost").click()

    page.get_by_role("button", name="Back to start").click()
    page.get_by_test_id("join-code-input").fill(code_a)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(button).to_have_text(CONNECTED_TEXT)


def test_display_reloaded_while_lookup_fails_shows_vportal_button_on_role_select(competition, server_url, fake_vportal_url):
    """VPortal-connected display loses the network and is reloaded → the
    WebSocket comes back while the session lookup keeps failing → back to
    role-select → the button shows the stored login as connected and the dialog
    offers disconnecting (#175) → close the dialog, open the display again →
    the lookup works again → the lifter overlay returns and role-select still
    shows the connection."""
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    corner = page.locator(".vportal-corner-left")
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)

    page.evaluate("window.__ivCutNetwork()")
    page.route("**/api/sessions/*", lambda route: route.abort())
    page.reload()
    expect(page.get_by_test_id("reconnecting-screen")).to_be_visible()
    page.evaluate("window.__ivRestoreNetwork()")
    page.locator(".display-full").wait_for(state="visible", timeout=15000)
    expect(page.locator(".vportal-disconnected-banner")).to_be_visible(timeout=10000)

    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    button = page.locator(".vportal-connect-btn")
    expect(button).to_have_text(CONNECTED_TEXT)
    button.click()
    expect(page.locator(".vportal-step-connected")).to_be_visible()
    expect(page.locator(".vportal-step-connected .btn-blood-primary")).to_have_text("Disconnect")
    page.locator(".vportal-step-connected .btn-blood-ghost").click()
    expect(page.locator(".vportal-modal")).to_be_hidden()

    page.unroute("**/api/sessions/*")
    page.locator(".role-btn", has_text="Display Screen").click()
    expect(corner).to_contain_text("MARIA SCHNEIDER", timeout=10000, ignore_case=True)
    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(button).to_have_text(CONNECTED_TEXT)


def test_judge_reloaded_while_lookup_fails_shows_vportal_button_on_role_select(competition, server_url, fake_vportal_url):
    """VPortal login made on this device → it joins as left judge → reloaded
    while the session lookup fails → back to role-select → the button shows the
    stored login as connected (#175)."""
    page = competition.new_context().new_page()
    _connect_and_open_display(page, server_url, fake_vportal_url)
    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Left Judge").click()
    page.get_by_test_id("judge-screen").wait_for(state="visible")

    page.route("**/api/sessions/*", lambda route: route.abort())
    page.reload()
    page.get_by_test_id("judge-screen").wait_for(state="visible", timeout=15000)
    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(page.locator(".vportal-connect-btn")).to_have_text(CONNECTED_TEXT)


def test_generic_session_display_reloaded_offline_shows_no_vportal_button(competition, server_url):
    """Generic session → display → network lost and the session lookup failing
    → reload → network back → back to role-select → no VPortal button (#175)."""
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    page.goto(server_url)
    page.get_by_test_id("session-name-input").fill("Generic Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Display Screen").click()
    page.locator(".display-full").wait_for(state="visible")

    page.evaluate("window.__ivCutNetwork()")
    page.route("**/api/sessions/*", lambda route: route.abort())
    page.reload()
    expect(page.get_by_test_id("reconnecting-screen")).to_be_visible()
    page.evaluate("window.__ivRestoreNetwork()")
    page.locator(".display-full").wait_for(state="visible", timeout=15000)

    page.go_back()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(page.locator(".vportal-connect-btn")).to_have_count(0)
