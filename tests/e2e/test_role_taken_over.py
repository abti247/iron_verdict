"""Role taken over — a judge device whose position was taken by another device
while it was offline stops retrying after the give-up limit (25 s of "Role
already taken" in a row) and shows role-select with a notice, instead of
"Connecting…" or a lost-connection judge screen forever. A rejection streak
that ends within the limit (the short reconnect race) stays silent.

Device A is the original left judge (with a network switch), device B the
replacement that takes "Left" while A is offline.
"""

import re

from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch

ROLE_SELECT = ".role-wrap"
NOTICE = ".role-wrap .role-notice"
RECONNECTING = '.landing-wrap[x-show="screen === \'reconnecting\'"]'
# Give-up limit is 25 s from the first rejection; allow for the time A needs
# to come back and receive it.
GIVE_UP_TIMEOUT_MS = 40000


def _take_over_left(competition):
    """Head and right judge join, A joins as left, goes offline, B takes left."""
    competition.create_session_and_join_head()
    competition.join_as("right_judge")
    device_a = join_with_network_switch(competition, "left_judge")
    dialogs = []
    device_a.on("dialog", lambda d: dialogs.append(d.message))
    cut_network(device_a)
    device_b = competition.join_as("left_judge")
    return device_a, device_b, dialogs


def _stored_session(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem('iv_session'))")


def _assert_device_b_undisturbed(competition, device_b):
    expect(device_b.locator(".judge-wrap")).to_be_visible()
    expect(device_b.locator(".judge-code .conn-dot")).not_to_have_class(re.compile(r"\breconnecting\b"))
    competition.vote_all_white()
    expect(device_b.locator(".locked-status")).to_be_visible()


def test_reloaded_device_with_taken_role_shows_notice_on_role_select(competition):
    """A reloads after B took "Left": "Connecting…" stays while the role is
    rejected, then after the give-up limit A shows role-select of the same
    session with the notice, its reconnect token is gone, and no popup came up.
    B stays connected and can vote."""
    device_a, device_b, dialogs = _take_over_left(competition)

    device_a.evaluate("window.__ivRestoreNetwork()")
    device_a.reload()
    expect(device_a.locator(RECONNECTING)).to_be_visible()
    # Several rejected attempts later, still within the limit: no notice yet.
    device_a.wait_for_function("window.__ivSocketCount() >= 3", timeout=10000)
    expect(device_a.locator(RECONNECTING)).to_be_visible()

    expect(device_a.locator(NOTICE)).to_be_visible(timeout=GIVE_UP_TIMEOUT_MS)
    expect(device_a.locator(NOTICE)).to_have_text("Left Judge is now signed in on another device")
    expect(device_a.locator(".role-wrap .session-tag .code")).to_have_text(competition.session_code)
    assert _stored_session(device_a) == {"code": competition.session_code}
    assert dialogs == []

    # The retry loop has ended: no further connection attempts.
    sockets = device_a.evaluate("window.__ivSocketCount()")
    device_a.wait_for_timeout(2000)
    assert device_a.evaluate("window.__ivSocketCount()") == sockets

    _assert_device_b_undisturbed(competition, device_b)


def test_judge_screen_with_taken_role_shows_notice_on_role_select(competition):
    """A's judge screen lost its connection while B took "Left". When A's
    network is back (no reload), its rejoin attempts are rejected; after the
    give-up limit A shows role-select with the notice. B stays connected."""
    device_a, device_b, dialogs = _take_over_left(competition)

    device_a.evaluate("window.__ivRestoreNetwork()")
    expect(device_a.locator(".judge-wrap")).to_be_visible()

    expect(device_a.locator(NOTICE)).to_be_visible(timeout=GIVE_UP_TIMEOUT_MS)
    expect(device_a.locator(".judge-wrap")).not_to_be_visible()
    assert _stored_session(device_a) == {"code": competition.session_code}
    assert dialogs == []

    _assert_device_b_undisturbed(competition, device_b)


def test_role_freed_within_limit_rejoins_without_notice(competition):
    """Counter-case (short race): A reloads while B holds "Left" and gets
    rejected a few times, then B leaves within the limit. A rejoins as left
    judge on its own, without notice or popup, and can vote."""
    device_a, device_b, dialogs = _take_over_left(competition)

    device_a.evaluate("window.__ivRestoreNetwork()")
    device_a.reload()
    device_a.wait_for_function("window.__ivSocketCount() >= 3", timeout=10000)
    expect(device_a.locator(RECONNECTING)).to_be_visible()

    device_b.locator(".judge-code .code-link").click()
    expect(device_b.locator(ROLE_SELECT)).to_be_visible()

    expect(device_a.locator(".judge-wrap")).to_be_visible(timeout=10000)
    expect(device_a.locator(NOTICE)).not_to_be_visible()
    assert dialogs == []
    competition.pages["left_judge"] = device_a
    competition.vote_all_white()
    expect(device_a.locator(".locked-status")).to_be_visible()
