"""Rate limits per client IP (issue #124) — behind Cloudflare and Railway every
request arrives from a proxy address, so the session lookup must be counted per
``CF-Connecting-IP``. One client using up its lookup limit must not keep a judge
on another network from joining or recovering after a reload.

Not ``remote_safe``: it relies on the default lookup limit (30/minute) and the
per-test ``limiter.reset()``; staging raises the limits.
"""

LOOKUP_LIMIT = 30


def test_exhausted_lookup_limit_of_one_network_does_not_block_judge_on_another(competition):
    """Network A uses up its 30 session lookups per minute and gets 429. A judge
    on network B (another CF-Connecting-IP) still joins, reloads and gets back
    to the judge screen, and its vote is confirmed by the server."""
    competition.create_session_and_join_head()
    lookup_url = f"{competition.url}/api/sessions/{competition.session_code}"

    other = competition.new_context(extra_http_headers={"CF-Connecting-IP": "198.51.100.1"})
    for _ in range(LOOKUP_LIMIT):
        assert other.request.get(lookup_url).status == 200
    assert other.request.get(lookup_url).status == 429

    judge_ctx = competition.new_context(extra_http_headers={"CF-Connecting-IP": "198.51.100.2"})
    judge = judge_ctx.new_page()
    judge.goto(competition.url)
    judge.get_by_test_id("join-code-input").fill(competition.session_code)
    judge.get_by_role("button", name="Join Session").click()
    judge.locator(".role-btn", has_text=competition.ROLE_LABELS["left_judge"]).click()
    judge.locator(".judge-wrap").wait_for(state="visible")

    judge.reload()
    judge.locator(".judge-wrap").wait_for(state="visible")

    competition.vote_and_lock(judge, "white")
