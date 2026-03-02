# Frontend E2E Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Playwright E2E tests guarding critical competition flows so judges can never lock themselves out during a live competition.

**Architecture:** pytest-playwright running against a real FastAPI server started in a background thread. Multiple browser contexts per test simulate judges + display. A `CompetitionHelper` class encapsulates session creation, role joining, voting, and assertions.

**Tech Stack:** pytest-playwright, Playwright sync API, Chromium, uvicorn (threaded)

---

### Task 1: Add dependencies and directory structure

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/e2e/__init__.py`

**Step 1: Add pytest-playwright to dev dependencies in pyproject.toml**

In `pyproject.toml`, add `"pytest-playwright>=0.6.2"` to the `dev` extras list alongside existing test deps.

**Step 2: Create empty init file**

```bash
mkdir -p tests/e2e
touch tests/e2e/__init__.py
```

**Step 3: Install dependencies and browsers**

```bash
pip install -e ".[dev]"
playwright install chromium
```

**Step 4: Commit**

```bash
git add pyproject.toml tests/e2e/__init__.py
git commit -m "chore: add pytest-playwright dependency and e2e directory"
```

---

### Task 2: E2E conftest — server fixture and competition helper

**Files:**
- Create: `tests/e2e/conftest.py`

**Step 1: Write conftest.py**

```python
"""E2E test infrastructure: real server + multi-browser competition helper."""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from iron_verdict.main import app, session_manager, connection_manager
from iron_verdict.main import limiter


