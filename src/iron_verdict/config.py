import logging
import os

from dotenv import load_dotenv
from limits import parse_many

load_dotenv()

logger = logging.getLogger("iron_verdict")

# Longest session name in characters (#237). Why: the name sits in memory and
# the snapshot and goes out with every join_success; the rate limit caps the
# number of sessions, not their size.
SESSION_NAME_MAX_LENGTH = 100

# Largest incoming WebSocket message in bytes, passed to uvicorn by run.py
# (#237). uvicorn closes a connection that sends more with 1009 before the
# handler parses anything. Why: uvicorn's default of 16 MiB lets one client
# keep the single event loop busy with json.loads and delay votes of every
# competition; the largest legitimate client message is under 1 KB.
WS_MAX_SIZE = 64 * 1024

_FETCH_INTERVAL_MIN_MS = 2000
_FETCH_INTERVAL_DEFAULT_MS = 3000


def _read_fetch_interval() -> int:
    raw = os.getenv("VPORTAL_FETCH_INTERVAL_MS")
    if raw is None:
        return _FETCH_INTERVAL_DEFAULT_MS
    try:
        value = int(raw)
    except ValueError:
        logger.warning("vportal_fetch_interval_invalid", extra={"raw": raw})
        return _FETCH_INTERVAL_DEFAULT_MS
    if value < _FETCH_INTERVAL_MIN_MS:
        logger.warning(
            "vportal_fetch_interval_clamped",
            extra={"requested": value, "clamped_to": _FETCH_INTERVAL_MIN_MS},
        )
        return _FETCH_INTERVAL_MIN_MS
    return value


def _read_rate_limit(name: str, default: str) -> str:
    """Rate limit in slowapi notation (e.g. "10/hour") from env var *name*.

    Why configurable: staging runs the E2E suite against a deployed server,
    where the test run cannot reset the limiter and needs more than the
    production limits. An invalid value refuses startup instead of silently
    falling back, so a typo on a deployment is seen at once.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parse_many(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name}={raw!r} is not a valid rate limit (e.g. '10/hour')") from exc
    return raw


def require_allowed_origin(value: str) -> str:
    """Refuse to start without an explicit ALLOWED_ORIGIN.

    Why: a missing value used to fall back to "*", so a new deployment that
    forgot the variable silently accepted WebSockets from any site (CSWSH).
    An explicit "*" stays valid for local/LAN use.
    """
    if not value:
        logger.error("allowed_origin_missing")
        raise RuntimeError(
            "ALLOWED_ORIGIN is not set. Set it to the app's public origin "
            "(e.g. https://iron-verdict.com), or explicitly to '*' for local/LAN use."
        )
    logger.info("allowed_origin_configured", extra={"allowed_origin": value})
    return value


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
    # Upper bound for joined WebSockets across all sessions (#61).
    MAX_WEBSOCKETS: int = int(os.getenv("MAX_WEBSOCKETS", "2000"))
    # Empty means "not set"; startup refuses it (see require_allowed_origin).
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "").strip()
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SNAPSHOT_PATH: str = os.getenv("SNAPSHOT_PATH", "/data/sessions.json")
    VPORTAL_FETCH_INTERVAL_MS: int = _read_fetch_interval()
    RATE_LIMIT_SESSION_CREATE: str = _read_rate_limit("RATE_LIMIT_SESSION_CREATE", "10/hour")
    RATE_LIMIT_SESSION_LOOKUP: str = _read_rate_limit("RATE_LIMIT_SESSION_LOOKUP", "30/minute")
    RATE_LIMIT_METRICS: str = _read_rate_limit("RATE_LIMIT_METRICS", "30/minute")
    # VPortal proxy (#236). Login: guards VPortal accounts against password
    # guessing through us. GraphQL: one device polls twice per interval (about
    # 40/minute at 3 s, 60 at the 2 s minimum) and a venue's devices share one
    # IP, so 600 leaves room for ~15 devices. VPortal sees all our traffic from
    # one Railway IP; a block there would take down every display at once.
    RATE_LIMIT_VPORTAL_LOGIN: str = _read_rate_limit("RATE_LIMIT_VPORTAL_LOGIN", "10/minute")
    RATE_LIMIT_VPORTAL_GRAPHQL: str = _read_rate_limit("RATE_LIMIT_VPORTAL_GRAPHQL", "600/minute")
    # Bearer token Grafana sends to GET /metrics (#133). Empty means the endpoint is off.
    METRICS_TOKEN: str = os.getenv("METRICS_TOKEN", "").strip()
    # Grafana Cloud Loki push (#134): full push URL, user (numeric ID) and an
    # access-policy token with logs:write only. All three or nothing is shipped.
    LOKI_URL: str = os.getenv("LOKI_URL", "").strip()
    LOKI_USER: str = os.getenv("LOKI_USER", "").strip()
    LOKI_TOKEN: str = os.getenv("LOKI_TOKEN", "").strip()
    TEST_MODE: bool = os.getenv("TEST_MODE") == "1"
    EXPOSE_VPORTAL_STAGING: bool = os.getenv("EXPOSE_VPORTAL_STAGING") == "1"


settings = Settings()
