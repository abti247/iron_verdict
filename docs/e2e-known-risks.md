# E2E Test Suite — Known Risks

Three tests have latent timing/race risks that could surface as intermittent failures (flakes). They all pass reliably today. This doc exists so that **when a test starts failing after a code change**, you can quickly check whether it's a known risk with a ready-to-apply fix.

## When to consult this doc

- An E2E test fails intermittently (passes on retry or passes locally but fails elsewhere)
- You just changed code in one of the trigger areas listed below

## When to verify stability after a code change

If you changed code in a trigger area, run the affected test 10 times to confirm it's still stable:

```bash
pip install pytest-repeat  # one-time
pytest tests/e2e/path/to/test.py::test_name --count=10 -v
```

Any failure out of 10 = flaky. Apply the fix documented below.

| Risk | Test | Code changes that warrant re-check |
|------|------|------------------------------------|
| Timer race | `test_timer_flow` | Timer logic, tick interval, `.judge-timer` rendering |
| Role rejection race | `test_cannot_join_taken_role` | Role locking, WebSocket reconnect, `handleJoinError` |
| Display orphan | `test_display_reconnects_after_refresh` | Display WS handling, connection cleanup, `display_XXXX` IDs |

---

## Risk 1: Timer assertion races — `test_timer_flow`

**File:** `tests/e2e/test_competition_flow.py:86`

**What it does:** Starts the 60s timer, then asserts `not_to_have_text("60")` to confirm the timer is counting down.

**Why it could flake:** If the assertion fires before the first tick (within ~1s of starting), the text is still "60" and the check fails. Playwright retries for up to 5s by default, which should be enough since the timer ticks every second — but a frozen or heavily loaded browser could delay the tick.

**Symptom:** `test_timer_flow` fails with `expected ".judge-timer" not to have text "60"`.

**Fix if it flakes:** Replace the `not_to_have_text("60")` assertion with an explicit wait for the value to change:

```python
head.get_by_role("button", name="Start Timer").click()
for p in (head, left, right):
    p.wait_for_function(
        '() => document.querySelector(".judge-timer")?.textContent?.trim() !== "60"',
        timeout=5000,
    )
```

---

## Risk 2: Auto-reconnect loop interference — `test_cannot_join_taken_role`

**File:** `tests/e2e/test_role_protection.py:7`

**What it does:** A fourth user clicks a taken role (Left). The test waits 2s then asserts `.judge-wrap` is not visible — confirming the user was rejected.

**Why it could flake:** The client's auto-reconnect loop retries WebSocket connections on failure. If the reconnect fires during the 2s wait window and the server has already freed the role (race condition), the intruder could accidentally succeed. This is unlikely with the current implementation since the original left judge is still connected, but server-side role locking changes could reintroduce the risk.

**Symptom:** `test_cannot_join_taken_role` fails with `.judge-wrap` unexpectedly becoming visible.

**Fix if it flakes:** Add explicit assertion that the intruder's page stays on role-select and did not transition:

```python
page.locator(".role-btn", has_text="Left").click()
# Wait and repeatedly confirm the user is still on role-select
for _ in range(4):
    page.wait_for_timeout(500)
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".judge-wrap")).not_to_be_visible()
```

Or disable auto-reconnect for the intruder's page via init script.

---

## Risk 3: Display orphan connections after reload — `test_display_reconnects_after_refresh`

**File:** `tests/e2e/test_display_resilience.py:7`

**What it does:** Display reloads, reconnects, then receives vote results.

**Why it could flake:** Display roles use a unique `display_XXXX` connection ID. On reload, the client opens a new WebSocket and gets a new ID. The old connection is orphaned on the server until its WebSocket close event fires. If the server is slow to clean up the old connection AND the test triggers a broadcast before cleanup completes, the new display connection might miss a message that went to the orphan.

**Symptom:** `test_display_reconnects_after_refresh` fails because `.verdict-stamp` never shows "Good Lift" after votes complete — the result broadcast went to the orphaned connection.

**Fix if it flakes:** Add a brief sleep after reload to ensure the old connection is cleaned up before voting:

```python
display.reload()
expect(display.locator(".display-full")).to_be_visible()
display.wait_for_timeout(500)  # let server clean up orphaned WS
competition.vote_all_white()
```

Or fix server-side: in the WebSocket handler, when a display reconnects with the same session code, proactively close the previous connection.

---

## Resolved (kept for reference)

These were flagged as unresolved during planning but resolved during implementation:

- **`set_offline()` for WebSocket**: Bypassed entirely — used WebSocket monkey-patching via init script instead (see `test_own_dot_orange_on_reconnecting`)
- **Server restart test complexity**: Solved by broadcasting `{"type": "server_restarting"}` via `connection_manager` without actually restarting the server (see `test_server_restart_message_shown`)
