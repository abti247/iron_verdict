"""Session expiry (#231) — a session with connected devices does not expire,
however long no vote, next lift or setting change happened.

Not ``remote_safe``: it ages the session and runs the expiry on the
in-process server (``run_on_server``).
"""

import re
from datetime import datetime, timedelta

import httpx
from playwright.sync_api import expect

from iron_verdict.config import settings
from iron_verdict.main import connection_manager, expire_sessions, session_manager
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

JUDGE_DOT = ".judge-code .conn-dot"
DISPLAY_DOT = ".display-tag .conn-dot"
CONNECTED = re.compile(r"\bconnected\b")


def test_connected_session_survives_expiry_then_reconnect_and_reload(competition, server_url, run_on_server):
    """Head judge, left judge and display are joined; the session's last
    activity lies past the timeout and the expiry runs. The session stays: the
    head judge starts the timer and the display counts down. Then the left
    judge and the display lose their connection and get it back, and all three
    reload — each comes back to its screen, connected."""
    head = competition.create_session_and_join_head()
    code = competition.session_code
    left = join_with_network_switch(competition, "left_judge")
    display = join_with_network_switch(competition, "display")
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)

    async def age_session():
        session_manager.sessions[code]["last_activity"] = datetime.now() - timedelta(
            hours=settings.SESSION_TIMEOUT_HOURS, minutes=15
        )

    run_on_server(age_session())
    run_on_server(expire_sessions(session_manager, connection_manager, settings.SESSION_TIMEOUT_HOURS))

    assert httpx.get(f"{server_url}/api/sessions/{code}").status_code == 200
    head.get_by_role("button", name="Start Timer").click()
    expect(display.locator(".display-timer-big")).to_have_text(re.compile(r"^(59|58|57)$"))
    expect(head.locator(JUDGE_DOT)).to_have_class(CONNECTED)

    cut_network(left)
    cut_network(display, conn_dot=DISPLAY_DOT)
    restore_network(left)
    restore_network(display)
    expect(left.locator(JUDGE_DOT)).to_have_class(CONNECTED)
    expect(display.locator(DISPLAY_DOT)).to_have_class(CONNECTED)

    for page, screen, dot in (
        (head, ".judge-wrap", JUDGE_DOT),
        (left, ".judge-wrap", JUDGE_DOT),
        (display, ".display-full", DISPLAY_DOT),
    ):
        page.reload()
        expect(page.locator(screen)).to_be_visible()
        expect(page.locator(dot)).to_have_class(CONNECTED)
    expect(display.locator(".display-timer-big")).to_have_text(re.compile(r"^(5\d)$"))
