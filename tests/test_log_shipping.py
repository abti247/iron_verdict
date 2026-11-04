"""Log shipping to Grafana Cloud Loki (#134).

The handler only formats and queues; a background thread sends. These tests
check that nothing on the logging path waits for the network, that the IP
never leaves the app, and that every line lost for Loki is counted.
"""

import base64
import json
import logging
import socket
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from iron_verdict import log_shipping, metrics
from iron_verdict.config import settings
from iron_verdict.log_shipping import LokiShipper, start_log_shipping

URL = "https://logs.example.invalid/loki/api/v1/push"


def _dropped(reason):
    return metrics.registry.get_sample_value("iron_verdict_log_ship_dropped_total", {"reason": reason}) or 0.0


def _record(msg="vote_locked", level=logging.INFO, **extra):
    record = logging.LogRecord(
        name="iron_verdict", level=level, pathname="", lineno=0, msg=msg, args=(), exc_info=None,
    )
    record.__dict__.update(extra)
    return record


class _Recorder:
    """httpx transport that records pushes and answers with *status*."""

    def __init__(self, status=204):
        self.status = status
        self.requests = []
        self.sent = threading.Event()

    def __call__(self, request):
        self.requests.append(request)
        self.sent.set()
        return httpx.Response(self.status)

    def transport(self):
        return httpx.MockTransport(self)


