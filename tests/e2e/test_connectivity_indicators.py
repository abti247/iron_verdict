"""Connectivity indicators — L/R dots on head screen, own connection dot."""

import re
import time
from playwright.sync_api import expect


def test_lr_dots_connected_on_join(competition):
    """L/R dots start disconnected, turn green as side judges join."""
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


def test_lr_dots_update_on_disconnect(competition):
    """Side judge disconnects → corresponding dot goes disconnected."""
    head, left, right = competition.join_all_judges()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    r_dot = head.locator(".connectivity-dot", has_text="R")

    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    expect(r_dot).to_have_class(re.compile(r"status-connected"))


def test_lr_dots_recover_on_reconnect(competition):
    """Side judge reconnects → dot returns to connected."""
    head, left, right = competition.join_all_judges()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    time.sleep(0.5)
    competition.join_as("left_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))


def test_own_dot_green_when_connected(competition):
    """Judge's own connection dot shows 'connected' class after joining."""
    head, left, right = competition.join_all_judges()

    for role in ("center_judge", "left_judge", "right_judge"):
        dot = competition.pages[role].locator(".judge-code .conn-dot")
        expect(dot).to_have_class(re.compile(r"\bconnected\b"))


def test_own_dot_orange_on_reconnecting(competition):
    """Connection drops → dot shows 'reconnecting' → reconnects → green.

    Closes the raw WebSocket via JS (tracked by init_script monkey-patch)
    to trigger the onclose handler, which sets connectionStatus to 'reconnecting'.
    The auto-reconnect then restores 'connected'.
    """
    # Create left judge with WebSocket tracking init script
    ctx = competition.browser.new_context(locale="en-US")
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
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())

    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")

    # Join left judge on the patched context
    page.goto(competition.url)
    page.locator('[x-model="joinCode"]').fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Left").click()
    page.locator(".judge-wrap").wait_for(state="visible")
    competition.pages["left_judge"] = page

    dot = page.locator(".judge-code .conn-dot")
    expect(dot).to_have_class(re.compile(r"\bconnected\b"))

    # Close the raw WebSocket to trigger onclose → reconnecting
    page.evaluate("window.__ws_instances.filter(ws => ws.readyState === 1).forEach(ws => ws.close())")
    expect(dot).to_have_class(re.compile(r"\breconnecting\b"), timeout=10000)

    # Auto-reconnect should restore connected status
    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=15000)


def test_server_restart_message_shown(competition, server_url):
    """Server sends server_restarting → label visible."""
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