# ---------------------------------------------------------------------------
# Server fixture (session-scoped — one server for all E2E tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def server_url():
    """Start real FastAPI server on a random port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is accepting connections
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("E2E server failed to start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Per-test cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_server_state():
    """Reset rate limiter and clean up sessions between tests."""
    limiter._storage.reset()
    yield
    session_manager.sessions.clear()
    connection_manager.active_connections.clear()


# ---------------------------------------------------------------------------
# Competition helper
# ---------------------------------------------------------------------------

class CompetitionHelper:
    """Drives a multi-participant competition through the browser UI."""

    ROLE_LABELS = {
        "left_judge": "Left",
        "center_judge": "Center",
        "right_judge": "Right",
        "display": "Display Screen",
    }

    def __init__(self, browser, url):
        self.browser = browser
        self.url = url
        self.contexts = []
        self.pages = {}
        self.session_code = None

    # -- lifecycle -----------------------------------------------------------

    def cleanup(self):
        for ctx in self.contexts:
            try:
                ctx.close()
            except Exception:
                pass

    # -- actions -------------------------------------------------------------

    def create_session_and_join_head(self, name="Test Session"):
        """Create a session and join as head judge (center). Returns page."""
        ctx = self.browser.new_context()
        self.contexts.append(ctx)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(self.url)

        page.locator('[x-model="newSessionName"]').fill(name)
        page.get_by_role("button", name="Create New Session").click()

        page.locator(".role-wrap").wait_for(state="visible")
        self.session_code = page.locator(".session-tag .code").text_content()

        page.locator(".role-btn", has_text="Center").click()
        page.locator(".judge-wrap").wait_for(state="visible")

        self.pages["center_judge"] = page
        return page

    def join_as(self, role):
        """Join the session as *role*. Returns page."""
        ctx = self.browser.new_context()
        self.contexts.append(ctx)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(self.url)

        page.locator('[x-model="joinCode"]').fill(self.session_code)
        page.get_by_role("button", name="Join Session").click()

        page.locator(".role-wrap").wait_for(state="visible")

        label = self.ROLE_LABELS[role]
        page.locator(".role-btn", has_text=label).click()

        if role == "display":
            page.locator(".display-full").wait_for(state="visible")
        else:
            page.locator(".judge-wrap").wait_for(state="visible")

        self.pages[role] = page
        return page

    def join_all_judges(self):
        """Create session + join all 3 judges. Returns (head, left, right)."""
        head = self.create_session_and_join_head()
        left = self.join_as("left_judge")
        right = self.join_as("right_judge")
        return head, left, right

    def vote_and_lock(self, page, color, reason=None):
        """Select color, optionally pick reason, and lock in."""
        page.locator(f".vote-btn.vote-{color}").click()
        if reason:
            page.locator(".reason-item", has_text=reason).click()
        page.locator(".lock-btn").click()
        page.locator(".locked-status").wait_for(state="visible")

    def vote_all_white(self):
        """All 3 judges vote white and lock in."""
        for role in ("center_judge", "left_judge", "right_judge"):
            self.vote_and_lock(self.pages[role], "white")

    def get_context_for(self, role):
        """Return the browser context that owns the page for *role*."""
        page = self.pages[role]
        for ctx in self.contexts:
            if page in ctx.pages:
                return ctx
        return None


@pytest.fixture()
def competition(browser, server_url):
    """Provide a CompetitionHelper wired to the running server."""
    helper = CompetitionHelper(browser, server_url)
    yield helper
    helper.cleanup()
```

**Step 2: Write smoke test to verify infrastructure**

Create `tests/e2e/test_smoke.py`:

```python
"""Smoke test — verify E2E infrastructure works."""

from playwright.sync_api import expect


def test_landing_page_loads(page, server_url):
    page.goto(server_url)
    expect(page.locator(".brand-iron")).to_have_text("Iron Verdict")


def test_create_session_shows_role_select(page, server_url):
    page.goto(server_url)
    page.locator('[x-model="newSessionName"]').fill("Smoke Test")
    page.get_by_role("button", name="Create New Session").click()
    expect(page.locator(".role-wrap")).to_be_visible()
    expect(page.locator(".session-tag .code")).not_to_be_empty()
```

**Step 3: Run smoke tests**

```bash
pytest tests/e2e/test_smoke.py -v
```

Expected: 2 tests PASS.

**Step 4: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_smoke.py
git commit -m "feat: add E2E test infrastructure with server fixture and competition helper"
```

---

### Task 3: test_competition_flow.py — happy path full lift cycle

**Files:**
- Create: `tests/e2e/test_competition_flow.py`

**Step 1: Write test file**

```python
"""Competition flow — happy path: full lift cycles, reasons, timer."""

import re
from playwright.sync_api import expect


def test_full_lift_cycle(competition):
    """Create → 3 judges join → all vote white → results → next lift → vote again."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    # -- Round 1: all white --------------------------------------------------
    competition.vote_all_white()

    # Results visible on judge screens
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".head-section").last).to_be_visible()

    # Display shows 3 white orbs and "Good Lift"
    for orb in display.locator(".display-orb").all():
        expect(orb).to_have_class(re.compile(r"\bwhite\b"))
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
    expect(display.locator(".verdict-stamp")).to_have_class(re.compile(r"\bvalid\b"))

    # -- Next Lift ------------------------------------------------------------
    head.get_by_role("button", name="Next Lift").click()

    # All judges can vote again (lock button hidden means not yet voted)
    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()

    # Display resets
    expect(display.locator(".verdict-stamp")).not_to_be_visible()

    # -- Round 2: mixed votes ------------------------------------------------
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "red")
    competition.vote_and_lock(right, "white")

    # 2 white + 1 red = "Good Lift" (majority white)
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")


def test_lift_cycle_with_required_reasons(competition):
    """Head judge enables require_reasons → judges must pick reason for non-white."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    # Enable settings
    head.locator('[x-model="showExplanations"]').check()
    head.locator('[x-model="requireReasons"]').check()

    # White vote locks without reason
    competition.vote_and_lock(head, "white")

    # Red vote requires reason
    left.locator(".vote-btn.vote-red").click()
    # Lock button should NOT be visible until reason selected
    expect(left.locator(".lock-btn")).not_to_be_visible()
    left.locator(".reason-item").first.click()
    left.locator(".lock-btn").click()
    left.locator(".locked-status").wait_for(state="visible")

    competition.vote_and_lock(right, "white")

    # Display shows reason for the red vote
    expect(display.locator(".display-orb-reason").first).to_be_visible()


def test_timer_flow(competition):
    """Head judge starts/resets 60s timer, visible on all screens."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    head.get_by_role("button", name="Start Timer").click()

    # Timer visible and counting on all screens
    for p in (head, left, right):
        expect(p.locator(".judge-timer")).not_to_have_text("60")
    expect(display.locator(".display-timer-big")).not_to_have_text("")

    # Reset
    head.get_by_role("button", name="Reset Timer").click()
    expect(head.locator(".judge-timer")).to_have_text("60")
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_competition_flow.py -v
```

Expected: 3 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_competition_flow.py
git commit -m "test: add competition flow E2E tests (happy path, reasons, timer)"
```

