"""Reason catalog wording (issue #98) — bench and deadlift reasons follow the rulebook."""

from playwright.sync_api import expect


def _switch_to_german(page, ready_selector):
    """Persist German as UI language and reload; the page rejoins its seat."""
    page.evaluate("localStorage.setItem('iron-verdict-lang', 'de')")
    page.reload()
    page.locator(ready_selector).wait_for(state="visible")


def test_bench_yellow_head_shoulders_reason_shown_on_display(competition):
    """Bench press, German UI: the left judge votes yellow with
    "Kopf/Schultern angehoben" and the others white. The display shows the
    reason in exactly that wording, and the judge sees the split reasons
    ("Handbewegung" separately) and the shortened rack/bench texts."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    head.get_by_test_id("lift-type-select").select_option("bench")
    _switch_to_german(left, ".judge-wrap")
    _switch_to_german(display, ".display-full")

    left.locator(".vote-btn.vote-yellow").click()
    reasons = left.locator(".reason-item")
    for text in (
        "Kopf/Schultern angehoben",
        "Handbewegung",
        "Oberkörperstoß",
        "Füße berühren Bank",
        "Hantelkontakt mit Hantelständern",
    ):
        expect(reasons.filter(has_text=text)).to_have_count(1)
    expect(reasons.filter(has_text="Stützen")).to_have_count(0)
    expect(reasons.filter(has_text="Absichtlich")).to_have_count(0)

    reasons.filter(has_text="Kopf/Schultern angehoben").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".locked-status")).to_be_visible()
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(right, "white")

    expect(
        display.locator(".display-full .display-orb-reason", has_text="Kopf/Schultern angehoben")
    ).to_be_visible()


def test_deadlift_red_shoulders_not_behind_bar_selectable(competition):
    """Deadlift, red card: "Shoulders not behind bar" is offered (English UI)
    and can be locked in; the old "Shoulders not back" is gone. In German the
    same reason reads "Schultern nicht hinter Hantel"."""
    head, left, _right = competition.join_all_judges()
    head.get_by_test_id("lift-type-select").select_option("deadlift")

    left.locator(".vote-btn.vote-red").click()
    reasons = left.locator(".reason-item")
    expect(reasons.filter(has_text="Shoulders not behind bar")).to_have_count(1)
    expect(reasons.filter(has_text="Shoulders not back")).to_have_count(0)
    left.locator(".back-btn").click()

    _switch_to_german(left, ".judge-wrap")
    left.locator(".vote-btn.vote-red").click()
    left.locator(".reason-item", has_text="Schultern nicht hinter Hantel").click()
    left.locator(".lock-btn").click()
    expect(left.locator(".locked-status")).to_be_visible()
