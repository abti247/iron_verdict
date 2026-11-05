"""Connectivity indicators — L/R dots on head screen, own connection dot."""

import re
from playwright.sync_api import expect


def test_lr_dots_follow_side_judges(competition):
    """L/R dots start disconnected and turn green as side judges join; a side
    judge disconnects → only its dot goes disconnected; it rejoins → green."""
    head = competition.create_session_and_join_head()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    r_dot = head.locator(".connectivity-dot", has_text="R")

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    expect(r_dot).to_have_class(re.compile(r"status-disconnected"))

    competition.join_as("left_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))
    expect(r_dot).to_have_class(re.compile(r"status-disconnected"))

    competition.join_as("right_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))
    expect(r_dot).to_have_class(re.compile(r"status-connected"))

    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    expect(r_dot).to_have_class(re.compile(r"status-connected"))

    competition.join_as("left_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))


def test_own_dot_orange_on_reconnecting(competition):
    """All three judges' own dots are green after joining; the left judge's
    connection drops → its dot shows 'reconnecting' → reconnects → green.

    Closes the raw WebSocket via JS (tracked by init_script monkey-patch)
    to trigger the onclose handler, which sets connectionStatus to 'reconnecting'.
    The auto-reconnect then restores 'connected'.
    """
    # Create left judge with WebSocket tracking init script
    ctx = competition.new_context()
    ctx.add_init_script("""
        window.__ws_instances = [];
        const OrigWebSocket = window.WebSocket;
        window.WebSocket = function(...args) {
            const ws = new OrigWebSocket(...args);
            window.__ws_instances.push(ws);
            return ws;
        };
        window.WebSocket.prototype = OrigWebSocket.prototype;
        window.WebSocket.CONNECTING = OrigWebSocket.CONNECTING;
        window.WebSocket.OPEN = OrigWebSocket.OPEN;
        window.WebSocket.CLOSING = OrigWebSocket.CLOSING;
        window.WebSocket.CLOSED = OrigWebSocket.CLOSED;
    """)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())

    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")

    # Join left judge on the patched context
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Left").click()
    page.locator(".judge-wrap").wait_for(state="visible")
    competition.pages["left_judge"] = page

    for p in (head, page, right):
        expect(p.locator(".judge-code .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))
    dot = page.locator(".judge-code .conn-dot")

    # Close the raw WebSocket to trigger onclose → reconnecting
    page.evaluate("window.__ws_instances.filter(ws => ws.readyState === 1).forEach(ws => ws.close())")
    expect(dot).to_have_class(re.compile(r"\breconnecting\b"), timeout=10000)

    # Auto-reconnect should restore connected status
    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=15000)


def test_server_restart_message_shown(competition, server_url):
    """Server sends server_restarting → label visible.

    Deliberate exception to "don't simulate server internals" (docs/testing.md,
    "Conventions"): the message is only sent while the server shuts down, and
    the in-process test server cannot be restarted under a running test, so the
    broadcast is triggered directly on ``connection_manager``. That the shutdown
    handler sends it to every session is pinned in the backend test
    ``test_shutdown_tells_every_connected_session_the_server_restarts``; this
    test is the only one that shows the label on screen."""
    import asyncio
    import threading
    from iron_verdict.main import connection_manager as cm

    head, left, right = competition.join_all_judges()

    label = left.locator(".judge-wrap .conn-label")
    expect(label).not_to_be_visible()

    # Run the async broadcast in a separate thread with its own event loop
    # (the main thread already has a running loop from Playwright/pytest-asyncio)
    exc_holder = []

    def broadcast():
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                cm.broadcast_to_session(
                    competition.session_code, {"type": "server_restarting"}
                )
            )
            loop.close()
        except Exception as e:
            exc_holder.append(e)

    t = threading.Thread(target=broadcast)
    t.start()
    t.join(timeout=5)
    if exc_holder:
        raise exc_holder[0]

    expect(label).to_be_visible()
    expect(label).to_have_text("Server restarting")
