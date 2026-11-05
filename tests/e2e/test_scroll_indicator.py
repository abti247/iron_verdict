"""Verify that the scroll indicator appears only when the reason list overflows."""

import re

from playwright.sync_api import expect


def test_scroll_indicator_only_for_long_list(competition):
    """Bench yellow has 12 reasons — the indicator appears. Back to the colours,
    bench red has 2 reasons — the indicator does not appear."""
    head = competition.create_session_and_join_head()

    # Set lift type to bench so yellow has 12 reasons
    head.get_by_test_id("lift-type-select").select_option("bench")
    wrap = head.locator(".reason-list-wrap")

    head.locator(".vote-btn.vote-yellow").click()
    head.locator(".reason-list").wait_for(state="visible")
    expect(wrap).to_have_class(re.compile(r"has-overflow-bottom"))

    head.locator(".back-btn").click()
    expect(head.locator(".vote-grid")).to_be_visible()

    # Red has only 2 reasons
    head.locator(".vote-btn.vote-red").click()
    head.locator(".reason-list").wait_for(state="visible")
    expect(wrap).not_to_have_class(re.compile(r"has-overflow-bottom"))