---

### Task 4: test_judge_reconnection.py

**Files:**
- Create: `tests/e2e/test_judge_reconnection.py`

**Step 1: Write test file**

```python
"""Judge reconnection — refresh/navigate-away must not break the session."""

import time
from playwright.sync_api import expect


def test_reconnect_before_voting(competition):
    """Judge refreshes before voting → returns to judge screen, can vote."""
    head, left, right = competition.join_all_judges()

    left.reload()
    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_enabled()

    # Verify full flow still works
    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()


def test_reconnect_after_voting(competition):
    """Judge refreshes after locking vote → vote restored, cannot re-vote."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "white")
    left.reload()

    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".vote-btn.vote-white")).to_be_disabled()


def test_reconnect_via_role_select(competition):
    """Judge clicks session code → role-select → re-selects role → state preserved."""
    head, left, right = competition.join_all_judges()

    # Click session code link to go back to role-select
    left.locator(".code-link").click()
    expect(left.locator(".role-wrap")).to_be_visible()

    # Re-select left judge
    left.locator(".role-btn", has_text="Left").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    # Full flow still works
    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()


def test_all_judges_reconnect_simultaneously(competition):
    """All 3 judges refresh at the same time → all reconnect, session continues."""
    head, left, right = competition.join_all_judges()

    head.reload()
    left.reload()
    right.reload()

    for p in (head, left, right):
        expect(p.locator(".judge-wrap")).to_be_visible()

    competition.vote_all_white()
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_judge_reconnection.py -v
```

Expected: 4 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_judge_reconnection.py
git commit -m "test: add judge reconnection E2E tests"
```

---

### Task 5: test_double_vote_prevention.py

**Files:**
- Create: `tests/e2e/test_double_vote_prevention.py`

**Step 1: Write test file**

```python
"""Double-vote prevention — locked votes must survive refresh and block re-voting."""

from playwright.sync_api import expect


def test_locked_vote_persists_after_refresh(competition):
    """Lock vote → refresh → vote still locked."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "red")
    left.reload()

    expect(left.locator(".judge-wrap")).to_be_visible()
    expect(left.locator(".locked-status")).to_be_visible()
    expect(left.locator(".locked-status")).to_contain_text("RED")


def test_cannot_vote_twice(competition):
    """After locking, vote buttons are disabled and lock button is hidden."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(left, "white")

    # Vote buttons disabled
    for color in ("white", "red", "blue", "yellow"):
        expect(left.locator(f".vote-btn.vote-{color}")).to_be_disabled()

    # Lock button not visible
    expect(left.locator(".lock-btn")).not_to_be_visible()


def test_vote_clears_after_next_lift(competition):
    """Full cycle → next lift → all judges can vote fresh."""
    head, left, right = competition.join_all_judges()

    competition.vote_all_white()

    # All locked
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()

    # All unlocked
    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_double_vote_prevention.py -v
```

Expected: 3 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_double_vote_prevention.py
git commit -m "test: add double-vote prevention E2E tests"
```

---

### Task 6: test_role_protection.py

**Files:**
- Create: `tests/e2e/test_role_protection.py`

**Step 1: Write test file**

