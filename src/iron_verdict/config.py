import logging
import os

from dotenv import load_dotenv

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


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "*")
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SNAPSHOT_PATH: str = os.getenv("SNAPSHOT_PATH", "/data/sessions.json")
    VPORTAL_FETCH_INTERVAL_MS: int = _read_fetch_interval()
    TEST_MODE: bool = os.getenv("TEST_MODE") == "1"
    EXPOSE_VPORTAL_STAGING: bool = os.getenv("EXPOSE_VPORTAL_STAGING") == "1"


settings = Settings()
