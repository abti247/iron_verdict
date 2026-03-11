"""End session safety — only head judge can end, all get redirected."""

from playwright.sync_api import expect


def test_only_head_judge_can_end(competition):
    """Side judges do not see the End Session button."""
    head, left, right = competition.join_all_judges()

    expect(head.get_by_role("button", name="End Session")).to_be_visible()
    expect(left.get_by_role("button", name="End Session")).not_to_be_visible()
    expect(right.get_by_role("button", name="End Session")).not_to_be_visible()


def test_end_redirects_all_participants(competition):
    """Head judge ends session → all participants return to landing."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    # End session — confirmEndSession() shows confirm dialog (auto-accepted)
    # handleSessionEnded shows alert (auto-accepted)
    head.get_by_role("button", name="End Session").click()

    # All screens return to landing — check for a unique landing-screen element
    # since there are multiple .landing-wrap divs (landing, contact, demo-intro)
    for p in (head, left, right, display):
        expect(
            p.get_by_role("button", name="Create New Session")
        ).to_be_visible(timeout=5000)


def test_session_gone_after_end(competition):
    """After ending, joining with old code fails."""
    head = competition.create_session_and_join_head()
    code = competition.session_code

    head.get_by_role("button", name="End Session").click()
    expect(
        head.get_by_role("button", name="Create New Session")
    ).to_be_visible(timeout=5000)

    # Try to join ended session
    dialogs = []
    ctx = competition.browser.new_context(locale="en-US")
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(competition.url)

    page.locator('[x-model="joinCode"]').fill(code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")
    page.locator(".role-btn", has_text="Left").click()

    # Should get an error (session not found)
    page.wait_for_timeout(2000)
    assert len(dialogs) > 0, "Expected error dialog when joining ended session"
    expect(page.locator(".judge-wrap")).not_to_be_visible()
