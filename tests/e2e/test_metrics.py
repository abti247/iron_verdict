"""Metrics endpoint (#133) — after a competition flow with a connection loss and
a reload, ``/metrics`` shows the real number of connected judges and displays
and counts every vote once, while voting keeps working.

Not ``remote_safe``: the token is set on the in-process server.
"""

import re

import httpx
import pytest
from playwright.sync_api import expect
from prometheus_client.parser import text_string_to_metric_families

from iron_verdict.config import settings
from tests.e2e.network_switch import cut_network, join_with_network_switch, restore_network

TOKEN = "e2e-metrics-token"


@pytest.fixture(autouse=True)
def metrics_token(monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", TOKEN)


def _scrape(server_url):
    r = httpx.get(f"{server_url}/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    return {
        (s.name, frozenset(s.labels.items())): s.value
        for family in text_string_to_metric_families(r.text)
        for s in family.samples
    }


def _disconnects(samples, reason):
    return samples[("iron_verdict_ws_disconnects_total", frozenset({("reason", reason)}))]


def _rejected(samples):
    return sum(v for (name, _), v in samples.items() if name == "iron_verdict_votes_rejected_total")


def test_metrics_match_competition_after_connection_loss_and_reload(competition, server_url):
    """Head, right judge and a display join; the left judge joins with a
    network switch. All vote white. The left judge loses the connection (head
    sees L disconnected) and reconnects, the right judge reloads the page.
    After the next lift all vote white again and the display shows Good Lift.
    /metrics then shows 3 judges, 1 display, 1 session, 6 votes, no
    rejections and the two lost connections — and is 404 without the token."""
    head = competition.create_session_and_join_head()
    right = competition.join_as("right_judge")
    display = competition.join_as("display")
    left = join_with_network_switch(competition, "left_judge")
    before = _scrape(server_url)

    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    l_dot = head.locator(".connectivity-dot", has_text="L")
    cut_network(left)
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    restore_network(left)
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    right.reload()
    expect(right.locator(".judge-wrap")).to_be_visible()
    expect(head.locator(".connectivity-dot", has_text="R")).to_have_class(re.compile(r"status-connected"))

    head.get_by_role("button", name="Next Lift").click()
    expect(display.locator(".verdict-stamp")).to_have_css("visibility", "hidden")
    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")

    after = _scrape(server_url)
    assert after[("iron_verdict_judges_connected", frozenset())] == 3
    assert after[("iron_verdict_displays_connected", frozenset())] == 1
    assert after[("iron_verdict_sessions_active", frozenset({("kind", "generic")}))] == 1
    assert after[("iron_verdict_votes_total", frozenset())] - before[("iron_verdict_votes_total", frozenset())] == 6
    assert _rejected(after) == _rejected(before)
    # The cut is seen as a closed socket; the reload either closes first or is
    # replaced by the new page's token reconnect. Each loss is counted once.
    lost = sum(_disconnects(after, r) - _disconnects(before, r) for r in ("client", "replaced"))
    assert lost == 2
    assert competition.session_code not in httpx.get(
        f"{server_url}/metrics", headers={"Authorization": f"Bearer {TOKEN}"}
    ).text
    assert httpx.get(f"{server_url}/metrics").status_code == 404
