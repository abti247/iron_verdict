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


def test_json_formatter_includes_conn_id():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.INFO, pathname="", lineno=0,
        msg="role_joined", args=(), exc_info=None
    )
    record.conn_id = "abc12345def67890"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["conn_id"] == "abc12345def67890"


def test_json_formatter_includes_vportal_fields():
    # Why: vportal_proxy.py logs structured diagnostics with these keys.
    # If the whitelist drops them, we lose context on every failure path.
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.WARNING, pathname="", lineno=0,
        msg="vportal_token_exchange_failed", args=(), exc_info=None,
    )
    record.upstream_status = 302
    record.host = "staging-bvdk.vportal-online.de"
    record.kind = "vportal"
    record.first_field = "secretAdminQuery"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["upstream_status"] == 302
    assert parsed["host"] == "staging-bvdk.vportal-online.de"
    assert parsed["kind"] == "vportal"
    assert parsed["first_field"] == "secretAdminQuery"


def test_json_formatter_includes_vportal_login_failure_fields():
    # Why: issue #100 — a failed VPortal login must leave enough context in the
    # server log to find the cause without staging access.
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.WARNING, pathname="", lineno=0,
        msg="vportal_login_failed", args=(), exc_info=None,
    )
    record.reason = "token_exchange_failed"
    record.login_status = 302
    record.login_location = "/dashboard"
    record.cookie_names = ["__Host-VPORTAL"]
    record.token_status = 500
    record.token_location = None
    record.content_type = "text/html"
    record.upstream_path = "/auth/token"
    record.error = "ConnectError"
    parsed = json.loads(formatter.format(record))
    assert parsed["reason"] == "token_exchange_failed"
    assert parsed["login_status"] == 302
    assert parsed["login_location"] == "/dashboard"
    assert parsed["cookie_names"] == ["__Host-VPORTAL"]
    assert parsed["token_status"] == 500
    assert parsed["token_location"] is None
    assert parsed["content_type"] == "text/html"
    assert parsed["upstream_path"] == "/auth/token"
    assert parsed["error"] == "ConnectError"


def test_json_formatter_includes_websocket_cap_limit():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.WARNING, pathname="", lineno=0,
        msg="websocket_cap_reached", args=(), exc_info=None
    )
    record.limit = 2000
    parsed = json.loads(formatter.format(record))
    assert parsed["limit"] == 2000


def test_json_formatter_includes_pause_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="iron_verdict", level=logging.INFO, pathname="", lineno=0,
        msg="pause_started", args=(), exc_info=None
    )
    record.pause_mode = "until"
    record.pause_seconds = 600
    record.ended_by = "timer_start"
    parsed = json.loads(formatter.format(record))
    assert parsed["pause_mode"] == "until"
    assert parsed["pause_seconds"] == 600
    assert parsed["ended_by"] == "timer_start"
