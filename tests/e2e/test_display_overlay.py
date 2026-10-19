"""Stream overlay for OBS (#107).

An OBS browser source loads ``/?session=CODE&overlay=1`` and lays the page
over the camera picture. The overlay joins the session as a display without
a click (it counts against the display cap) and shows only the blocks of its
layout on a transparent page: no gear, no session name, no "Waiting…" text;
the connection dot only appears while the connection is down. "S" still
opens the settings panel (OBS: "Interact"), where the overlay's own layout is
edited, or — for VPortal sessions — VPortal is connected, because the
overlay never passes role-select. A layout code in the URL (``&layout=…``)
is the only layout source then and locks the editor. The URL stays in the
address bar, so a reload in OBS starts the overlay again. When the session
ends or is gone, a short notice shows instead of an alert.
"""

import base64
import json
import re

import httpx
from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH, cut_network, restore_network

VIEWPORT = {"width": 1920, "height": 1080}
OVERLAY_LAYOUT_KEY = "iron-verdict:display-layout:overlay"
HALL_LAYOUT_KEY = "iron-verdict:display-layout"
TRANSPARENT = "rgba(0, 0, 0, 0)"


def overlay_url(competition, layout_code=None, code=None):
    url = f"{competition.url}/?session={code or competition.session_code}&overlay=1"
    if layout_code:
        url += f"&layout={layout_code}"
    return url


def open_overlay(competition, layout_code=None, network_switch=False, code=None, name="Test Session"):
    """Open the overlay URL in a new 1920×1080 context, as OBS does; returns
    (page, dialogs) — dialogs collects every alert/confirm the page raised."""
    ctx = competition.new_context(viewport=VIEWPORT)
    if network_switch:
        ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(overlay_url(competition, layout_code, code))
    expect(page.get_by_test_id("display-screen")).to_be_visible()
    wait_joined(page, name)
    return page, dialogs


def wait_joined(page, name="Test Session"):
    # join_success sets the session name (not shown in the overlay).
    page.wait_for_function(f"Alpine.store('session').name === {json.dumps(name)}")


def backgrounds(page):
    return page.evaluate(
        """() => ['html', 'body', '.display-full'].map((sel) => {
            const s = getComputedStyle(document.querySelector(sel));
            return [s.backgroundColor, s.backgroundImage];
        })"""
    )


def layout_code(layout):
    raw = base64.urlsafe_b64encode(json.dumps(layout).encode()).decode().rstrip("=")
    return "IV1." + raw


def layout_with_timer_hidden():
    return {
        "v": 1,
        "blocks": {
            "timer": {"x": 50, "y": 5, "s": 1, "hidden": True},
            "lights": {"x": 50, "y": 60, "s": 0.6, "hidden": False},
            "cards": {"gap": 0, "hidden": False},
            "verdict": {"x": 50, "y": 85, "s": 0.6, "hidden": False},
            "lifter": {"x": 2, "y": 88, "s": 1, "hidden": False},
            "attempt": {"x": 98, "y": 88, "s": 1, "hidden": False},
        },
    }


def expect_good_lift(page):
    expect(page.locator(".verdict-stamp")).to_have_text("Good Lift")
    for orb in page.locator(".display-lights .display-orb").all():
        expect(orb).to_have_class(re.compile(r"\bwhite\b"))


def test_overlay_opens_without_clicks_and_shows_votes_on_transparent_background(competition):
    """The overlay URL opens the display directly (no landing or role-select),
    on a transparent page without gear, session name, panel or "Waiting…";
    a vote shows lights and verdict as on the hall display. The URL keeps the
    overlay parameters, so OBS reloads the overlay itself."""
    competition.join_all_judges()
    overlay, dialogs = open_overlay(competition)

    for color, image in backgrounds(overlay):
        assert color == TRANSPARENT
        assert image == "none"
    expect(overlay.get_by_test_id("display-settings-gear")).to_be_hidden()
    expect(overlay.get_by_test_id("display-tag")).to_be_hidden()
    expect(overlay.locator(".display-settings-panel")).to_be_hidden()
    expect(overlay.locator(".display-status")).to_be_hidden()
    expect(overlay.locator(".role-wrap")).to_be_hidden()
    expect(overlay.get_by_role("button", name="Create New Session")).to_be_hidden()
    assert "overlay=1" in overlay.url and competition.session_code in overlay.url

    competition.vote_all_white()
    expect_good_lift(overlay)
    assert dialogs == []