@pytest.fixture
def blackhole():
    """A TCP address that accepts the connection and never answers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}/loki/api/v1/push"
    sock.close()


def _shipper(**kwargs):
    kwargs.setdefault("url", URL)
    kwargs.setdefault("user", "123456")
    kwargs.setdefault("token", "glc_secret")
    kwargs.setdefault("version", "v1.2.3")
    return LokiShipper(**kwargs)


def test_push_payload_has_labels_lines_and_basic_auth():
    rec = _Recorder()
    shipper = _shipper(transport=rec.transport())
    shipper.handler.handle(_record("vote_locked", session_code="ABC12345"))
    shipper.handler.handle(_record("broadcast_send_failed", level=logging.WARNING))
    shipper.send_pending()

    assert len(rec.requests) == 1
    request = rec.requests[0]
    assert str(request.url) == URL
    assert request.headers["authorization"] == "Basic " + base64.b64encode(b"123456:glc_secret").decode()
    streams = json.loads(request.content)["streams"]
    by_level = {s["stream"]["level"]: s for s in streams}
    assert by_level["info"]["stream"] == {"app": "iron-verdict", "level": "info", "version": "v1.2.3"}
    assert set(by_level) == {"info", "warning"}
    ts, line = by_level["info"]["values"][0]
    assert ts.isdigit() and len(ts) == 19  # nanoseconds since the epoch
    assert json.loads(line)["message"] == "vote_locked"
    assert json.loads(line)["session_code"] == "ABC12345"


def test_client_ip_is_removed_before_shipping():
    rec = _Recorder()
    shipper = _shipper(transport=rec.transport())
    shipper.handler.handle(_record("session_created", client_ip="203.0.113.7", session_code="ABC12345"))
    shipper.send_pending()
    body = rec.requests[0].content.decode()
    assert "203.0.113.7" not in body
    assert "client_ip" not in body
    assert "ABC12345" in body


def test_full_queue_drops_and_counts_without_blocking():
    shipper = _shipper(queue_size=2, transport=_Recorder().transport())
    before = _dropped("queue_full")
    start = time.monotonic()
    for _ in range(5):
        shipper.handler.handle(_record())
    assert time.monotonic() - start < 0.5
    assert _dropped("queue_full") - before == 3


def test_failed_push_drops_the_batch_and_counts_it():
    shipper = _shipper(transport=_Recorder(status=500).transport())
    before = _dropped("send_failed")
    for _ in range(3):
        shipper.handler.handle(_record())
    shipper.send_pending()
    assert _dropped("send_failed") - before == 3
    shipper.send_pending()  # nothing left to send, nothing more counted
    assert _dropped("send_failed") - before == 3


def test_failure_and_recovery_are_logged_once_and_not_shipped(caplog):
    rec = _Recorder(status=401)
    shipper = _shipper(transport=rec.transport())
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        for _ in range(2):
            shipper.handler.handle(_record())
            shipper.send_pending()
        rec.status = 204
        shipper.handler.handle(_record())
        shipper.send_pending()
        shipper.handler.handle(_record())
        shipper.send_pending()
    messages = [r.getMessage() for r in caplog.records if r.name == log_shipping.logger.name]
    assert messages == ["log_ship_failed", "log_ship_recovered"]
    failed = next(r for r in caplog.records if r.getMessage() == "log_ship_failed")
    assert failed.upstream_status == 401
    # Its own messages never go to Loki (no feedback loop while Loki is down).
    shipper.handler.handle(failed)
    assert shipper.handler.queue.qsize() == 0


def test_unreachable_loki_does_not_block_logging(blackhole):
    """While the sender thread hangs on an address that never answers, logging
    returns at once; the batch counts as failed after the timeout."""
    shipper = _shipper(url=blackhole, interval=0.05, timeout=0.3)
    logger = logging.getLogger("iron_verdict.test_shipping")
    before = _dropped("send_failed")
    shipper.start(logger)
    try:
        logger.setLevel(logging.INFO)
        logger.info("first")
        # The sender has taken "first" off the queue and now hangs on the blackhole.
        deadline = time.monotonic() + 3
        while shipper.handler.queue.qsize() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert shipper.handler.queue.qsize() == 0
        start = time.monotonic()
        for _ in range(200):
            logger.info("vote_locked")
        assert time.monotonic() - start < 0.2
        deadline = time.monotonic() + 3
        while _dropped("send_failed") == before and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _dropped("send_failed") > before
    finally:
        shipper.stop()
    assert shipper.handler not in logger.handlers


def test_stop_flushes_the_rest():
    rec = _Recorder()
    shipper = _shipper(interval=60, transport=rec.transport())
    logger = logging.getLogger("iron_verdict.test_flush")
    logger.setLevel(logging.INFO)
    shipper.start(logger)
    logger.info("server_shutdown_started")
    shipper.stop()
    assert "server_shutdown_started" in rec.requests[0].content.decode()


def test_stop_returns_within_the_flush_limit_when_loki_hangs(blackhole):
    shipper = _shipper(url=blackhole, interval=60, timeout=5, flush_timeout=0.3)
    logger = logging.getLogger("iron_verdict.test_flush_limit")
    logger.setLevel(logging.INFO)
    shipper.start(logger)
    logger.info("server_shutdown_started")
    start = time.monotonic()
    shipper.stop()
    assert time.monotonic() - start < 1


def test_without_configuration_no_handler_is_added(caplog):
    logger = logging.getLogger("iron_verdict.test_unconfigured")
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        assert start_log_shipping("", "", "", "dev", logger) is None
    assert not any(isinstance(h, log_shipping.LokiHandler) for h in logger.handlers)
    record = next(r for r in caplog.records if r.getMessage() == "log_shipping_disabled")
    assert record.reason == "not_configured"


def test_incomplete_configuration_is_a_warning_and_ships_nothing(caplog):
    logger = logging.getLogger("iron_verdict.test_incomplete")
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        assert start_log_shipping(URL, "123456", "", "dev", logger) is None
    record = next(r for r in caplog.records if r.getMessage() == "log_shipping_disabled")
    assert record.levelno == logging.WARNING
    assert record.reason == "incomplete_config"


def test_complete_configuration_starts_shipping(caplog):
    logger = logging.getLogger("iron_verdict.test_configured")
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        shipper = start_log_shipping(URL, "123456", "glc_secret", "dev", logger)
    try:
        assert shipper is not None
        assert shipper.handler in logger.handlers
        assert "log_shipping_enabled" in [r.getMessage() for r in caplog.records]
        assert "glc_secret" not in caplog.text
    finally:
        shipper.stop()


def test_app_startup_without_loki_variables_ships_nothing(monkeypatch, caplog, tmp_path):
    monkeypatch.setattr(settings, "LOKI_URL", "")
    monkeypatch.setattr(settings, "LOKI_USER", "")
    monkeypatch.setattr(settings, "LOKI_TOKEN", "")
    monkeypatch.setattr(settings, "SNAPSHOT_PATH", str(tmp_path / "sessions.json"))
    from iron_verdict.main import app

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        with TestClient(app):
            assert not any(
                isinstance(h, log_shipping.LokiHandler) for h in logging.getLogger("iron_verdict").handlers
            )
    assert "log_shipping_disabled" in [r.getMessage() for r in caplog.records]


def test_app_shutdown_saves_the_snapshot_and_flushes_the_rest(monkeypatch, caplog, tmp_path):
    rec = _Recorder()
    monkeypatch.setattr(settings, "LOKI_URL", URL)
    monkeypatch.setattr(settings, "LOKI_USER", "123456")
    monkeypatch.setattr(settings, "LOKI_TOKEN", "glc_secret")
    monkeypatch.setattr(settings, "SNAPSHOT_PATH", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(log_shipping, "_default_transport", rec.transport)
    from iron_verdict.main import app

    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        with TestClient(app):
            pass
    assert not any(isinstance(h, log_shipping.LokiHandler) for h in logging.getLogger("iron_verdict").handlers)
    assert (tmp_path / "sessions.json").exists()
    body = b"".join(r.content for r in rec.requests).decode()
    assert "log_shipping_enabled" in body
