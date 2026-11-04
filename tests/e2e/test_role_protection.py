"""Role protection — occupied roles blocked, freed on disconnect, switchable."""

import re
from playwright.sync_api import expect


def test_cannot_join_taken_role(competition):
    """Second user clicking a taken role sees an error and cannot reach the judge screen."""
    head, left, right = competition.join_all_judges()

    # A fourth user tries to join as left_judge (already taken)
    ctx = competition.new_context()
    page = ctx.new_page()
    page.goto(competition.url)

    page.get_by_test_id("join-code-input").fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    # The handler accepts the alert as it opens, before the click returns
    # (see docs/testing.md, "Conventions").
    with page.expect_event("dialog") as dialog_info:
        page.once("dialog", lambda d: d.accept())
        page.locator(".role-btn", has_text="Left").click()

    # The rejection is shown, and the user stays on role select
    assert dialog_info.value.message == "Failed to join session: Role already taken"
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".judge-wrap")).not_to_be_visible()


def test_role_freed_on_disconnect(competition):
    """Judge disconnects → role freed → new user can take it."""
    head, left, right = competition.join_all_judges()
    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    # Close left judge's browser context
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    # The server frees the role before it reports the judge as disconnected
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    # New user takes left_judge
    new_left = competition.join_as("left_judge")
    expect(new_left.locator(".judge-wrap")).to_be_visible()


def test_switch_role_via_session_code(competition):
    """Judge navigates to role-select, picks a different available role."""
    head = competition.create_session_and_join_head()
    left = competition.join_as("left_judge")
    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    # Left judge switches to right judge
    left.locator(".judge-code .code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    # The server frees the role before it reports the judge as disconnected
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    left.locator(".role-btn", has_text="Right").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    # Original left_judge role is now free
    new_left = competition.join_as("left_judge")
    expect(new_left.locator(".judge-wrap")).to_be_visible()


def test_head_judge_is_center(competition):
    """Only center_judge sees head judge controls."""
    head, left, right = competition.join_all_judges()

    expect(head.locator(".head-section").first).to_be_visible()
    expect(head.get_by_role("button", name="Next Lift")).to_be_visible()
    expect(head.get_by_role("button", name="End Session")).to_be_visible()

    for p in (left, right):
        expect(p.get_by_role("button", name="Next Lift")).not_to_be_visible()
        expect(p.get_by_role("button", name="End Session")).not_to_be_visible()
