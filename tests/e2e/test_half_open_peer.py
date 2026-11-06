"""Half-open peer (#230) — a device that vanishes without closing its socket must
not disconnect anyone else, and its own reconnect must not wait for the old socket.

The vanished device is a raw TCP client: it does the WebSocket handshake, joins
as the left judge and then never reads or answers again (phone switched access
point, laptop lid closed). A browser cannot be made to stop answering a close
frame, so only a raw socket shows the server waiting for a close reply that
never comes.

Not ``remote_safe``: it lowers ``PONG_STALE_SECONDS`` on the in-process server
and opens a plain TCP connection to it.
"""

import base64
import json
import os
import re
import socket
import struct
import time
from urllib.parse import urlparse

from playwright.sync_api import expect

import iron_verdict.main as main_module

CONNECTED = re.compile(r"\bconnected\b")

# Longer than the browser watchdog (15–17.5 s without a server message,
# websocket.js): a sweep stuck on the dead socket would reconnect every device.
WATCHDOG_WINDOW_MS = 20000

# Counts the page's sockets, so a reconnect that is over in milliseconds on
# localhost is still seen.
SOCKET_COUNTER = """
(() => {
    const Orig = window.WebSocket;
    window.__ws_count = 0;
    function Counted(url, protocols) {
        window.__ws_count += 1;
        return new Orig(url, protocols);
    }
    Counted.prototype = Orig.prototype;
    Object.assign(Counted, {CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3});
    window.WebSocket = Counted;
})();
"""


def _frame(text):
    """A masked client text frame (RFC 6455)."""
    payload = text.encode()
    mask = os.urandom(4)
    header = bytes([0x81])
    if len(payload) < 126:
        header += bytes([0x80 | len(payload)])
    else:
        header += bytes([0x80 | 126]) + struct.pack("!H", len(payload))
    return header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def _read_text_frame(sock):
    """Read one unmasked server text frame and return its payload."""
    def read(n):
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            assert chunk, "server closed the raw socket"
            data += chunk
        return data

    first, second = read(2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", read(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read(8))[0]
    assert first & 0x0F == 0x1, f"expected a text frame, got opcode {first & 0x0F}"
    return read(length).decode()


def _join_and_go_silent(server_url, code, role):
    """Join *role* over a raw socket, return (socket, reconnect token), then never read again."""
    host, port = urlparse(server_url).hostname, urlparse(server_url).port
    sock = socket.create_connection((host, port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((
        f"GET /ws HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\nOrigin: {server_url}\r\n\r\n"
    ).encode())
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(1024)
    assert response.startswith(b"HTTP/1.1 101"), response
    sock.sendall(_frame(json.dumps({"type": "join", "session_code": code, "role": role})))
    join = json.loads(_read_text_frame(sock))
    assert join["type"] == "join_success", join
    return sock, join["reconnect_token"]


def _join_with_counter(competition, role):
    ctx = competition.new_context()
    ctx.add_init_script(SOCKET_COUNTER)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    return page


def test_vanished_judge_does_not_disconnect_others_and_reconnects_at_once(
    competition, server_url, monkeypatch
):
    """The left judge's device vanishes with its socket half open. The server
    drops it (the head judge sees L disconnected) while the head judge and the
    display keep their only socket for longer than the browser watchdog: their
    dots stay connected, no reconnect.

    Then the left judge comes back on a new device with its reconnect token,
    while the second dead socket still holds the slot: the judge is back in the
    session within seconds (the server does not wait for the old socket to
    close), its vote is confirmed and reaches the display, and after a reload
    the judge is connected again.
    """
    # Why 8 s: the server pings every 5 s, so a healthy client's last pong is
    # at most ~5 s old when the sweep checks it. 8 s keeps them fresh and shows
    # the dead socket 7 s earlier than the default 15 s.
    monkeypatch.setattr(main_module, "PONG_STALE_SECONDS", 8)

    head = competition.create_session_and_join_head()
    head_dot = head.locator(".judge-code .conn-dot")
    left_status = head.locator(".connectivity-dot", has_text="L")

    display = _join_with_counter(competition, "display")
    display.locator(".role-btn", has_text=competition.ROLE_LABELS["display"]).click()
    display.locator(".display-full").wait_for(state="visible")
    competition.pages["display"] = display
    display_dot = display.locator(".display-tag .conn-dot")
    competition.join_as("right_judge")

    dead, token = _join_and_go_silent(server_url, competition.session_code, "left_judge")
    try:
        expect(left_status).to_have_class(re.compile(r"status-connected"))
        # A healthy head judge page for the socket count: the fixture's page has no counter.
        head.add_init_script(SOCKET_COUNTER)
        head.reload()
        head.locator(".judge-wrap").wait_for(state="visible")
        expect(head_dot).to_have_class(CONNECTED)

        # Stale after 8 s, detected by the next sweep.
        expect(left_status).not_to_have_class(re.compile(r"status-connected"), timeout=20000)
        head.wait_for_timeout(WATCHDOG_WINDOW_MS)
        assert head.evaluate("window.__ws_count") == 1
        assert display.evaluate("window.__ws_count") == 1
        expect(head_dot).to_have_class(CONNECTED)
        expect(display_dot).to_have_class(CONNECTED)

        # A second dead socket holds the slot when the judge returns with its token.
        dead.close()
        dead, token = _join_and_go_silent(server_url, competition.session_code, "left_judge")
        expect(left_status).to_have_class(re.compile(r"status-connected"))

        left = _join_with_counter(competition, "left_judge")
        left.evaluate(
            "([code, token]) => sessionStorage.setItem('iv_session', JSON.stringify("
            "{code, role: 'left_judge', reconnect_token: token}))",
            [competition.session_code, token],
        )
        left.locator(".role-btn", has_text=competition.ROLE_LABELS["left_judge"]).click()
        left.locator(".judge-wrap").wait_for(state="visible")
        competition.pages["left_judge"] = left
        # Well below the watchdog limit: the join did not wait for the old socket.
        expect(left.locator(".judge-code .conn-dot")).to_have_class(CONNECTED, timeout=5000)
        assert left.evaluate("window.__ws_count") == 1
        expect(left_status).to_have_class(re.compile(r"status-connected"))

        competition.vote_all_white()
        expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

        left.reload()
        left.locator(".judge-wrap").wait_for(state="visible")
        expect(left.locator(".judge-code .conn-dot")).to_have_class(CONNECTED)
        expect(left_status).to_have_class(re.compile(r"status-connected"))
    finally:
        dead.close()
