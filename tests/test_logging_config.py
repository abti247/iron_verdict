import json
import logging
from iron_verdict.logging_config import JsonFormatter


def test_json_formatter_produces_valid_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.INFO, pathname="", lineno=0,
        msg="test message", args=(), exc_info=None
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "test message"
    assert "timestamp" in parsed


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.INFO, pathname="", lineno=0,
        msg="session created", args=(), exc_info=None
    )
    record.session_code = "ABC12345"
    record.client_ip = "1.2.3.4"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["session_code"] == "ABC12345"
    assert parsed["client_ip"] == "1.2.3.4"
