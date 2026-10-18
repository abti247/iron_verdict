"""E2E test infrastructure — server fixture, cleanup, and CompetitionHelper.

Set ``E2E_BASE_URL`` (e.g. ``http://127.0.0.1:8000``) to run the tests against
an already running server — the Docker image in CI, later a staging
deployment — instead of starting the app in-process. In that mode the
fixtures cannot reset server state and there is no fake VPortal (tests using
``fake_vportal_url`` are skipped). Tests that import the in-process managers
directly (e.g. ``connection_manager``) do not work externally either; CI only
runs ``test_smoke.py`` in external mode and everything else in the ``e2e`` job
against the in-process server.

In external mode every session a test creates is ended after the test (see
``created_sessions``), so test runs against staging or production leave
no sessions in the server's snapshot.
"""

import json
import os
import socket
import threading
import time
from urllib.parse import urlparse

os.environ["TEST_MODE"] = "1"
os.environ["VPORTAL_FETCH_INTERVAL_MS"] = "2000"

import httpx
import pytest
import uvicorn
from httpx_ws import WebSocketDisconnect, connect_ws

from iron_verdict.main import app, session_manager, connection_manager
from iron_verdict.main import limiter

EXTERNAL_BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# 1. Session-scoped server fixture — starts real FastAPI on a random port
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def server_url():
    if EXTERNAL_BASE_URL:
        yield EXTERNAL_BASE_URL
        return

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
    if EXTERNAL_BASE_URL:
        # The state lives in another process; nothing to reset.
        yield
        return
    limiter.reset()
    yield
    session_manager.sessions.clear()
    connection_manager.active_connections.clear()


# How long _end_session waits for the head-judge slot to become free. The
# server frees it only once it has processed the closed browser's WebSocket
# close, which over a proxy (Railway) can lag behind the context close; a
# half-open connection is evicted by the heartbeat watchdog after 15 s.
END_SESSION_JOIN_TIMEOUT_S = 20
END_SESSION_RETRY_INTERVAL_S = 0.5
# How long _end_session waits for the ended session to disappear from lookups.
END_SESSION_DELETE_TIMEOUT_S = 5


def _end_session(base_url, code):
    """End session *code* on the external server the way the head judge does
    (join as center judge, ``end_session_confirmed``) and check it is gone."""
    with httpx.Client(base_url=base_url, timeout=10) as client:
        deadline = time.monotonic() + END_SESSION_JOIN_TIMEOUT_S
        while True:
            with connect_ws(f"{base_url}/ws", client, headers={"Origin": base_url}) as ws:
                ws.send_text(json.dumps({"type": "join", "session_code": code, "role": "center_judge"}))
                reply = json.loads(ws.receive_text(timeout=10))
                if reply["type"] == "join_success":
                    ws.send_text(json.dumps({"type": "end_session_confirmed"}))
                    # The server broadcasts session_ended, closes every socket
                    # (ours included) and deletes the session last.
                    try:
                        while True:
                            ws.receive_text(timeout=10)
                    except WebSocketDisconnect:
                        pass
                    break
            if reply.get("message") == "Session not found":
                return  # the test ended it itself (or it expired)
            if reply.get("message") != "Role already taken" or time.monotonic() > deadline:
                raise AssertionError(f"could not end test session {code}: {reply}")
            time.sleep(END_SESSION_RETRY_INTERVAL_S)

        # Deleting the session follows our socket's close without an await
        # barrier we can observe, so the lookup may still race it briefly.
        deadline = time.monotonic() + END_SESSION_DELETE_TIMEOUT_S
        while True:
            lookup = client.get(f"/api/sessions/{code}")
            if lookup.status_code != 200 or time.monotonic() > deadline:
                break
            time.sleep(END_SESSION_RETRY_INTERVAL_S)
        assert lookup.status_code == 404, (
            f"test session {code} not confirmed ended: lookup answered {lookup.status_code}"
        )


class _CreatedSessions(list):
    """Session codes, plus errors from reading a creation response."""

    def __init__(self):
        super().__init__()
        self.unrecorded = []


