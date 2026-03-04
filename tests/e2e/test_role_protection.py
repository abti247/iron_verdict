"""Role protection — occupied roles blocked, freed on disconnect, switchable."""

import time
from playwright.sync_api import expect


def test_cannot_join_taken_role(competition):
    """Second user clicking a taken role sees an error and cannot reach the judge screen."""
    head, left, right = competition.join_all_judges()

    # A fourth user tries to join as left_judge (already taken)
    ctx = competition.browser.new_context()
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)

    page.locator('[x-model="joinCode"]').fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    page.locator(".role-btn", has_text="Left").click()

    # Should NOT reach judge screen (role is taken, error alert shown and accepted)
    page.wait_for_timeout(2000)
    expect(page.locator(".judge-wrap")).not_to_be_visible()


def test_role_freed_on_disconnect(competition):
    """Judge disconnects → role freed → new user can take it."""
    head, left, right = competition.join_all_judges()

    # Close left judge's browser context
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    time.sleep(0.5)

    # New user takes left_judge
    new_left = competition.join_as("left_judge")
    expect(new_left.locator(".judge-wrap")).to_be_visible()


def test_switch_role_via_session_code(competition):
    """Judge navigates to role-select, picks a different available role."""
    head = competition.create_session_and_join_head()
    left = competition.join_as("left_judge")

    # Left judge switches to right judge
    left.locator(".code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    left.wait_for_timeout(500)

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
