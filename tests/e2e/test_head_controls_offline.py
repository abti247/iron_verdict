"""Head judge controls without a connection — locked with a hint, never a silent no-op.

The head judge's network is cut with the WebSocket patch from
``network_switch.py``, so the client sees a real connection loss and keeps
retrying, also across a page reload.
"""

from playwright.sync_api import expect

from tests.e2e.network_switch import NETWORK_SWITCH, cut_network, restore_network

# Retries wait at most 3 s (websocket.js) — generous margin for slow CI runners.
RECONNECT_TIMEOUT = 20000

BUTTONS = ("Start Timer", "Reset Timer", "Next Lift", "End Session")
SETTINGS = ("show-explanations-checkbox", "require-reasons-checkbox", "lift-type-select")


def _head_with_network_switch(competition):
    head = competition.create_session_and_join_head()
    head.context.add_init_script(NETWORK_SWITCH)
    head.reload()
    head.locator(".judge-wrap").wait_for(state="visible")
    return head


def _expect_controls(head, enabled, timeout=None):
    check = "to_be_enabled" if enabled else "to_be_disabled"
    kwargs = {"timeout": timeout} if timeout else {}
    for name in BUTTONS:
        getattr(expect(head.get_by_role("button", name=name)), check)(**kwargs)
    for test_id in SETTINGS:
        getattr(expect(head.get_by_test_id(test_id)), check)(**kwargs)


def test_head_controls_locked_while_offline_and_active_again_after_reconnect(competition):
    """Head judge loses the connection → Start/Reset Timer, Next Lift, End Session
    and the settings are disabled and a hint says why; the head judge's own LOCK IN
    stays usable. Connection back → controls active without a reload and
    "Start Timer" starts the timer on the other judge's screen too. A reload while
    offline shows "Connecting…"; once back, the controls are active."""
    head = _head_with_network_switch(competition)
    left = competition.join_as("left_judge")
    hint = head.get_by_test_id("head-offline")

    _expect_controls(head, enabled=True)
    expect(hint).not_to_be_visible()

    cut_network(head)
    _expect_controls(head, enabled=False)
    expect(hint).to_have_text("No connection – controls are locked until the connection is back.")
    head.locator(".vote-btn.vote-white").click()
    expect(head.locator(".lock-btn")).to_be_enabled()

    restore_network(head)
    _expect_controls(head, enabled=True, timeout=RECONNECT_TIMEOUT)
    expect(hint).not_to_be_visible()

    head.get_by_role("button", name="Start Timer").click()
    expect(left.locator(".judge-timer")).not_to_have_text("60")

    cut_network(head)
    head.reload()
    expect(head.get_by_test_id("reconnecting-screen")).to_be_visible()

    restore_network(head)
    expect(head.locator(".judge-wrap")).to_be_visible(timeout=RECONNECT_TIMEOUT)
    _expect_controls(head, enabled=True)
    expect(hint).not_to_be_visible()
