"""E2E test infrastructure — server fixture, cleanup, and CompetitionHelper."""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from iron_verdict.main import app, session_manager, connection_manager
from iron_verdict.main import limiter


# ---------------------------------------------------------------------------
# 1. Session-scoped server fixture — starts real FastAPI on a random port
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def server_url():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

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
# 2. Per-test cleanup (autouse)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "locale": "en-US"}


@pytest.fixture(autouse=True)
def _reset_server_state():
    limiter.reset()
    yield
    session_manager.sessions.clear()
    connection_manager.active_connections.clear()


# ---------------------------------------------------------------------------
# 3. CompetitionHelper — encapsulates multi-browser test flows
# ---------------------------------------------------------------------------

class CompetitionHelper:
    ROLE_LABELS = {
        "left_judge": "Left",
        "center_judge": "Chief Referee",
        "right_judge": "Right",
        "display": "Display Screen",
    }

    def __init__(self, browser, url):
        self.browser = browser
        self.url = url
        self.contexts = []
        self.pages = {}
        self.session_code = None

    def cleanup(self):
        for ctx in self.contexts:
            try:
                ctx.close()
            except Exception:
                pass

    def create_session_and_join_head(self, name="Test Session"):
        """Create a session and join as head judge (center). Returns page."""
        ctx = self.browser.new_context(locale="en-US")
        self.contexts.append(ctx)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(self.url)

        page.locator('[x-model="newSessionName"]').fill(name)
        page.get_by_role("button", name="Create New Session").click()
        page.locator(".role-wrap").wait_for(state="visible")

        self.session_code = page.locator(".session-tag .code").text_content()
        assert self.session_code, "Failed to extract session code"

        page.locator(".role-btn", has_text="Chief Referee").click()
        page.locator(".judge-wrap").wait_for(state="visible")

        self.pages["center_judge"] = page
        return page

    def join_as(self, role):
        """Join the session as *role*. Returns page."""
        ctx = self.browser.new_context(locale="en-US")
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


# ---------------------------------------------------------------------------
# 4. Competition fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def competition(browser, server_url):
    helper = CompetitionHelper(browser, server_url)
    yield helper
    helper.cleanup()