```python
"""Role protection — occupied roles blocked, freed on disconnect, switchable."""

import time
from playwright.sync_api import expect


def test_cannot_join_taken_role(competition):
    """Second user clicking a taken role stays on role-select (silent handling)."""
    head, left, right = competition.join_all_judges()

    # A fourth user tries to join as left_judge (already taken)
    intruder = competition.join_as.__func__  # we need manual flow here
    ctx = competition.browser.new_context()
    competition.contexts.append(ctx)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(competition.url)

    page.locator('[x-model="joinCode"]').fill(competition.session_code)
    page.get_by_role("button", name="Join Session").click()
    page.locator(".role-wrap").wait_for(state="visible")

    page.locator(".role-btn", has_text="Left").click()

    # Should NOT reach judge screen (role is taken, error silently handled)
    page.wait_for_timeout(2000)
    expect(page.locator(".judge-wrap")).not_to_be_visible()


def test_role_freed_on_disconnect(competition):
    """Judge disconnects → role freed → new user can take it."""
    head, left, right = competition.join_all_judges()

    # Close left judge's browser context
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    # Brief wait for server to process disconnect
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

    # Brief wait for server to free the left_judge role
    left.wait_for_timeout(500)

    left.locator(".role-btn", has_text="Right").click()
    expect(left.locator(".judge-wrap")).to_be_visible()

    # Original left_judge role is now free — another user can take it
    new_left = competition.join_as("left_judge")
    expect(new_left.locator(".judge-wrap")).to_be_visible()


def test_head_judge_is_center(competition):
    """Only center_judge sees head judge controls."""
    head, left, right = competition.join_all_judges()

    # Head judge sees controls
    expect(head.locator(".head-section").first).to_be_visible()
    expect(head.get_by_role("button", name="Next Lift")).to_be_visible()
    expect(head.get_by_role("button", name="End Session")).to_be_visible()

    # Side judges do NOT see head controls
    for p in (left, right):
        expect(p.get_by_role("button", name="Next Lift")).not_to_be_visible()
        expect(p.get_by_role("button", name="End Session")).not_to_be_visible()
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_role_protection.py -v
```

Expected: 4 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_role_protection.py
git commit -m "test: add role protection E2E tests"
```

---

### Task 7: test_connectivity_indicators.py

**Files:**
- Create: `tests/e2e/test_connectivity_indicators.py`

**Step 1: Write test file**

```python
"""Connectivity indicators — L/R dots on head screen, own connection dot."""

import re
import time
from playwright.sync_api import expect


def test_lr_dots_connected_on_join(competition):
    """L/R dots start disconnected, turn green as side judges join."""
    head = competition.create_session_and_join_head()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    r_dot = head.locator(".connectivity-dot", has_text="R")

    # Both disconnected before side judges join
    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    expect(r_dot).to_have_class(re.compile(r"status-disconnected"))

    # Left joins → L turns connected
    competition.join_as("left_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))
    expect(r_dot).to_have_class(re.compile(r"status-disconnected"))

    # Right joins → R turns connected
    competition.join_as("right_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))
    expect(r_dot).to_have_class(re.compile(r"status-connected"))


def test_lr_dots_update_on_disconnect(competition):
    """Side judge disconnects → corresponding dot goes disconnected."""
    head, left, right = competition.join_all_judges()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    r_dot = head.locator(".connectivity-dot", has_text="R")

    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    # Close left judge
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))
    expect(r_dot).to_have_class(re.compile(r"status-connected"))


def test_lr_dots_recover_on_reconnect(competition):
    """Side judge reconnects → dot returns to connected."""
    head, left, right = competition.join_all_judges()

    l_dot = head.locator(".connectivity-dot", has_text="L")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))

    # Close and reconnect left judge
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    expect(l_dot).to_have_class(re.compile(r"status-disconnected"))

    time.sleep(0.5)
    competition.join_as("left_judge")
    expect(l_dot).to_have_class(re.compile(r"status-connected"))


def test_own_dot_green_when_connected(competition):
    """Judge's own connection dot shows 'connected' class after joining."""
    head, left, right = competition.join_all_judges()

    for role in ("center_judge", "left_judge", "right_judge"):
        dot = competition.pages[role].locator(".judge-code .conn-dot")
        expect(dot).to_have_class(re.compile(r"\bconnected\b"))


def test_own_dot_orange_on_reconnecting(competition):
    """Connection drops → dot shows 'reconnecting' → reconnects → green.

    Uses page.context.set_offline() to simulate network loss.
    """
    head, left, right = competition.join_all_judges()

    dot = left.locator(".judge-code .conn-dot")
    expect(dot).to_have_class(re.compile(r"\bconnected\b"))

    # Go offline
    left.context.set_offline(True)
    expect(dot).to_have_class(re.compile(r"\breconnecting\b"), timeout=10000)

    # Come back online
    left.context.set_offline(False)
    expect(dot).to_have_class(re.compile(r"\bconnected\b"), timeout=10000)