def test_overlay_shows_dot_only_while_disconnected_and_misses_no_result(competition):
    """The connection drops: a small dot appears (the stream shows something is
    wrong). The judges vote meanwhile. After reconnecting the dot disappears and
    the result that was decided during the outage shows."""
    competition.join_all_judges()
    overlay, _ = open_overlay(competition, network_switch=True)
    expect(overlay.get_by_test_id("display-tag")).to_be_hidden()

    cut_network(overlay, conn_dot=".display-tag .conn-dot")
    expect(overlay.get_by_test_id("display-tag")).to_be_visible()
    expect(overlay.locator(".display-tag .code-link")).to_be_hidden()

    competition.vote_all_white()
    restore_network(overlay)

    expect(overlay.get_by_test_id("display-tag")).to_be_hidden(timeout=10000)
    expect_good_lift(overlay)


def test_overlay_reload_rejoins_and_restores_the_result(competition):
    """OBS reloads the browser source: the overlay comes back on the same URL,
    transparent, without the "Connecting…" screen or the landing screen, and
    shows the current result again."""
    competition.join_all_judges()
    overlay, dialogs = open_overlay(competition)
    competition.vote_all_white()
    expect_good_lift(overlay)

    url = overlay.url
    overlay.reload()
    expect(overlay.get_by_test_id("display-screen")).to_be_visible()
    expect(overlay.get_by_test_id("reconnecting-screen")).to_have_count(0)
    expect(overlay.get_by_test_id("landing-screen")).to_have_count(0)
    expect_good_lift(overlay)
    assert overlay.url == url
    for color, image in backgrounds(overlay):
        assert color == TRANSPARENT and image == "none"
    assert dialogs == []


def test_overlay_session_end_shows_notice_without_alert(competition):
    """The head judge ends the session: the overlay shows "Session ended"
    instead of an alert (which would block OBS) and stays transparent. A
    reload then shows "Session not found"."""
    head, _, _ = competition.join_all_judges()
    overlay, dialogs = open_overlay(competition)
    competition.vote_all_white()
    expect_good_lift(overlay)

    head.get_by_role("button", name="End Session").click()

    expect(overlay.get_by_test_id("overlay-notice")).to_have_text("Session ended")
    expect(overlay.locator(".verdict-stamp")).to_be_hidden()
    expect(overlay.get_by_role("button", name="Create New Session")).to_be_hidden()
    assert dialogs == []

    overlay.reload()
    expect(overlay.get_by_test_id("overlay-notice")).to_have_text("Session not found")
    assert dialogs == []


def test_overlay_layout_from_url_is_used_and_locks_the_editor(competition):
    """A layout code in the URL places the blocks (here: timer hidden) and is
    the only source: the panel ("S") says so instead of offering the editor."""
    competition.create_session_and_join_head()
    overlay, _ = open_overlay(competition, layout_code=layout_code(layout_with_timer_hidden()))

    expect(overlay.locator('[data-layout-block="timer"]')).to_be_hidden()
    expect(overlay.locator(".display-full")).to_have_class(re.compile(r"\bdisplay-layout-custom\b"))

    overlay.keyboard.press("s")
    expect(overlay.locator(".display-settings-panel")).to_be_visible()
    expect(overlay.get_by_test_id("overlay-layout-from-url")).to_be_visible()
    expect(overlay.get_by_test_id("display-layout-edit")).to_be_hidden()


def test_overlay_invalid_layout_code_falls_back_with_a_hint(competition):
    """An unreadable layout code in the URL: the overlay keeps its default
    (or saved) layout, the panel says the code is invalid, editing works."""
    competition.create_session_and_join_head()
    overlay, _ = open_overlay(competition, layout_code="IV1.not-a-layout")

    expect(overlay.locator('[data-layout-block="timer"]')).to_be_visible()
    overlay.keyboard.press("s")
    expect(overlay.get_by_test_id("overlay-layout-url-invalid")).to_be_visible()
    expect(overlay.get_by_test_id("display-layout-edit")).to_be_visible()


