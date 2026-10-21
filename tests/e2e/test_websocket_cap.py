"""Global WebSocket cap (#61) — over ``MAX_WEBSOCKETS`` a new device is turned
away visibly, while a judge with a reconnect token always gets back in.

Not ``remote_safe``: it lowers ``MAX_WEBSOCKETS`` in-process.
"""

import re

from playwright.sync_api import expect

from iron_verdict.config import settings
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

JUDGE_DOT = ".judge-code .conn-dot"
CONNECTED = re.compile(r"\bconnected\b")
STATUS_CONNECTED = re.compile(r"status-connected")


def _try_join_display(competition):
    """Open a new device, pick the display role and return (page, join alert text)."""
    ctx = competition.new_context()
    page = ctx.new_page()
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    # The alert must be accepted as it opens: if the server's rejection arrives
    # while the click still waits for scheduled navigations, an open alert
    # blocks the page and the click never returns (seen on CI).
    with page.expect_event("dialog") as dialog_info:
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(".role-btn", has_text=competition.ROLE_LABELS["display"]).click()
    return page, dialog_info.value.message


def test_cap_rejects_new_device_but_admits_judge_reconnect_and_reload(competition, monkeypatch):
    """Three judges are connected and the server allows three WebSockets.

    A display that tries to join sees "Failed to join session: Server at capacity" and is
    not shown as a display. The left judge then loses the connection; while it is
    offline a display takes the freed slot, so the server is full again. The left
    judge reconnects with its reconnect token and gets back in, and again after a
    page reload. The head judge sees L connected again and the vote of all three
    judges is shown on the display.
    """
    head = competition.create_session_and_join_head()
    competition.join_as("right_judge")
    left = join_with_network_switch(competition, "left_judge")
    monkeypatch.setattr(settings, "MAX_WEBSOCKETS", 3)

    rejected, alert = _try_join_display(competition)
    assert alert == "Failed to join session: Server at capacity"
    expect(rejected.locator(".display-full")).to_be_hidden()

    left_dot_on_head = head.locator(".connectivity-dot", has_text="L")
    cut_network(left)
    expect(left_dot_on_head).not_to_have_class(STATUS_CONNECTED)
    display = competition.join_as("display")

    restore_network(left)
    expect(left.locator(JUDGE_DOT)).to_have_class(CONNECTED, timeout=10000)
    expect(left_dot_on_head).to_have_class(STATUS_CONNECTED)

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")
    expect(left.locator(JUDGE_DOT)).to_have_class(CONNECTED)
    expect(left_dot_on_head).to_have_class(STATUS_CONNECTED)

    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
