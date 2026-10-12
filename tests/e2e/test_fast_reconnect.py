"""Fast reconnect — after a connection loss the client retries within 3 s and
reconnects at once when the device comes back online or the tab becomes visible.

The judge's network is cut with the WebSocket patch from ``network_switch.py``;
every reconnect attempt fails until the network is restored.
"""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

# Attempts after a cut: 0.5, 1.5, 3.5, 6.5 s — four retries reach the 3 s cap
# within ~7 s. The old doubling backoff needed 15 s for that.
CAPPED_ATTEMPTS = 5
CAPPED_TIMEOUT = 12000
# Longest retry wait (3 s + 20 % jitter) plus margin for the connect itself.
MAX_RETRY_GAP_MS = 5000
# Much shorter than the remaining retry wait (>= 2.4 s right after a failed attempt).
IMMEDIATE_MS = 1500


def _wait_until_waiting_at_cap(page):
    page.wait_for_function(
        f"window.__ivSocketCount() >= {CAPPED_ATTEMPTS} && window.__ivLastSocketClosed()",
        timeout=CAPPED_TIMEOUT,
    )


def _setup(competition):
    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")
    display = competition.join_as("display")
    left = join_with_network_switch(competition, "left_judge")
    return head, left, right, display


def test_judge_reconnects_within_three_seconds_after_long_outage(competition):
    """Left judge is offline long enough for the retry wait to reach its cap.

    When the network returns, the judge is connected again within one capped
    retry wait (≤ 3.6 s) — not after up to 16 s as before. The vote cast
    afterwards is confirmed, and a reload reconnects as well.
    """
    head, left, right, display = _setup(competition)
    dot = left.locator(".judge-code .conn-dot")

    cut_network(left)
    _wait_until_waiting_at_cap(left)
    restore_network(left)

    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=MAX_RETRY_GAP_MS)
    expect(head.locator(".connectivity-dot", has_text="L")).to_have_class(
        re.compile(r"status-connected")
    )
    competition.vote_all_white()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    left.reload()
    left.locator(".judge-wrap").wait_for(state="visible")
    expect(left.locator(".judge-code .conn-dot")).to_have_class(re.compile(r"\bconnected\b"))


@pytest.mark.parametrize(
    "event_script",
    [
        "window.dispatchEvent(new Event('online'))",
        "document.dispatchEvent(new Event('visibilitychange'))",
    ],
    ids=["online", "visibilitychange"],
)
def test_judge_reconnects_at_once_when_back_online_or_visible(competition, event_script):
    """Left judge is offline and the client waits ~3 s for its next retry.

    The network returns and the browser reports the device online again (or the
    tab visible again): the client skips the rest of the wait and is connected
    well before the retry would have fired. Exactly one new socket is opened,
    and the judge's vote is confirmed on it.
    """
    head, left, right, display = _setup(competition)
    dot = left.locator(".judge-code .conn-dot")

    cut_network(left)
    _wait_until_waiting_at_cap(left)
    attempts = left.evaluate("window.__ivSocketCount()")
    restore_network(left)
    left.evaluate(event_script)

    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=IMMEDIATE_MS)
    assert left.evaluate("window.__ivSocketCount()") == attempts + 1

    competition.vote_all_white()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    assert left.evaluate("window.__ivSocketCount()") == attempts + 1
