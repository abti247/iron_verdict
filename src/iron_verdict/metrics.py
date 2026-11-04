"""Prometheus metrics served at GET /metrics (#133).

Only totals: no session codes, names, IPs or paths as label values — for
privacy, and because every label value is its own time series.

Why a registry of its own: the global default registry would collect metrics
of every imported library and reject a second registration if a test reloads
a module.
"""

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
)
from prometheus_client.core import GaugeMetricFamily

registry = CollectorRegistry()
ProcessCollector(registry=registry)

# Why a socket was lost. A session ended by the head judge is not a disconnect.
DISCONNECT_REASONS = (
    "client",  # closed by the device or the network; the handler saw the close
    "heartbeat_stale",  # no pong for PONG_STALE_SECONDS (half-open connection)
    "heartbeat_send_failed",  # the ping could not be sent
    "flood",  # more than 20 messages per second
    "replaced",  # a judge reconnected with its token while the old socket was still registered
    "error",  # the handler raised an unhandled exception
)

# Outcome of a VPortal proxy request (#181), one value per way the handler ends
# after it called VPortal. Login reasons match `vportal_login_failed` in the logs.
VPORTAL_LOGIN_RESULTS = (
    "ok",
    "rejected",  # /auth/token refused the cookie: usually wrong credentials (answered 401)
    "unreachable",
    "no_session_cookie",
    "token_exchange_failed",
    "missing_access_token",
)
VPORTAL_GRAPHQL_RESULTS = (
    "ok",  # JSON passed through to the device, whatever the upstream status
    "token_rejected",
    "upstream_error",
    "unreachable",  # also after the retry
    "invalid_response",
)

build_info = Gauge("iron_verdict_build_info", "Running app version", ["version"], registry=registry)
votes = Counter("iron_verdict_votes", "Votes locked in (idempotent resends not counted)", registry=registry)
votes_rejected = Counter(
    "iron_verdict_votes_rejected", "Votes answered with vote_rejected", ["code"], registry=registry
)
ws_disconnects = Counter(
    "iron_verdict_ws_disconnects", "WebSockets lost, by reason (flood also before a join)", ["reason"], registry=registry
)
snapshot_last_ok = Gauge(
    "iron_verdict_snapshot_last_ok_timestamp_seconds",
    "Unix time of the last snapshot check that left the file up to date (written or unchanged)",
    registry=registry,
)
snapshot_failures = Counter("iron_verdict_snapshot_failures", "Failed periodic snapshot writes", registry=registry)
unhandled_exceptions = Counter(
    "iron_verdict_unhandled_exceptions", "Exceptions no handler caught (HTTP and WebSocket)", registry=registry
)
http_requests = Counter(
    "iron_verdict_http_requests", "HTTP responses by status class", ["status_class"], registry=registry
)
vportal_logins = Counter(
    "iron_verdict_vportal_logins", "VPortal proxy logins by result", ["result"], registry=registry
)
vportal_graphql_requests = Counter(
    "iron_verdict_vportal_graphql_requests", "VPortal proxy GraphQL requests by result", ["result"], registry=registry
)
vportal_transport_retries = Counter(
    "iron_verdict_vportal_transport_retries",
    "GraphQL calls retried after a transport error (stale pooled connection)",
    registry=registry,
)
log_ship_dropped = Counter(
    "iron_verdict_log_ship_dropped",
    "Log lines not delivered to Loki (queue full or push failed); stdout still has them",
    ["reason"],
    registry=registry,
)
# Why these buckets: few series (8 per endpoint); the upstream timeout is 5 s,
# so slower requests land in +Inf only as failures.
vportal_upstream_duration = Histogram(
    "iron_verdict_vportal_upstream_duration_seconds",
    "Time a VPortal proxy request spent on upstream calls (login: both calls; GraphQL: including the retry)",
    ["endpoint"],
    buckets=(0.25, 0.5, 1, 2, 5),
    registry=registry,
)

# Fixed label values show up as 0 from the start, so rate() and alerts see them
# before the first increment.
for _code in ("invalid", "lift_changed", "reason_required"):
    votes_rejected.labels(code=_code)
for _reason in DISCONNECT_REASONS:
    ws_disconnects.labels(reason=_reason)
for _cls in ("2xx", "3xx", "4xx", "5xx"):
    http_requests.labels(status_class=_cls)
for _result in VPORTAL_LOGIN_RESULTS:
    vportal_logins.labels(result=_result)
for _result in VPORTAL_GRAPHQL_RESULTS:
    vportal_graphql_requests.labels(result=_result)
for _reason in ("queue_full", "send_failed"):
    log_ship_dropped.labels(reason=_reason)
for _endpoint in ("login", "graphql"):
    vportal_upstream_duration.labels(endpoint=_endpoint)


def status_class(status: int) -> str:
    return f"{status // 100}xx"


class LiveStateCollector:
    """Counts sessions, judges and displays on each scrape.

    Why counted on scrape instead of incremented at every join and leave: a
    forgotten code path cannot make the number wrong (same reasoning as the
    snapshot comparing content instead of a dirty flag).
    """

    def __init__(self, session_manager, connection_manager):
        self._sessions = session_manager
        self._connections = connection_manager

    def collect(self):
        kinds = {"generic": 0, "vportal": 0}
        for session in list(self._sessions.sessions.values()):
            kind = session.get("kind", "generic")
            kinds[kind] = kinds.get(kind, 0) + 1
        sessions = GaugeMetricFamily("iron_verdict_sessions_active", "Sessions in memory", labels=["kind"])
        for kind, count in kinds.items():
            sessions.add_metric([kind], count)
        yield sessions

        roles = [role for roles in list(self._connections.active_connections.values()) for role in list(roles)]
        yield GaugeMetricFamily(
            "iron_verdict_judges_connected",
            "Judge WebSockets registered",
            value=sum(1 for r in roles if r.endswith("_judge")),
        )
        yield GaugeMetricFamily(
            "iron_verdict_displays_connected",
            "Display WebSockets registered",
            value=sum(1 for r in roles if r.startswith("display_")),
        )


def register_live_state(session_manager, connection_manager, version: str) -> None:
    registry.register(LiveStateCollector(session_manager, connection_manager))
    build_info.labels(version=version).set(1)
