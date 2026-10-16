import logging
import os

from dotenv import load_dotenv
from limits import parse_many

load_dotenv()

logger = logging.getLogger("iron_verdict")

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
    # Empty means "not set"; startup refuses it (see require_allowed_origin).
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "").strip()
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SNAPSHOT_PATH: str = os.getenv("SNAPSHOT_PATH", "/data/sessions.json")
    VPORTAL_FETCH_INTERVAL_MS: int = _read_fetch_interval()
    RATE_LIMIT_SESSION_CREATE: str = _read_rate_limit("RATE_LIMIT_SESSION_CREATE", "10/hour")
    RATE_LIMIT_SESSION_LOOKUP: str = _read_rate_limit("RATE_LIMIT_SESSION_LOOKUP", "30/minute")
    TEST_MODE: bool = os.getenv("TEST_MODE") == "1"
    EXPOSE_VPORTAL_STAGING: bool = os.getenv("EXPOSE_VPORTAL_STAGING") == "1"


settings = Settings()
