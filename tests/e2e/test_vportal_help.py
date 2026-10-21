"""In-place "?" explanation in the VPortal connect dialog (#160).

The title row of the dialog has a "?" that opens a full explanation of the
connection to the competition software right in the dialog — what it is for,
which credentials, the stage choice, one login per device (the stream overlay
needs its own), that the dialog is visible in the stream while open there, and
that judging goes on without VPortal. The "?" is there in every step
(federation, credentials, stage, connected), the explanation closes together
with the dialog and starts closed the next time. The connect flow itself is
unchanged. Texts follow the UI language (DE/EN).
"""

import httpx
from playwright.sync_api import expect

from tests.e2e.test_display_overlay import create_vportal_session, open_overlay

TITLE = {"en": "Connecting to the competition software", "de": "Verbindung zur Wettkampf-Software"}
STREAM_NOTE = {"en": "visible in the stream", "de": "im Stream zu sehen"}


def _new_vportal_session(competition, server_url, lang, name="VP Help"):
    ctx = competition.new_context()
    ctx.add_init_script(f"localStorage.setItem('iron-verdict-lang', '{lang}')")
    page = ctx.new_page()
    page.goto(server_url + "/vportal")
    page.get_by_test_id("session-name-input").fill(name)
    page.get_by_test_id("session-name-input").press("Enter")
    page.locator(".role-wrap").wait_for(state="visible")
    return page


def _toggle_in_step(page, lang):
    """Open and close the explanation in the step currently shown."""
    toggle = page.get_by_test_id("vportal-help-toggle")
    help_box = page.get_by_test_id("vportal-help")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(help_box).to_be_hidden()
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(help_box).to_be_visible()
    expect(help_box).to_contain_text(TITLE[lang])
    expect(help_box).to_contain_text(STREAM_NOTE[lang])
    # Clicking inside the explanation keeps the dialog open.
    help_box.locator("h3").first.click()
    expect(page.locator(".vportal-modal")).to_be_visible()
    toggle.click()
    expect(help_box).to_be_hidden()


def test_vportal_help_in_every_step_and_connect_flow_unchanged_en_de(competition, server_url, fake_vportal_url):
    """Role-select of a VPortal session (EN, then DE): the "?" opens and closes
    the explanation in the federation, credentials, stage and connected step.
    Cancelling the dialog with the explanation open closes both; reopening
    starts with the explanation closed. Login and stage choice still connect."""
    for lang in ("en", "de"):
        httpx.post(f"http://{fake_vportal_url}/_control/reset")
        page = _new_vportal_session(competition, server_url, lang)
        help_box = page.get_by_test_id("vportal-help")

        page.locator(".vportal-connect-btn").click()
        page.locator(".vportal-modal").wait_for(state="visible")
        _toggle_in_step(page, lang)

        # Cancel with the explanation open: both close, the next opening starts closed.
        page.get_by_test_id("vportal-help-toggle").click()
        expect(help_box).to_be_visible()
        page.locator(".vportal-step-federation .btn-blood-ghost").click()
        expect(page.locator(".vportal-modal")).to_be_hidden()
        expect(help_box).to_be_hidden()
        page.locator(".vportal-connect-btn").click()
        expect(page.locator(".vportal-modal")).to_be_visible()
        expect(help_box).to_be_hidden()

        page.evaluate(f"() => {{ window._testVportalHost = '{fake_vportal_url}'; }}")
        page.get_by_test_id("vportal-federation-select").select_option("BVDK")
        page.locator(".vportal-step-federation .vportal-next-btn").click()
        expect(page.locator(".vportal-step-credentials")).to_be_visible()
        _toggle_in_step(page, lang)
        page.get_by_test_id("vportal-identity-input").fill("u")
        page.get_by_test_id("vportal-credential-input").fill("p")
        page.locator(".vportal-step-credentials .vportal-next-btn").click()

        page.locator(".vportal-step-stage").wait_for(state="visible")
        _toggle_in_step(page, lang)
        page.get_by_test_id("vportal-stage-select").select_option("STAGE-1")
        page.locator(".vportal-step-stage .vportal-next-btn").click()
        expect(page.locator(".vportal-modal")).to_be_hidden()
        expect(page.locator(".vportal-connect-btn")).to_contain_text("BVDK")

        page.locator(".vportal-connect-btn").click()
        expect(page.locator(".vportal-step-connected")).to_be_visible()
        _toggle_in_step(page, lang)
        page.context.close()
    httpx.post(f"http://{fake_vportal_url}/_control/reset")


