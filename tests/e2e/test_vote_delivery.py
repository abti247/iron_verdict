"""Vote delivery — a vote is only shown as locked once the server confirmed it.

The judge's network is cut with the WebSocket patch from ``network_switch.py``,
so the client sees a real connection loss and keeps retrying, also across a
page reload.
"""

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

# Retries wait at most 3 s (websocket.js) — generous margin for slow CI runners.
RECONNECT_TIMEOUT = 20000


def setup_panel(competition):
    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")
    display = competition.join_as("display")
    left = join_with_network_switch(competition, "left_judge")
    return head, left, right, display


def test_vote_cast_offline_is_delivered_after_reconnect(competition):
    """Left judge loses the connection, votes white and presses LOCK IN.

    The UI must show "Sending…" (not "Vote Locked") while offline. When the
    connection returns, the queued vote reaches the server, the judge sees
    "Vote Locked" and the display shows the result.
    """
    head, left, right, display = setup_panel(competition)
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")

    cut_network(left)
    left.locator(".vote-btn.vote-white").click()
    left.locator(".lock-btn").click()

    expect(left.locator(".vote-sending-status")).to_be_visible()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(left.locator(".vote-btn.vote-red")).to_be_disabled()
    expect(display.locator(".verdict-stamp")).not_to_be_visible()

    restore_network(left)

    expect(left.locator(".locked-status")).to_be_visible(timeout=RECONNECT_TIMEOUT)
    expect(left.locator(".vote-sending-status")).not_to_be_visible()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift", timeout=RECONNECT_TIMEOUT)


def test_pending_vote_survives_reload(competition):
    """Left judge votes while offline, then reloads the page before reconnecting.

    The pending vote is kept in sessionStorage; after the reload and reconnect it
    is sent automatically and the result appears on the display.
    """
    head, left, right, display = setup_panel(competition)
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")

    cut_network(left)
    left.locator(".vote-btn.vote-white").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".vote-sending-status")).to_be_visible()

    left.reload()
    restore_network(left)

    expect(left.locator(".locked-status")).to_be_visible(timeout=RECONNECT_TIMEOUT)
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift", timeout=RECONNECT_TIMEOUT)


def test_pending_vote_discarded_when_lift_changed(competition):
    """Left judge votes offline; meanwhile the chief referee advances to the next lift.

    After reconnecting, the stale vote must not count for the new lift: the
    judge sees a "lift changed" message and can vote again.
    """
    head, left, right, display = setup_panel(competition)

    cut_network(left)
    left.locator(".vote-btn.vote-white").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".vote-sending-status")).to_be_visible()

    head.locator(".head-grid button", has_text="Next Lift").click()  # confirm dialog auto-accepted

    restore_network(left)

    expect(left.locator(".vote-error")).to_contain_text("next lift", timeout=RECONNECT_TIMEOUT)
    expect(left.locator(".vote-sending-status")).not_to_be_visible()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_enabled()

    # The judge can vote for the new lift; the message clears.
    competition.vote_and_lock(left, "white")
    expect(left.locator(".vote-error")).not_to_be_visible()


def test_stale_vote_without_reason_is_lift_changed_when_reasons_become_mandatory(competition):
    """Left judge votes red without a reason while offline; meanwhile the chief
    referee advances to the next lift and then makes reasons mandatory.

    After reconnecting, the queued vote belongs to the previous lift. The judge
    sees "lift changed" (not "reason required"), the vote is open again with no
    colour preselected and no reason step, so the old red cannot slip into the
    new lift.
    """
    head, left, right, display = setup_panel(competition)

    cut_network(left)
    left.locator(".vote-btn.vote-red").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".vote-sending-status")).to_be_visible()

    head.locator(".head-grid button", has_text="Next Lift").click()  # confirm dialog auto-accepted
    head.locator('[x-model="showExplanations"]').check()
    head.locator('[x-model="requireReasons"]').check()

    restore_network(left)

    expect(left.locator(".vote-error")).to_contain_text("next lift", timeout=RECONNECT_TIMEOUT)
    expect(left.locator(".vote-error")).not_to_contain_text("reason")
    expect(left.locator(".vote-sending-status")).not_to_be_visible()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(left.locator(".vote-btn.selected")).to_have_count(0)
    expect(left.locator(".reason-step")).not_to_be_visible()
    expect(left.locator(".vote-btn.vote-red")).to_be_enabled()


def test_rejected_vote_unlocks_ui_with_message(competition):
    """Left judge votes red without a reason while offline; meanwhile the chief
    referee makes reasons mandatory.

    After reconnecting the server rejects the queued vote. The judge screen
    unlocks and explains that a reason is required — no alert dialog.
    """
    head, left, right, display = setup_panel(competition)

    cut_network(left)
    left.locator(".vote-btn.vote-red").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".vote-sending-status")).to_be_visible()

    head.locator('[x-model="showExplanations"]').check()
    head.locator('[x-model="requireReasons"]').check()

    dialogs = []
    left.on("dialog", lambda d: dialogs.append(d.message))
    restore_network(left)

    expect(left.locator(".vote-error")).to_contain_text("reason", timeout=RECONNECT_TIMEOUT)
    expect(left.locator(".vote-sending-status")).not_to_be_visible()
    expect(left.locator(".locked-status")).not_to_be_visible()
    assert dialogs == []

    # Picking a reason and locking in again works.
    left.locator(".reason-item").first.click()
    left.locator(".lock-btn").click()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".vote-error")).not_to_be_visible()
