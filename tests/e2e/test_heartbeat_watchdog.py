"""Heartbeat watchdog — a half-open connection is detected and replaced by the client."""

import re
from playwright.sync_api import expect

# Client watchdog fires 15–17.5 s after the last server message (websocket.js).
WATCHDOG_DETECT_MS = 25000

# Wraps WebSocket so the test can turn the *first* socket into a half-open one:
# while window.__blackhole is true, its incoming messages and its close event
# never reach the app — exactly what the browser sees when a router silently
# drops the connection. Later sockets (the reconnect) behave normally.
HALF_OPEN_INIT_SCRIPT = """
    window.__ws_instances = [];
    window.__blackhole = false;
    const OrigWebSocket = window.WebSocket;
    window.WebSocket = function(...args) {
        const ws = new OrigWebSocket(...args);
        const index = window.__ws_instances.push(ws) - 1;
        const silenced = () => window.__blackhole && index === 0;
        for (const type of ['message', 'close']) {
            let handler = null;
            ws.addEventListener(type, (event) => {
                if (!silenced() && handler) handler.call(ws, event);
            });
            Object.defineProperty(ws, 'on' + type, {
                get: () => handler,
                set: (h) => { handler = h; },
                configurable: true,
            });
        }
        return ws;
    };
    window.WebSocket.prototype = OrigWebSocket.prototype;
    window.WebSocket.CONNECTING = OrigWebSocket.CONNECTING;
    window.WebSocket.OPEN = OrigWebSocket.OPEN;
    window.WebSocket.CLOSING = OrigWebSocket.CLOSING;
    window.WebSocket.CLOSED = OrigWebSocket.CLOSED;
"""


def _join_with_half_open_socket(competition, role):
    ctx = competition.new_context()
    ctx.add_init_script(HALF_OPEN_INIT_SCRIPT)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)
    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text=competition.ROLE_LABELS[role]).click()
    if role == "display":
        page.locator(".display-full").wait_for(state="visible")
    else:
        page.locator(".judge-wrap").wait_for(state="visible")
    competition.pages[role] = page
    return page


def _socket_count(page):
    return page.evaluate("window.__ws_instances.length")


def _record_dot_states(page, selector):
    # On localhost the reconnect takes milliseconds, too short for a polling
    # assertion to see "reconnecting" — record every class change instead.
    page.evaluate("""(selector) => {
        const dot = document.querySelector(selector);
        window.__dot_states = [];
        new MutationObserver(() => window.__dot_states.push(dot.className))
            .observe(dot, { attributes: true, attributeFilter: ['class'] });
    }""", selector)


def _expect_watchdog_reconnect(page, dot):
    page.wait_for_function("window.__ws_instances.length === 2", timeout=WATCHDOG_DETECT_MS)
    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=10000)
    states = page.evaluate("window.__dot_states")
    assert any(re.search(r"\breconnecting\b", s) for s in states), states


def test_judge_and_display_reconnect_when_heartbeat_stops(competition):
    """A display with a healthy connection keeps its socket for longer than the
    watchdog limit (pings arrive, no false reconnect). Then the left judge's
    and the display's connections turn half-open at the same time (no
    messages, no close event), so both watchdog waits run in parallel.

    For each, the watchdog notices the missing pings, the dot switches to
    reconnecting and a new socket connects. The head judge sees L connected,
    the judge's vote is confirmed on the new connection and the display shows
    the result. After a reload the judge is connected again.
    """
    head = competition.create_session_and_join_head()
    left = _join_with_half_open_socket(competition, "left_judge")
    competition.join_as("right_judge")
    display = _join_with_half_open_socket(competition, "display")

    judge_dot = left.locator(".judge-code .conn-dot")
    display_dot = display.locator(".display-tag .conn-dot")
    expect(judge_dot).to_have_class(re.compile(r"\bconnected\b"))
    expect(display_dot).to_have_class(re.compile(r"\bconnected\b"))
    assert _socket_count(left) == 1

    # Longer than the 15–17.5 s watchdog window: only heartbeat pings flow to
    # the display. The judge stays connected meanwhile, so no other message
    # reaches the display that could hide a false reconnect.
    display.wait_for_timeout(20000)
    assert _socket_count(display) == 1
    expect(display_dot).to_have_class(re.compile(r"\bconnected\b"))

    _record_dot_states(left, ".judge-code .conn-dot")
    _record_dot_states(display, ".display-tag .conn-dot")
    left.evaluate("window.__blackhole = true")
    display.evaluate("window.__blackhole = true")
    _expect_watchdog_reconnect(left, judge_dot)
    _expect_watchdog_reconnect(display, display_dot)

    expect(head.locator(".connectivity-dot", has_text="L")).to_have_class(
        re.compile(r"status-connected")
    )
    competition.vote_all_white()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")
    expect(left.locator(".judge-code .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))