def test_server_restart_message_shown(competition, server_url):
    """Server sends server_restarting → label visible → reconnects → label hidden.

    NOTE: This test injects the message via the server's connection_manager
    rather than actually restarting the server, to avoid infrastructure complexity.
    """
    import asyncio
    from iron_verdict.main import connection_manager

    head, left, right = competition.join_all_judges()

    label = left.locator(".conn-label")
    expect(label).not_to_be_visible()

    # Broadcast server_restarting message via the connection manager
    loop = asyncio.new_event_loop()
    loop.run_until_complete(
        connection_manager.broadcast_to_session(
            competition.session_code, {"type": "server_restarting"}
        )
    )
    loop.close()

    expect(label).to_be_visible()
    expect(label).to_have_text("Server restarting")
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_connectivity_indicators.py -v
```

Expected: 6 PASS. The offline/server-restart tests may need timeout tuning — adjust if needed.

**Step 3: Commit**

```bash
git add tests/e2e/test_connectivity_indicators.py
git commit -m "test: add connectivity indicator E2E tests (L/R dots, conn dot, server restart)"
```

---

### Task 8: test_session_stuck_states.py

**Files:**
- Create: `tests/e2e/test_session_stuck_states.py`

**Step 1: Write test file**

```python
"""Session stuck states — session must never get stuck during competition."""

from playwright.sync_api import expect


def test_next_lift_when_not_all_voted(competition):
    """Only 2/3 vote → head judge clicks Next Lift (with confirm) → all reset."""
    head, left, right = competition.join_all_judges()

    # Only 2 judges vote
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "white")

    # Next Lift shows confirm dialog (results not shown yet) — auto-accepted
    head.get_by_role("button", name="Next Lift").click()

    # All judges can vote fresh
    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-btn.vote-white")).to_be_enabled()


def test_continue_after_judge_disconnect_mid_vote(competition):
    """Judge disconnects after partial voting → remaining judges still work."""
    head, left, right = competition.join_all_judges()

    competition.vote_and_lock(head, "white")

    # Left judge disconnects
    left_ctx = competition.get_context_for("left_judge")
    left_ctx.close()
    competition.contexts.remove(left_ctx)

    # Right judge can still vote
    competition.vote_and_lock(right, "white")

    # Head judge can still reset
    head.get_by_role("button", name="Next Lift").click()
    expect(head.locator(".locked-status")).not_to_be_visible()
    expect(head.locator(".vote-btn.vote-white")).to_be_enabled()


def test_next_lift_resets_all_state(competition):
    """Full cycle → Next Lift → voteLocked false, selectedVote cleared, resultsShown false."""
    head, left, right = competition.join_all_judges()

    competition.vote_all_white()

    # Results shown
    for role in ("center_judge", "left_judge", "right_judge"):
        expect(competition.pages[role].locator(".locked-status")).to_be_visible()

    head.get_by_role("button", name="Next Lift").click()

    for role in ("center_judge", "left_judge", "right_judge"):
        p = competition.pages[role]
        expect(p.locator(".locked-status")).not_to_be_visible()
        expect(p.locator(".vote-grid")).to_be_visible()
        # No vote is pre-selected
        expect(p.locator(".vote-btn.selected")).not_to_be_visible()
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_session_stuck_states.py -v
```

Expected: 3 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_session_stuck_states.py
git commit -m "test: add session stuck-state prevention E2E tests"
```

---

### Task 9: test_display_resilience.py

**Files:**
- Create: `tests/e2e/test_display_resilience.py`

**Step 1: Write test file**