def test_vportal_help_closed_after_reload(competition, server_url):
    """Reload with the dialog and its explanation open: afterwards both are
    closed, and opening the dialog again shows the explanation closed."""
    page = _new_vportal_session(competition, server_url, "en")
    page.locator(".vportal-connect-btn").click()
    page.get_by_test_id("vportal-help-toggle").click()
    expect(page.get_by_test_id("vportal-help")).to_be_visible()

    page.reload()
    page.locator(".role-wrap").wait_for(state="visible")
    expect(page.locator(".vportal-modal")).to_be_hidden()
    expect(page.get_by_test_id("vportal-help")).to_be_hidden()
    page.locator(".vportal-connect-btn").click()
    expect(page.locator(".vportal-modal")).to_be_visible()
    expect(page.get_by_test_id("vportal-help")).to_be_hidden()


def test_vportal_help_on_a_phone_keeps_the_dialog_buttons_reachable(competition, server_url):
    """Phone (390 × 640): with the explanation open the dialog stays within
    the screen, the explanation scrolls, and the dialog buttons stay usable."""
    page = _new_vportal_session(competition, server_url, "de")
    page.set_viewport_size({"width": 390, "height": 640})
    page.locator(".vportal-connect-btn").click()
    page.get_by_test_id("vportal-help-toggle").click()
    help_box = page.get_by_test_id("vportal-help")
    expect(help_box).to_be_visible()

    modal = page.locator(".vportal-modal").bounding_box()
    assert modal["y"] >= 0 and modal["y"] + modal["height"] <= 640
    assert modal["x"] >= 0 and modal["x"] + modal["width"] <= 390
    assert help_box.evaluate("el => el.scrollHeight > el.clientHeight")
    page.locator(".vportal-step-federation .vportal-next-btn").click()
    expect(page.locator(".vportal-step-credentials")).to_be_visible()


def test_vportal_help_in_the_stream_overlay_closes_with_the_dialog(page, competition, server_url):
    """Stream overlay of a VPortal session: the dialog opened from the panel
    ("S") has the "?" too. A click on the backdrop closes the dialog and the
    explanation; reopening starts with the explanation closed."""
    create_vportal_session(page, competition, server_url, "VP Overlay Help")
    overlay, _ = open_overlay(competition, name="VP Overlay Help")
    help_box = overlay.get_by_test_id("vportal-help")
    expect(help_box).to_be_hidden()

    overlay.keyboard.press("s")
    overlay.get_by_test_id("overlay-vportal-connect").click()
    expect(overlay.locator(".vportal-modal")).to_be_visible()
    _toggle_in_step(overlay, "en")
    overlay.get_by_test_id("vportal-help-toggle").click()
    expect(help_box).to_be_visible()

    overlay.locator(".vportal-modal-backdrop").click(position={"x": 5, "y": 5})
    expect(overlay.locator(".vportal-modal")).to_be_hidden()
    expect(help_box).to_be_hidden()
    # Opening the dialog closed the panel: "S" again to reach the button.
    overlay.keyboard.press("s")
    overlay.get_by_test_id("overlay-vportal-connect").click()
    expect(overlay.locator(".vportal-modal")).to_be_visible()
    expect(help_box).to_be_hidden()
