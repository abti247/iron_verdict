from playwright.sync_api import expect


def test_ci_demo_deliberately_red(competition):
    """Temporary CI demo for #49: judges join, then an assertion that must fail.

    Proves that a red E2E test fails the required `e2e` check and that the
    traces/screenshots artifact is uploaded. Reverted right after the demo.
    """
    head, _left, _right = competition.join_all_judges()
    expect(head.locator(".judge-wrap")).to_have_text("this text never appears", timeout=2000)
