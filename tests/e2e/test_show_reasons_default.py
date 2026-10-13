"""Show reasons on display — enabled by default, the chief referee can opt out,
and the chosen setting survives a reload of the chief referee and the display."""

from playwright.sync_api import expect


def red_lift_with_reason(competition, head, left, right):
    """Left judge votes red with a reason, the others white → Good Lift."""
    competition.vote_and_lock(head, "white")
    left.locator(".vote-btn.vote-red").click()
    left.locator(".reason-item").first.click()
    left.locator(".lock-btn").click()
    left.locator(".locked-status").wait_for(state="visible")
    competition.vote_and_lock(right, "white")


def expect_no_reason_on_display(display):
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    for reason in display.locator(".display-full .display-orb-reason").all():
        expect(reason).not_to_be_visible()


def test_reasons_shown_by_default_and_opt_out_survives_reload(competition):
    """New session: without touching the setting, "Show reasons on display" is
    checked and a red vote's reason appears on the display.

    The chief referee unchecks it → the next lift shows no reason. Then the
    display and the chief referee reload (connection dropped and re-established):
    the setting stays off — the stored choice wins over the default — and the
    following lift still shows no reason.
    """
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    checkbox = head.get_by_test_id("show-explanations-checkbox")
    expect(checkbox).to_be_checked()

    # -- Lift 1: default on → reason on display ------------------------------
    red_lift_with_reason(competition, head, left, right)
    expect(display.locator(".display-full .display-orb-reason").first).to_be_visible()

    # -- Opt out → lift 2 shows no reason ------------------------------------
    checkbox.uncheck()
    head.get_by_role("button", name="Next Lift").click()
    red_lift_with_reason(competition, head, left, right)
    expect_no_reason_on_display(display)

    # -- Reload display and chief referee → setting stays off ----------------
    display.reload()
    display.locator(".display-full").wait_for(state="visible")
    head.reload()
    head.locator(".judge-wrap").wait_for(state="visible")
    expect(head.get_by_test_id("show-explanations-checkbox")).not_to_be_checked()

    head.get_by_role("button", name="Next Lift").click()
    red_lift_with_reason(competition, head, left, right)
    expect_no_reason_on_display(display)