def test_overlay_edits_its_own_layout_on_a_checkerboard(competition):
    """Edit mode in the overlay ("S" → edit): a dark checkerboard shows behind
    the blocks; after saving the page is transparent again. The layout is
    stored under the overlay's own key — the hall display layout of the same
    browser stays untouched — and survives a reload."""
    competition.create_session_and_join_head()
    overlay, _ = open_overlay(competition)

    overlay.keyboard.press("s")
    overlay.get_by_test_id("display-layout-edit").click()
    expect(overlay.get_by_test_id("layout-toolbar")).to_be_visible()
    assert "conic-gradient" in backgrounds(overlay)[2][1]

    overlay.get_by_test_id("layout-hide-timer").click()
    overlay.get_by_test_id("layout-save").click()
    expect(overlay.get_by_test_id("layout-toolbar")).to_be_hidden()
    assert backgrounds(overlay)[2] == [TRANSPARENT, "none"]
    expect(overlay.locator('[data-layout-block="timer"]')).to_be_hidden()

    stored = json.loads(overlay.evaluate(f"localStorage.getItem('{OVERLAY_LAYOUT_KEY}')"))
    assert stored["blocks"]["timer"]["hidden"] is True
    assert overlay.evaluate(f"localStorage.getItem('{HALL_LAYOUT_KEY}')") is None

    overlay.reload()
    wait_joined(overlay)
    expect(overlay.locator('[data-layout-block="timer"]')).to_be_hidden()


def _open_role_select(competition, insecure=False):
    ctx = competition.new_context()
    if insecure:
        # Like plain http on the venue network: no clipboard API.
        ctx.add_init_script("Object.defineProperty(window, 'isSecureContext', { value: false })")
    else:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    return page


def test_role_select_offers_the_overlay_url_to_copy(competition):
    """Role-select shows "Stream overlay (OBS)": it opens the URL for the OBS
    browser source — exactly the URL that opens the overlay — and copies it.
    Without the clipboard API (plain http) the URL is selected for Ctrl+C."""
    competition.create_session_and_join_head()

    page = _open_role_select(competition)
    expect(page.get_by_test_id("overlay-link-url")).to_be_hidden()
    page.get_by_test_id("overlay-link-toggle").click()
    expect(page.get_by_test_id("overlay-link-url")).to_have_value(overlay_url(competition))
    page.get_by_test_id("overlay-link-copy").click()
    expect(page.get_by_test_id("overlay-link-copy")).to_have_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == overlay_url(competition)

    insecure = _open_role_select(competition, insecure=True)
    insecure.get_by_test_id("overlay-link-toggle").click()
    insecure.get_by_test_id("overlay-link-copy").click()
    expect(insecure.get_by_test_id("overlay-link-copy")).to_have_text("Copy")
    assert insecure.evaluate("document.activeElement.dataset.testid") == "overlay-link-url"
    assert insecure.evaluate("window.getSelection().toString() || document.activeElement.value.substring("
                             "document.activeElement.selectionStart, document.activeElement.selectionEnd)") \
        == overlay_url(competition)


def test_overlay_connects_vportal_from_the_panel_and_keeps_it_after_reload(
    page, competition, server_url, fake_vportal_url
):
    """VPortal session: the overlay never passes role-select, so its panel
    ("S") offers "Connect VPortal". After login and stage choice the lifter
    and attempt info appear without a reload; after a reload (OBS) they come
    back from the stored login and the panel shows it as connected."""
    httpx.post(f"http://{fake_vportal_url}/_control/reset")
    httpx.post(f"http://{fake_vportal_url}/_control/restore_attempt")
    page.goto(server_url + "/vportal")
    page.get_by_test_id("session-name-input").fill("VP Overlay")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    code = page.locator(".session-tag .code").text_content()
    competition.session_code = code

    overlay, _ = open_overlay(competition, code=code, name="VP Overlay")
    expect(overlay.locator(".vportal-corner-left")).to_be_hidden()

    overlay.keyboard.press("s")
    connect = overlay.get_by_test_id("overlay-vportal-connect")
    expect(connect).to_have_text("Connect to comp software")
    connect.click()
    overlay.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
    overlay.get_by_test_id("vportal-federation-select").select_option("BVDK")
    overlay.locator(".vportal-step-federation .vportal-next-btn").click()
    overlay.get_by_test_id("vportal-identity-input").fill("u")
    overlay.get_by_test_id("vportal-credential-input").fill("p")
    overlay.locator(".vportal-step-credentials .vportal-next-btn").click()
    overlay.locator(".vportal-step-stage").wait_for(state="visible")
    overlay.get_by_test_id("vportal-stage-select").select_option("STAGE-1")
    overlay.locator(".vportal-step-stage .vportal-next-btn").click()

    expect(overlay.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    expect(overlay.locator(".vportal-corner-right")).to_be_visible()

    overlay.reload()
    wait_joined(overlay, "VP Overlay")
    expect(overlay.locator(".vportal-corner-left")).to_be_visible(timeout=10000)
    overlay.keyboard.press("s")
    expect(overlay.get_by_test_id("overlay-vportal-connect")).to_have_text(re.compile(r"^Connected to BVDK"))
    httpx.post(f"http://{fake_vportal_url}/_control/reset")
