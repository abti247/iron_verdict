"""Lift type locked once a judge voted (#254).

A reason belongs to the lift type it was chosen for. Once a judge of the current
lift has voted, the chief referee cannot switch the lift type until "Next Lift";
a reason chosen (or still being sent) for the old lift type never ends up under
the new one. The rules themselves (which change is refused, which reason is
rejected) are pinned in the backend and Vitest tests; these tests show what the
devices display.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

# Retries wait at most 3 s (websocket.js) — generous margin for slow CI runners.
RECONNECT_TIMEOUT = 20000


def test_lift_type_change_refused_after_a_vote_until_next_lift(competition):
    """Left judge votes red with the squat reason "Depth"; the chief referee then
    picks "Bench Press".

    The chief referee sees the hint, and the select goes back to "squat". After
    "Next Lift" the hint is gone, the change goes through and the side judge is
    offered the bench reasons.
    """
    head, left, right = competition.join_all_judges()
    competition.vote_and_lock(left, "red", reason="Depth")

    select = head.get_by_test_id("lift-type-select")
    select.select_option("bench")

    expect(head.get_by_test_id("lift-type-locked")).to_be_visible()
    expect(select).to_have_value("squat")

    head.locator(".head-grid button", has_text="Next Lift").click()  # confirm dialog auto-accepted
    expect(head.get_by_test_id("lift-type-locked")).not_to_be_visible()

    select.select_option("bench")
    left.locator(".vote-btn.vote-red").click()
    expect(left.locator(".reason-item", has_text="Elbow depth")).to_be_visible()
    expect(head.get_by_test_id("lift-type-locked")).not_to_be_visible()
    expect(select).to_have_value("bench")


def test_reason_chosen_but_not_locked_is_dropped_when_lift_type_changes(competition):
    """Reasons are mandatory. Left judge picks red and the squat reason "Depth"
    without locking in; the chief referee switches to "Bench Press" (no one has
    voted yet, so it is allowed).

    The left judge's selection is cleared: LOCK IN disappears until a bench reason
    is picked, and the display shows the bench reason the judge then locks in.
    """
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")
    head.get_by_test_id("require-reasons-checkbox").check()

    left.locator(".vote-btn.vote-red").click()
    left.locator(".reason-item", has_text="Depth").click()
    expect(left.locator(".reason-item.selected")).to_have_text("Depth")
    expect(left.locator(".lock-btn")).to_be_visible()

    head.get_by_test_id("lift-type-select").select_option("bench")

    expect(left.locator(".reason-item", has_text="Elbow depth")).to_be_visible()
    expect(left.locator(".reason-item.selected")).to_have_count(0)
    expect(left.locator(".lock-btn")).not_to_be_visible()

    left.locator(".reason-item", has_text="Elbow depth").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".locked-status")).to_be_visible()
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")

    expect(display.locator(".display-full .display-orb-reason", has_text="Elbow depth")).to_be_visible()


def test_refused_lift_type_change_after_chief_referee_reload(competition):
    """The chief referee's lift type change is refused, then the chief referee
    reloads the page.

    After the reload the select shows the real lift type ("squat"), the old hint
    is gone, and a new attempt is refused again with the hint — the vote of the
    lift still exists on the server.
    """
    head, left, right = competition.join_all_judges()
    competition.vote_and_lock(left, "red", reason="Depth")
    head.get_by_test_id("lift-type-select").select_option("bench")
    expect(head.get_by_test_id("lift-type-locked")).to_be_visible()

    head.reload()
    head.locator(".judge-wrap").wait_for(state="visible")

    select = head.get_by_test_id("lift-type-select")
    expect(select).to_have_value("squat")
    expect(select).to_be_enabled()
    expect(head.get_by_test_id("lift-type-locked")).not_to_be_visible()

    select.select_option("deadlift")
    expect(head.get_by_test_id("lift-type-locked")).to_be_visible()
    expect(select).to_have_value("squat")


def test_offline_vote_with_old_reason_rejected_after_lift_type_change(competition):
    """Left judge loses the connection and locks in red with the squat reason
    "Depth"; meanwhile the chief referee switches to "Bench Press" (the server has
    no vote yet, so it is allowed).

    After reconnecting, the queued vote is rejected: the judge sees that the lift
    type changed, red stays selected and the bench reasons are offered. The judge
    picks one and the vote is locked.
    """
    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")
    left = join_with_network_switch(competition, "left_judge")

    cut_network(left)
    left.locator(".vote-btn.vote-red").click()
    left.locator(".reason-item", has_text="Depth").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".vote-sending-status")).to_be_visible()

    head.get_by_test_id("lift-type-select").select_option("bench")
    expect(head.get_by_test_id("lift-type-locked")).not_to_be_visible()

    restore_network(left)

    expect(left.locator(".vote-error")).to_contain_text("lift type has changed", timeout=RECONNECT_TIMEOUT)
    expect(left.locator(".vote-sending-status")).not_to_be_visible()
    expect(left.locator(".locked-status")).not_to_be_visible()
    expect(left.locator(".vote-btn.vote-red")).to_have_class(re.compile(r"\bselected\b"))
    expect(left.locator(".reason-item.selected")).to_have_count(0)

    left.locator(".reason-item", has_text="Elbow depth").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".vote-error")).not_to_be_visible()
