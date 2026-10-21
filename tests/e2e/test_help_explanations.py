"""In-place "?" explanations (#159).

Two places get a "?" that opens a full explanation right there, without a
link to another page: the display settings panel (gear or "S") explains the
panel itself — opening it, the pause, the layout editor, layout codes and the
contrast mode — in a box beside the panel that closes together with it. On
role-select, a "?" beside "Stream overlay (OBS)" explains how to add the
overlay to OBS, independent of the URL box. The display explanation never
shows on the free display or in the stream overlay while the panel is closed,
and the judge screen has no help elements at all. Both texts follow the
language toggle.
"""

from playwright.sync_api import expect

from tests.e2e.test_display_overlay import open_overlay

DISPLAY_TITLE = {"en": "How the display works", "de": "So funktioniert das Display"}
OBS_TITLE = {"en": "Stream overlay in OBS", "de": "Stream-Overlay in OBS"}


def join_display(competition, lang):
    """Join the current session as display with the given UI language."""
    ctx = competition.new_context()
    ctx.add_init_script(f"localStorage.setItem('iron-verdict-lang', '{lang}')")
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_test_id("join-code-input").press("Enter")
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-display-btn").click()
    page.locator(".display-full").wait_for(state="visible")
    return page


def open_role_select(competition):
    ctx = competition.new_context()
    page = ctx.new_page()
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    return page


def _check_display_help(page, lang):
    help_box = page.get_by_test_id("display-help")
    toggle = page.get_by_test_id("display-help-toggle")
    expect(toggle).to_be_hidden()
    expect(help_box).to_be_hidden()

    page.locator(".display-settings-gear").click()
    panel = page.locator(".display-settings-panel")
    expect(panel).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(help_box).to_be_hidden()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(help_box).to_be_visible()
    expect(help_box).to_contain_text(DISPLAY_TITLE[lang])
    # Beside the panel, not on top of its controls.
    panel_box, box = panel.bounding_box(), help_box.bounding_box()
    assert box["x"] >= panel_box["x"] + panel_box["width"] - 1
    # Clicking inside the explanation keeps the panel open.
    help_box.locator("h3").first.click()
    expect(panel).to_be_visible()

    toggle.click()
    expect(help_box).to_be_hidden()
    expect(panel).to_be_visible()

    # Closing the panel closes the explanation; reopening starts closed.
    toggle.click()
    expect(help_box).to_be_visible()
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(help_box).to_be_hidden()
    page.locator(".display-settings-gear").click()
    expect(panel).to_be_visible()
    expect(help_box).to_be_hidden()


def test_display_help_opens_and_closes_in_the_settings_panel_en_de(competition):
    """Display (EN, then DE): the "?" only exists in the open settings panel.
    It opens the explanation beside the panel and closes it again; closing
    the panel (Escape) closes the explanation too, and the next time the
    panel opens it starts closed."""
    competition.create_session_and_join_head()
    for lang in ("en", "de"):
        _check_display_help(join_display(competition, lang), lang)


def test_display_help_never_shows_in_the_stream_overlay_while_the_panel_is_closed(competition):
    """Stream overlay: neither the "?" nor the explanation is in the picture.
    "S" opens the panel with the "?"; the explanation opened there disappears
    with the next "S" together with the panel."""
    competition.create_session_and_join_head()
    overlay, _ = open_overlay(competition)
    help_box = overlay.get_by_test_id("display-help")
    toggle = overlay.get_by_test_id("display-help-toggle")
    expect(toggle).to_be_hidden()
    expect(help_box).to_be_hidden()

    overlay.keyboard.press("s")
    expect(overlay.locator(".display-settings-panel")).to_be_visible()
    toggle.click()
    expect(help_box).to_be_visible()
    expect(help_box).to_contain_text(DISPLAY_TITLE["en"])

    overlay.keyboard.press("s")
    expect(overlay.locator(".display-settings-panel")).to_be_hidden()
    expect(help_box).to_be_hidden()
    expect(toggle).to_be_hidden()


def test_overlay_link_help_opens_and_closes_and_follows_the_language(competition):
    """Role-select: the "?" beside "Stream overlay (OBS)" opens the OBS
    instructions without opening the URL box, and closes them again. With the
    explanation open, the language toggle switches it between EN and DE."""
    competition.create_session_and_join_head()
    page = open_role_select(competition)
    help_box = page.get_by_test_id("overlay-help")
    toggle = page.get_by_test_id("overlay-help-toggle")
    expect(help_box).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(help_box).to_be_visible()
    expect(help_box).to_contain_text(OBS_TITLE["en"])
    expect(help_box).to_contain_text("1920")
    expect(page.get_by_test_id("overlay-link-url")).to_be_hidden()

    page.locator(".lang-toggle-btn", has_text="DE").click()
    expect(help_box).to_contain_text(OBS_TITLE["de"])
    expect(help_box).to_contain_text("Browser")

    toggle.click()
    expect(help_box).to_be_hidden()


def test_judge_screen_has_no_help_elements(competition):
    """The judges' voting screen shows no "?" and no explanation."""
    head = competition.create_session_and_join_head()
    expect(head.locator(".judge-wrap")).to_be_visible()
    expect(head.locator(".help-toggle:visible")).to_have_count(0)
    expect(head.locator(".help-box:visible")).to_have_count(0)
