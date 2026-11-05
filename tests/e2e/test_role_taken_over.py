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
RECONNECTING = "reconnecting-screen"
# Give-up limit is 25 s from the first rejection; allow for the time A needs
# to come back and receive it.
GIVE_UP_TIMEOUT_MS = 40000


def _take_over(competition, *roles):
    """Head judge and the remaining side judge join; for each of *roles* an
    original device A joins (with a network switch) and goes offline, then a
    replacement B takes the role. Returns {role: (device_a, device_b, dialogs)}."""
    competition.create_session_and_join_head()
    for role in ("left_judge", "right_judge"):
        if role not in roles:
            competition.join_as(role)
    devices = {}
    for role in roles:
        device_a = join_with_network_switch(competition, role)
        dialogs = []
        device_a.on("dialog", lambda d, dialogs=dialogs: dialogs.append(d.message))
        devices[role] = [device_a, None, dialogs]
    for role in roles:
        cut_network(devices[role][0])
        devices[role][1] = competition.join_as(role)
    return {role: tuple(v) for role, v in devices.items()}


def _stored_session(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem('iv_session'))")


def _assert_devices_b_undisturbed(competition, *devices_b):
    for device_b in devices_b:
        expect(device_b.locator(".judge-wrap")).to_be_visible()
        expect(device_b.locator(".judge-code .conn-dot")).not_to_have_class(re.compile(r"\breconnecting\b"))
    competition.vote_all_white()
    for device_b in devices_b:
        expect(device_b.locator(".locked-status")).to_be_visible()


def test_taken_role_shows_notice_on_role_select_after_reload_and_on_judge_screen(competition):
    """B takes "Left" and another B takes "Right" while the original devices
    are offline. Both cases wait out the give-up limit at the same time:

    - Left A reloads: "Connecting…" stays while the role is rejected, then
      after the give-up limit A shows role-select of the same session with the
      notice, its reconnect token is gone, no popup came up, and it stops
      trying to connect.
    - Right A's judge screen lost its connection; when its network is back (no
      reload), its rejoin attempts are rejected; after the give-up limit it
      shows role-select with the notice.

    Both Bs stay connected and can vote."""
    devices = _take_over(competition, "left_judge", "right_judge")
    left_a, left_b, left_dialogs = devices["left_judge"]
    right_a, right_b, right_dialogs = devices["right_judge"]

    left_a.evaluate("window.__ivRestoreNetwork()")
    left_a.reload()
    right_a.evaluate("window.__ivRestoreNetwork()")
    expect(left_a.get_by_test_id(RECONNECTING)).to_be_visible()
    expect(right_a.locator(".judge-wrap")).to_be_visible()
    # Several rejected attempts later, still within the limit: no notice yet.
    left_a.wait_for_function("window.__ivSocketCount() >= 3", timeout=10000)
    expect(left_a.get_by_test_id(RECONNECTING)).to_be_visible()

    expect(left_a.locator(NOTICE)).to_be_visible(timeout=GIVE_UP_TIMEOUT_MS)
    expect(left_a.locator(NOTICE)).to_have_text("Left Judge is now signed in on another device")
    expect(left_a.locator(".role-wrap .session-tag .code")).to_have_text(competition.session_code)
    left_a.locator(".lang-toggle-btn", has_text="DE").click()
    expect(left_a.locator(NOTICE)).to_have_text("KARI Links ist inzwischen auf einem anderen Gerät angemeldet")
    assert _stored_session(left_a) == {"code": competition.session_code}
    assert left_dialogs == []

    # The retry loop has ended: no further connection attempts. While it ran, a
    # rejected attempt was retried every ~0.5 s, so 2 s would show several.
    sockets = left_a.evaluate("window.__ivSocketCount()")
    left_a.wait_for_timeout(2000)
    assert left_a.evaluate("window.__ivSocketCount()") == sockets

    expect(right_a.locator(NOTICE)).to_be_visible(timeout=GIVE_UP_TIMEOUT_MS)
    expect(right_a.locator(".judge-wrap")).not_to_be_visible()
    assert _stored_session(right_a) == {"code": competition.session_code}
    assert right_dialogs == []

    _assert_devices_b_undisturbed(competition, left_b, right_b)


def test_role_freed_within_limit_rejoins_without_notice(competition):
    """Counter-case (short race): A reloads while B holds "Left" and gets
    rejected a few times, then B leaves within the limit. A rejoins as left
    judge on its own, without notice or popup, and can vote."""
    device_a, device_b, dialogs = _take_over(competition, "left_judge")["left_judge"]

    device_a.evaluate("window.__ivRestoreNetwork()")
    device_a.reload()
    device_a.wait_for_function("window.__ivSocketCount() >= 3", timeout=10000)
    expect(device_a.get_by_test_id(RECONNECTING)).to_be_visible()

    device_b.locator(".judge-code .code-link").click()
    expect(device_b.locator(ROLE_SELECT)).to_be_visible()

    expect(device_a.locator(".judge-wrap")).to_be_visible(timeout=10000)
    expect(device_a.locator(NOTICE)).not_to_be_visible()
    assert dialogs == []
    competition.pages["left_judge"] = device_a
    competition.vote_all_white()
    expect(device_a.locator(".locked-status")).to_be_visible()
