"""Back navigation — clickable display header, browser back, swipe-back."""

from playwright.sync_api import expect


def test_display_session_name_is_clickable_returns_to_role_select(competition):
    """Clicking the session name on the display screen returns to role-select."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")

    display.locator(".display-tag .code-link").click()

    expect(display.locator(".role-wrap")).to_be_visible()
    expect(display.locator(".display-full")).not_to_be_visible()


def test_judge_browser_back_returns_to_role_select(competition):
    """Pressing the browser back button on the judge screen returns to role-select."""
    head = competition.create_session_and_join_head()

    head.go_back()

    expect(head.locator(".role-wrap")).to_be_visible()
    expect(head.locator(".judge-wrap")).not_to_be_visible()


def test_display_browser_back_returns_to_role_select(competition):
    """Browser back from the display screen returns to role-select."""
    competition.create_session_and_join_head()
    display = competition.join_as("display")

    display.go_back()

    expect(display.locator(".role-wrap")).to_be_visible()
    expect(display.locator(".display-full")).not_to_be_visible()


def test_role_select_browser_back_returns_to_landing(competition):
    """Browser back from role-select returns to the landing screen."""
    ctx = competition.browser.new_context(locale="en-US")
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)

    page.locator('[x-model="newSessionName"]').fill("Back-Nav Test")
    page.get_by_role("button", name="Create New Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    page.go_back()

    expect(page.locator('.landing-wrap[x-show*="\'landing\'"]')).to_be_visible()
    expect(page.locator(".role-wrap")).not_to_be_visible()


def test_two_step_back_jump_from_judge_to_landing(competition):
    """A single history.go(-2) from the judge screen lands on landing and closes the WebSocket."""
    head = competition.create_session_and_join_head()

    head.evaluate("history.go(-2)")

    expect(head.locator('.landing-wrap[x-show*="\'landing\'"]')).to_be_visible()
    expect(head.locator(".judge-wrap")).not_to_be_visible()

    # Confirm the judge socket actually closed — sessionStorage cleared by returnToLanding.
    assert head.evaluate("sessionStorage.getItem('iv_session')") is None


def test_qr_entry_back_returns_to_landing(competition):
    """Arriving via ?session=<code>, then pressing back, returns to the landing screen."""
    competition.create_session_and_join_head()
    code = competition.session_code

    ctx = competition.browser.new_context(locale="en-US")
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(f"{competition.url}/?session={code}")

    page.locator(".role-wrap").wait_for(state="visible")

    page.go_back()

    expect(page.locator('.landing-wrap[x-show*="\'landing\'"]')).to_be_visible()
    expect(page.locator(".role-wrap")).not_to_be_visible()


def test_reload_recovery_back_returns_to_landing(competition):
    """After a reload-recovered auto-rejoin to judge, browser back returns to landing."""
    head = competition.create_session_and_join_head()

    head.reload()
    head.locator(".judge-wrap").wait_for(state="visible")

    head.go_back()

    expect(head.locator('.landing-wrap[x-show*="\'landing\'"]')).to_be_visible()
    expect(head.locator(".judge-wrap")).not_to_be_visible()
