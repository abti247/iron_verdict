import json
import logging
import sys
from datetime import datetime, timezone

_EXTRA_FIELDS = (
    "session_code", "role", "client_ip", "color",
    "position", "all_locked", "reason", "origin", "conn_id",
    # VPortal integration — proxy diagnostics
    "kind", "host", "first_field", "upstream_status", "error",
    # VPortal login failures — statuses, headers and cookie *names* only
    "login_status", "login_location", "cookie_names",
    "token_status", "token_location", "content_type", "upstream_path",
    # VPortal integration — config-time diagnostics
    "raw", "requested", "clamped_to",
    # Startup configuration
    "allowed_origin",
    # Global WebSocket cap (#61)
    "limit",
    # Display pause (#163)
    "pause_mode", "pause_seconds", "ended_by",
    # Heartbeat, snapshot, vote rejection and startup rate limits (#134)
    "seconds_since_pong", "session_count", "code", "session_create", "session_lookup",
    # Lift traceability: votes, the result as sent, and the lift they belong to (#240)
    "lift_id", "votes", "reasons", "show_explanations", "lift_type",
    # Startup rate limits of the VPortal proxy (#236)
    "vportal_login", "vportal_graphql",
)

class JsonFormatter(logging.Formatter):
    """One JSON object per line with the whitelisted extra fields.

    *exclude* leaves out fields, e.g. ``client_ip`` for lines leaving the
    app (#134): IP addresses stay in the Railway logs only.
    """

    def __init__(self, exclude: tuple[str, ...] = ()):
        super().__init__()
        self._fields = tuple(f for f in _EXTRA_FIELDS if f not in exclude)

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in self._fields:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)
        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root 'iron_verdict' logger with JSON output to stdout."""
    logger = logging.getLogger("iron_verdict")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(handler)