@pytest.fixture(autouse=True)
def created_sessions():
    """Codes of the sessions the current test created; in external mode each
    is ended after the test, also when the test failed.

    Browser-created sessions are recorded automatically (see ``new_context``).
    A test that creates a session over plain HTTP appends its code itself.
    Autouse fixtures are set up first and torn down last, so all browser
    contexts are closed (and the head-judge slot freed) before this runs.
    A session that cannot be ended fails the teardown, so it never stays
    behind unnoticed.
    """
    codes = _CreatedSessions()
    yield codes
    if not EXTERNAL_BASE_URL:
        return  # _reset_server_state clears the in-process sessions
    # Try every session even if one fails, so the error names all that stay open.
    failures = [f"session creation not recorded: {error}" for error in codes.unrecorded]
    for code in dict.fromkeys(codes):
        try:
            _end_session(EXTERNAL_BASE_URL, code)
        except Exception as exc:
            failures.append(f"{code}: {exc!r}")
    if failures:
        raise AssertionError("test sessions left open on the server:\n" + "\n".join(failures))


@pytest.fixture
def new_context(new_context, created_sessions):
    """pytest-playwright's ``new_context``; in external mode every context also
    records the codes of sessions created through ``POST /api/sessions``.

    The code is read as soon as a creation response has fully arrived: the
    body is gone once the page navigates away (e.g. a reload right after
    joining). Requests still pending when the context is closed are read
    then, after waiting for their response: a test may end right after a
    click that creates a session (the body cannot be read once the context
    is closed).
    """
    if not EXTERNAL_BASE_URL:
        return new_context

    def _new_context(**kwargs):
        ctx = new_context(**kwargs)
        creations = []

        def is_creation(request):
            return request.method == "POST" and urlparse(request.url).path == "/api/sessions"

        def track_creation(request):
            if is_creation(request):
                creations.append(request)

        def record_finished_creation(request):
            if is_creation(request) and request in creations:
                creations.remove(request)
                record(request)

        def record(request):
            try:
                response = request.response()  # waits for it
                if response is None:
                    # The server may still have created the session.
                    created_sessions.unrecorded.append(f"request failed: {request.failure}")
                elif response.ok:
                    created_sessions.append(response.json()["session_code"])
            except Exception as exc:
                created_sessions.unrecorded.append(repr(exc))

        ctx.on("request", track_creation)
        ctx.on("requestfinished", record_finished_creation)
        close = ctx.close

        def close_after_recording_sessions(*args, **kwargs):
            # CompetitionHelper.cleanup swallows close errors, so anything that
            # keeps a code from being read is reported in created_sessions'
            # teardown instead; the context is closed in any case.
            try:
                while creations:
                    record(creations.pop(0))
            finally:
                close(*args, **kwargs)

        ctx.close = close_after_recording_sessions
        return ctx

    return _new_context


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

    def __init__(self, browser, url, new_context_factory):
        self.browser = browser
        self.url = url
        self._new_context_factory = new_context_factory
        self.contexts = []
        self.pages = {}
        self.session_code = None

    def new_context(self, **kwargs):
        """Open a browser context that pytest-playwright records.

        Contexts from pytest-playwright's ``new_context`` fixture get the
        ``--tracing`` / ``--screenshot`` artifacts on failure (CI uploads
        them); contexts from ``browser.new_context`` do not. The ``en-US``
        locale comes from ``browser_context_args``.
        """
        ctx = self._new_context_factory(**kwargs)
        self.contexts.append(ctx)
        return ctx

    def cleanup(self):
        for ctx in self.contexts:
            try:
                ctx.close()
            except Exception:
                pass

    def create_session_and_join_head(self, name="Test Session"):
        """Create a session and join as head judge (center). Returns page."""
        ctx = self.new_context()
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(self.url)

        page.get_by_test_id("session-name-input").fill(name)
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
        ctx = self.new_context()
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(self.url)

        page.get_by_test_id("join-code-input").fill(self.session_code)
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
        # "Vote Locked" only appears once the server acknowledged the vote.
        page.locator(".locked-status").wait_for(state="visible")
        assert not page.locator(".vote-sending-status").is_visible()

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
def competition(browser, server_url, new_context):
    helper = CompetitionHelper(browser, server_url, new_context)
    yield helper
    helper.cleanup()


# ---------------------------------------------------------------------------
# 5. Fake VPortal server fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fake_vportal_url():
    if EXTERNAL_BASE_URL:
        pytest.skip("fake VPortal needs the in-process server (TEST_MODE); runs in the e2e job")
    from tests.e2e.fake_vportal import app as fake_app
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(app=fake_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{port}/auth/token", timeout=1.0)
            break
        except Exception:
            time.sleep(0.1)
    yield f"127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