```python
"""Display resilience — display must recover from refresh and support multiples."""

import re
from playwright.sync_api import expect


def test_display_reconnects_after_refresh(competition):
    """Display refreshes → reconnects and shows current state."""
    head, left, right = competition.join_all_judges()
    display = competition.join_as("display")

    display.reload()
    expect(display.locator(".display-full")).to_be_visible()

    # Verify the display still works after refresh — run full vote
    competition.vote_all_white()
    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")


def test_display_joins_mid_competition(competition):
    """Display joins after votes already started → shows correct state."""
    head, left, right = competition.join_all_judges()

    # Two judges vote before display joins
    competition.vote_and_lock(head, "white")
    competition.vote_and_lock(left, "white")

    display = competition.join_as("display")

    # Third judge votes → results shown on display
    competition.vote_and_lock(right, "white")

    expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")


def test_multiple_displays_receive_results(competition):
    """Two displays join → both show identical results after all votes."""
    head, left, right = competition.join_all_judges()
    display1 = competition.join_as("display")

    # Second display needs a fresh join — "display" key is reused, so use manual flow
    ctx = competition.browser.new_context()
    competition.contexts.append(ctx)
    display2 = ctx.new_page()
    display2.on("dialog", lambda d: d.accept())
    display2.goto(competition.url)
    display2.locator('[x-model="joinCode"]').fill(competition.session_code)
    display2.get_by_role("button", name="Join Session").click()
    display2.locator(".role-wrap").wait_for(state="visible")
    display2.locator(".role-btn", has_text="Display Screen").click()
    display2.locator(".display-full").wait_for(state="visible")

    competition.vote_all_white()

    for display in (display1, display2):
        expect(display.locator(".verdict-stamp")).to_have_text("Good Lift")
        for orb in display.locator(".display-orb").all():
            expect(orb).to_have_class(re.compile(r"\bwhite\b"))
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_display_resilience.py -v
```

Expected: 3 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_display_resilience.py
git commit -m "test: add display resilience E2E tests"
```

---

### Task 10: test_end_session.py

**Files:**
- Create: `tests/e2e/test_end_session.py`

**Step 1: Write test file**

```python
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

    # All screens return to landing
    for p in (head, left, right, display):
        expect(p.locator(".landing-wrap")).to_be_visible(timeout=5000)


def test_session_gone_after_end(competition):
    """After ending, joining with old code fails."""
    head = competition.create_session_and_join_head()
    code = competition.session_code

    head.get_by_role("button", name="End Session").click()
    expect(head.locator(".landing-wrap")).to_be_visible(timeout=5000)

    # Try to join ended session
    dialogs = []
    ctx = competition.browser.new_context()
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
```

**Step 2: Run tests**

```bash
pytest tests/e2e/test_end_session.py -v
```

Expected: 3 PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_end_session.py
git commit -m "test: add end session safety E2E tests"
```

---

### Task 11: Save design doc and finalize

**Files:**
- Create: `docs/plans/2026-03-02-frontend-e2e-testing-design.md`

**Step 1: Copy the design doc content**

Save the approved design document (the one created during brainstorming) to `docs/plans/2026-03-02-frontend-e2e-testing-design.md`.

**Step 2: Run full E2E suite**

```bash
pytest tests/e2e/ -v
```

Expected: ~25 tests PASS across 9 files.

**Step 3: Run backend tests to verify no regression**

```bash
pytest tests/ -v
```

Expected: all backend tests still pass.

**Step 4: Add changelog entry**

In `CHANGELOG.md` under `[Unreleased]`, add to `Added`:

```
- Playwright E2E test suite covering competition flow, reconnection, double-vote prevention, role protection, connectivity indicators, stuck states, display resilience, and session end
```

**Step 5: Final commit**

```bash
git add docs/plans/2026-03-02-frontend-e2e-testing-design.md CHANGELOG.md
git commit -m "docs: add E2E testing design doc and changelog entry"
```

---

## Unresolved Questions

1. **`set_offline()` for WebSocket** — `page.context.set_offline(True)` should affect WebSocket connections, but verify. If not, the orange-dot test (`test_own_dot_orange_on_reconnecting`) may need an alternative approach (e.g., firewall rule or server-side connection kill).

2. **`handleJoinError` silent handling** — "Role already taken" is silently swallowed. The `test_cannot_join_taken_role` test checks the user stays on role-select, but the auto-reconnect loop may keep retrying. Verify the test is stable.

3. **Timer assertion timing** — `test_timer_flow` asserts timer text is not "60" after starting. If the assertion runs before the timer ticks, it may be flaky. May need `page.wait_for_function()` to wait for the value to change.

4. **Display reconnect after reload** — The display role uses a unique `display_XXXX` ID. After reload, the client sends a new join with role `display`, getting a new ID. The old display connection is orphaned. Verify the server handles this correctly.
