"""Ship log lines to Grafana Cloud Loki (#134).

stdout stays the complete log (read in Railway); Loki gets a copy for search
and the weekly review. Only production sets the ``LOKI_*`` variables.

Nothing on the request or WebSocket path waits for the network: the handler
formats the line and puts it into a bounded queue without blocking. A daemon
thread sends the queue in batches. A full queue or a failed push drops the
lines for Loki only and counts them in ``iron_verdict_log_ship_dropped_total``.
"""

import logging
import queue
import threading
import time
from urllib.parse import urlparse

import httpx

from iron_verdict import metrics
from iron_verdict.logging_config import JsonFormatter

logger = logging.getLogger("iron_verdict.log_shipping")

# Why a 5 s batch interval (a deliberate delay): one push every 5 s instead of
# one per line keeps the request count and Grafana's free-tier ingest small.
# It delays only the copy in Loki; stdout and the app are not delayed.
SEND_INTERVAL_SECONDS = 5
# Upper bound for lines waiting to be sent; a 5 s burst or a Grafana outage
# beyond it drops lines for Loki (counted), never blocks logging.
QUEUE_SIZE = 10_000
# Lines per push request, so one request stays well below Loki's size limit.
MAX_BATCH_LINES = 1_000
# A slow Grafana must not hold the sender for long; the batch is dropped.
REQUEST_TIMEOUT_SECONDS = 5
# How long shutdown waits for the rest of the queue. Runs after the shutdown
# snapshot, so it never delays it; the thread is a daemon and cannot block exit.
SHUTDOWN_FLUSH_SECONDS = 2

# IP addresses stay in the Railway logs only (privacy policy, 7 days).
_EXCLUDED_FIELDS = ("client_ip",)


def _default_transport():
    """Transport for the HTTP client; None is httpx's default. Tests replace it."""
    return None


class LokiHandler(logging.Handler):
    """Formats a record and queues it without blocking."""

    def __init__(self, queue_size: int):
        super().__init__()
        self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self.setFormatter(JsonFormatter(exclude=_EXCLUDED_FIELDS))

    def emit(self, record: logging.LogRecord) -> None:
        # The shipper's own failures go to stdout only: queuing them while Loki
        # is down would only add to what cannot be sent.
        if record.name == logger.name:
            return
        try:
            item = (str(int(record.created * 1_000_000_000)), record.levelname.lower(), self.format(record))
            self.queue.put_nowait(item)
        except queue.Full:
            metrics.log_ship_dropped.labels(reason="queue_full").inc()
        except Exception:
            self.handleError(record)


class LokiShipper:
    def __init__(
        self,
        url: str,
        user: str,
        token: str,
        version: str,
        *,
        interval: float = SEND_INTERVAL_SECONDS,
        queue_size: int = QUEUE_SIZE,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        flush_timeout: float = SHUTDOWN_FLUSH_SECONDS,
        transport=None,
    ):
        self.handler = LokiHandler(queue_size)
        self._url = url
        self._labels = {"app": "iron-verdict", "version": version}
        self._interval = interval
        self._timeout = timeout
        self._flush_timeout = flush_timeout
        self._client = httpx.Client(
            auth=(user, token),
            timeout=timeout,
            transport=transport if transport is not None else _default_transport(),
        )
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="loki-shipper", daemon=True)
        self._logger: logging.Logger | None = None
        self._failing = False

    def start(self, target: logging.Logger) -> None:
        self._logger = target
        target.addHandler(self.handler)
        self._thread.start()

    def stop(self) -> None:
        """Stop queuing, send the rest within SHUTDOWN_FLUSH_SECONDS, return."""
        if self._logger is not None:
            self._logger.removeHandler(self.handler)
        self._stop.set()
        self._thread.join(self._flush_timeout)
        if not self._thread.is_alive():
            self._client.close()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self.send_pending()
        self.send_pending(deadline=time.monotonic() + self._flush_timeout)

    def send_pending(self, deadline: float | None = None) -> None:
        """Push everything queued, MAX_BATCH_LINES per request.

        With *deadline* (shutdown), stop when it has passed; lines left behind
        are still on stdout.
        """
        while True:
            timeout = self._timeout
            if deadline is not None:
                timeout = min(timeout, deadline - time.monotonic())
                if timeout <= 0:
                    return
            batch = []
            while len(batch) < MAX_BATCH_LINES:
                try:
                    batch.append(self.handler.queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            self._push(batch, timeout)

    def _push(self, batch: list[tuple[str, str, str]], timeout: float) -> None:
        streams: dict[str, list[list[str]]] = {}
        for ts, level, line in batch:
            streams.setdefault(level, []).append([ts, line])
        payload = {
            "streams": [
                {"stream": {**self._labels, "level": level}, "values": values}
                for level, values in streams.items()
            ]
        }
        status = None
        error = None
        try:
            response = self._client.post(self._url, json=payload, timeout=timeout)
            status = response.status_code
            if not response.is_success:
                error = f"HTTP {status}"
        except Exception as exc:  # network error, timeout, anything: never crash the thread
            error = str(exc) or type(exc).__name__
        if error is None:
            if self._failing:
                self._failing = False
                logger.info("log_ship_recovered")
            return
        metrics.log_ship_dropped.labels(reason="send_failed").inc(len(batch))
        if not self._failing:
            self._failing = True
            logger.warning("log_ship_failed", extra={"error": error, "upstream_status": status})


def start_log_shipping(url: str, user: str, token: str, version: str, target: logging.Logger):
    """Start shipping *target*'s lines to Loki if all three variables are set.

    Returns the shipper (call ``stop()`` on shutdown) or None.
    """
    if not (url or user or token):
        target.info("log_shipping_disabled", extra={"reason": "not_configured"})
        return None
    if not (url and user and token):
        target.warning("log_shipping_disabled", extra={"reason": "incomplete_config"})
        return None
    shipper = LokiShipper(url, user, token, version)
    shipper.start(target)
    target.info("log_shipping_enabled", extra={"host": urlparse(url).hostname})
    return shipper
