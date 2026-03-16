"""Verify that the scroll indicator appears only when the reason list overflows."""

import re

from playwright.sync_api import expect


def test_scroll_indicator_shown_for_long_list(competition):
    """Bench yellow has 12 reasons — indicator should appear."""
    head = competition.create_session_and_join_head()

    # Set lift type to bench so yellow has 12 reasons
    head.evaluate("""() => {
        const app = document.querySelector('[x-data]');
        app._x_dataStack[0].liftType = 'bench';
    }""")

    # Select yellow vote
    head.locator(".vote-btn.vote-yellow").click()
    head.locator(".reason-list").wait_for(state="visible")

    # Wrapper should have overflow class
    wrap = head.locator(".reason-list-wrap")
    expect(wrap).to_have_class(re.compile(r"has-overflow-bottom"))


def test_scroll_indicator_hidden_for_short_list(competition):
    """Bench red has 2 reasons — indicator should NOT appear."""
    head = competition.create_session_and_join_head()

    head.evaluate("""() => {
        const app = document.querySelector('[x-data]');
        app._x_dataStack[0].liftType = 'bench';
    }""")

    # Select red vote (only 2 reasons)
    head.locator(".vote-btn.vote-red").click()
    head.locator(".reason-list").wait_for(state="visible")

    wrap = head.locator(".reason-list-wrap")
    expect(wrap).not_to_have_class(re.compile(r"has-overflow-bottom"))
