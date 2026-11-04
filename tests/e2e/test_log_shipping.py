"""Log shipping (#134) — a competition flow with a connection loss, a
reconnect and a reload runs normally while the Loki endpoint never answers,
and stdout still gets every event.

Not ``remote_safe``: the shipper is attached to the in-process server.
"""

import io
import json
import logging
import re
import socket

import pytest
from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network
from iron_verdict.log_shipping import LokiShipper


@pytest.fixture
def unreachable_loki():
    """Ship the server's logs to an address that accepts the connection and
    never answers; capture what the stdout handler writes meanwhile."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    url = f"http://127.0.0.1:{sock.getsockname()[1]}/loki/api/v1/push"
    app_logger = logging.getLogger("iron_verdict")
    stdout_handler = next(h for h in app_logger.handlers if isinstance(h, logging.StreamHandler))
    captured = io.StringIO()
    original_stream = stdout_handler.setStream(captured)
    previous_level = app_logger.level
    app_logger.setLevel(logging.INFO)
    # interval=0.1: the sender pushes (and hangs on the socket) from the first
    # second on, so the whole flow runs while Loki does not answer.
    shipper = LokiShipper(url, "123456", "e2e-token", "e2e", interval=0.1)
    shipper.start(app_logger)
    try:
        yield captured, sock
    finally:
        shipper.stop()
        stdout_handler.setStream(original_stream)
        app_logger.setLevel(previous_level)
        sock.close()


def _events(captured):
    return [json.loads(line) for line in captured.getvalue().splitlines() if line.startswith("{")]


def test_competition_runs_and_stdout_is_complete_while_loki_never_answers(competition, unreachable_loki):
    captured, loki_socket = unreachable_loki
    """Head, right judge and a display join; the left judge joins with a
    network switch. All vote white and the display shows Good Lift. The left
    judge loses the connection (head sees L disconnected) and reconnects, the
    right judge reloads the page. After the next lift all vote white again and
    the display shows Good Lift. The shipper has connected to the silent
    endpoint meanwhile. stdout has every join, all six votes and the
    lost connection, with the client IP."""
    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")
    display = competition.join_as("display")
    left = join_with_network_switch(competition, "left_judge")

    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    l_dot = head.locator(".connectivity-dot", has_text="L")
    cut_network(left)
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    restore_network(left)
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    right.reload()
    expect(right.locator(".judge-wrap")).to_be_visible()
    expect(head.locator(".connectivity-dot", has_text="R")).to_have_class(re.compile(r"status-connected"))

    head.get_by_role("button", name="Next Lift").click()
    expect(display.locator(".verdict-stamp")).to_have_css("visibility", "hidden")
    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    # The sender really did connect to the endpoint that never answers.
    loki_socket.setblocking(False)
    conn, _ = loki_socket.accept()
    conn.close()

    events = [e for e in _events(captured) if e.get("session_code") == competition.session_code]
    names = [e["message"] for e in events]
    assert names.count("vote_locked") == 6
    # head, right, display, left — then left after the cut and right after the reload
    assert names.count("role_joined") == 6
    assert "role_disconnected" in names
    assert "next_lift" in names
    assert all("client_ip" in e for e in events if e["message"] == "role_joined")
