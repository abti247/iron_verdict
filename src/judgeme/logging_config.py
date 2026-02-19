import json
import logging
import sys
from datetime import datetime, timezone

_EXTRA_FIELDS = (
    "session_code", "role", "client_ip", "color",
    "position", "all_locked", "reason", "origin",
)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)
        return json.dumps(log_obj)


def setup_logging() -> None:
    """Configure root 'judgeme' logger with JSON output to stdout."""
    logger = logging.getLogger("judgeme")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
