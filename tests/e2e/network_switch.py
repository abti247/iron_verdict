"""Test network switch for E2E tests — cut and restore one page's WebSocket.

Cutting closes the open socket and points every reconnect attempt at a closed
port, so the client sees a real connection loss and keeps retrying. The switch
lives in ``localStorage`` so it survives a page reload.
"""

import re

from playwright.sync_api import expect

NETWORK_SWITCH = """
(() => {
    const KEY = '__iv_test_offline';
    const Orig = window.WebSocket;
    const sockets = [];
    function Patched(url, protocols) {
        const offline = localStorage.getItem(KEY) === '1';
        const ws = new Orig(offline ? 'ws://127.0.0.1:9/offline' : url, protocols);
        sockets.push(ws);
        return ws;
    }
    Patched.prototype = Orig.prototype;
    Patched.CONNECTING = Orig.CONNECTING;
    Patched.OPEN = Orig.OPEN;
    Patched.CLOSING = Orig.CLOSING;
    Patched.CLOSED = Orig.CLOSED;
    window.WebSocket = Patched;
    window.__ivCutNetwork = () => {
        localStorage.setItem(KEY, '1');
        sockets.forEach(ws => { if (ws.readyState <= Orig.OPEN) ws.close(); });
    };
    window.__ivRestoreNetwork = () => localStorage.removeItem(KEY);
    // Number of connection attempts on this page so far (including failed ones).
    window.__ivSocketCount = () => sockets.length;
    window.__ivLastSocketClosed = () => sockets[sockets.length - 1].readyState === Orig.CLOSED;
})();
"""


def join_with_network_switch(competition, role):
    ctx = competition.new_context()
    ctx.add_init_script(NETWORK_SWITCH)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text=competition.ROLE_LABELS[role]).click()
    page.locator(".display-full" if role == "display" else ".judge-wrap").wait_for(state="visible")
    competition.pages[role] = page
    return page


def cut_network(page, conn_dot=".judge-code .conn-dot"):
    """Cut the page's socket; pass ``conn_dot=".display-tag .conn-dot"`` for a display."""
    page.evaluate("window.__ivCutNetwork()")
    expect(page.locator(conn_dot)).to_have_class(re.compile(r"\breconnecting\b"))


def restore_network(page):
    page.evaluate("window.__ivRestoreNetwork()")
