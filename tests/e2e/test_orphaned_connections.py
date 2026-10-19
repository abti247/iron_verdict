"""Orphaned connections (#136) — a connection that ends without a regular
disconnect must not stay registered on the server.

Not ``remote_safe``: it lowers ``DISPLAY_CAP`` and reads the in-process
``connection_manager``.
"""

import re
import time

from playwright.sync_api import expect

from iron_verdict.config import settings
from iron_verdict.main import connection_manager
from tests.e2e.network_switch import NETWORK_SWITCH, cut_network, join_with_network_switch, restore_network

# Runs after NETWORK_SWITCH and wraps its WebSocket again, so the test can send
# raw messages on the page's socket and see the server's replies.
SOCKET_RECORDER = """
(() => {
    const Inner = window.WebSocket;
    window.__ws_instances = [];
    window.__ws_received = [];
    function Recorded(url, protocols) {
        const ws = new Inner(url, protocols);
        window.__ws_instances.push(ws);
        ws.addEventListener('message', (e) => window.__ws_received.push(JSON.parse(e.data)));
        return ws;
    }
    Recorded.prototype = Inner.prototype;
    Object.assign(Recorded, {CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3});
    window.WebSocket = Recorded;
})();
"""

DISPLAY_DOT = ".display-tag .conn-dot"
CONNECTED = re.compile(r"\bconnected\b")


def _join_display_with_recorder(competition):
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    ctx.add_init_script(SOCKET_RECORDER)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text=competition.ROLE_LABELS["display"]).click()
    page.locator(".display-full").wait_for(state="visible")
    competition.pages["display"] = page
    return page


def _registered_roles(code, timeout_s=5.0):
    """Poll until the server's registrations settle, then return them sorted."""
    deadline = time.monotonic() + timeout_s
    expected = ["center_judge", "display", "left_judge", "right_judge"]
    while True:
        roles = sorted(
            "display" if r.startswith("display_") else r
            # list() copies the keys in one step; the server thread may be
            # releasing the reloaded pages' old sockets meanwhile.
            for r in list(connection_manager.active_connections.get(code, {}))
        )
        if roles == expected or time.monotonic() > deadline:
            return roles
        time.sleep(0.05)


def test_no_orphaned_connection_after_second_join_and_connection_loss(competition, monkeypatch):
    """Only one display may be connected (DISPLAY_CAP = 1). The display's socket
    sends a second join — the trigger of the orphaned entry seen in PROD — and the
    server rejects it. Then the display and the left judge lose their connection,
    reconnect and reload.

    The display gets its slot back every time (an orphaned entry would block it
    with "Display cap reached"), the head judge sees the left judge disconnected
    and connected again, the vote reaches the display, and the server holds
    exactly one registration per device afterwards.
    """
    head = competition.create_session_and_join_head()
    competition.join_as("right_judge")
    left = join_with_network_switch(competition, "left_judge")
    display = _join_display_with_recorder(competition)
    monkeypatch.setattr(settings, "DISPLAY_CAP", 1)

    display.evaluate(
        "(code) => window.__ws_instances[0].send(JSON.stringify("
        "{type: 'join', session_code: code, role: 'display'}))",
        competition.session_code,
    )
    second_join_reply = display.wait_for_function(
        "window.__ws_received.find(m => m.type === 'error' || m.type === 'join_error')"
    ).json_value()
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)

    cut_network(display, DISPLAY_DOT)
    restore_network(display)
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED, timeout=10000)

    left_dot_on_head = head.locator(".connectivity-dot", has_text="L")
    cut_network(left)
    expect(left_dot_on_head).not_to_have_class(re.compile(r"status-connected"))
    restore_network(left)
    expect(left.locator(".judge-code .conn-dot")).to_have_class(CONNECTED, timeout=10000)
    expect(left_dot_on_head).to_have_class(re.compile(r"status-connected"))

    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    display.reload()
    display.locator(".display-full").wait_for(state="visible")
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)
    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")
    expect(left.locator(".judge-code .conn-dot")).to_have_class(CONNECTED)
    expect(left_dot_on_head).to_have_class(re.compile(r"status-connected"))

    assert second_join_reply == {"type": "error", "message": "Already joined"}
    assert _registered_roles(competition.session_code) == [
        "center_judge", "display", "left_judge", "right_judge",
    ]
