import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest


def reload_config():
    import iron_verdict.config as cfg
    importlib.reload(cfg)
    return cfg.settings


def test_vportal_fetch_interval_defaults_to_3000(monkeypatch):
    monkeypatch.delenv("VPORTAL_FETCH_INTERVAL_MS", raising=False)
    settings = reload_config()
    assert settings.VPORTAL_FETCH_INTERVAL_MS == 3000


def test_vportal_fetch_interval_honors_env(monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "5000")
    settings = reload_config()
    assert settings.VPORTAL_FETCH_INTERVAL_MS == 5000


def test_vportal_fetch_interval_clamps_to_2000_minimum(monkeypatch):
    monkeypatch.setenv("VPORTAL_FETCH_INTERVAL_MS", "500")
    settings = reload_config()
    assert settings.VPORTAL_FETCH_INTERVAL_MS == 2000


def test_max_websockets_defaults_to_2000(monkeypatch):
    monkeypatch.delenv("MAX_WEBSOCKETS", raising=False)
    settings = reload_config()
    assert settings.MAX_WEBSOCKETS == 2000


def test_max_websockets_honors_env(monkeypatch):
    monkeypatch.setenv("MAX_WEBSOCKETS", "3")
    settings = reload_config()
    assert settings.MAX_WEBSOCKETS == 3


def test_test_mode_defaults_to_false(monkeypatch):
    monkeypatch.delenv("TEST_MODE", raising=False)
    settings = reload_config()
    assert settings.TEST_MODE is False


def test_test_mode_true_when_env_set_to_1(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    settings = reload_config()
    assert settings.TEST_MODE is True


def test_expose_vportal_staging_defaults_to_false(monkeypatch):
    monkeypatch.delenv("EXPOSE_VPORTAL_STAGING", raising=False)
    settings = reload_config()
    assert settings.EXPOSE_VPORTAL_STAGING is False


def test_expose_vportal_staging_true_when_env_set_to_1(monkeypatch):
    monkeypatch.setenv("EXPOSE_VPORTAL_STAGING", "1")
    settings = reload_config()
    assert settings.EXPOSE_VPORTAL_STAGING is True


def test_allowed_origin_missing_resolves_to_empty(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGIN", raising=False)
    # A developer's .env (copied from .env.example) would set it again.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    settings = reload_config()
    assert settings.ALLOWED_ORIGIN == ""


def test_allowed_origin_blank_resolves_to_empty(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "  ")
    settings = reload_config()
    assert settings.ALLOWED_ORIGIN == ""


def test_allowed_origin_explicit_wildcard_is_kept(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "*")
    settings = reload_config()
    assert settings.ALLOWED_ORIGIN == "*"


def test_require_allowed_origin_rejects_missing_value_with_error_log(caplog):
    from iron_verdict.config import require_allowed_origin
    with caplog.at_level(logging.ERROR, logger="iron_verdict"):
        with pytest.raises(RuntimeError, match="ALLOWED_ORIGIN is not set"):
            require_allowed_origin("")
    assert [r.getMessage() for r in caplog.records] == ["allowed_origin_missing"]
    assert caplog.records[0].levelno == logging.ERROR


def test_require_allowed_origin_accepts_explicit_wildcard_and_logs_it(caplog):
    from iron_verdict.config import require_allowed_origin
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        require_allowed_origin("*")
    record = next(r for r in caplog.records if r.getMessage() == "allowed_origin_configured")
    assert record.allowed_origin == "*"


def test_require_allowed_origin_accepts_domain_and_logs_it(caplog):
    from iron_verdict.config import require_allowed_origin
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        require_allowed_origin("https://iron-verdict.com")
    record = next(r for r in caplog.records if r.getMessage() == "allowed_origin_configured")
    assert record.allowed_origin == "https://iron-verdict.com"


def test_run_py_exits_nonzero_without_allowed_origin(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    # Empty counts as missing; setting it also keeps a developer's .env out.
    env = {**os.environ, "ALLOWED_ORIGIN": "", "PORT": "0", "HOST": "127.0.0.1",
           "SNAPSHOT_PATH": str(tmp_path / "sessions.json")}
    env.pop("ENV", None)
    result = subprocess.run(
        [sys.executable, str(repo_root / "run.py")],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "allowed_origin_missing" in result.stdout


def test_rate_limits_default_to_10_per_hour_and_30_per_minute(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_SESSION_CREATE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_SESSION_LOOKUP", raising=False)
    monkeypatch.delenv("RATE_LIMIT_METRICS", raising=False)
    settings = reload_config()
    assert settings.RATE_LIMIT_SESSION_CREATE == "10/hour"
    assert settings.RATE_LIMIT_SESSION_LOOKUP == "30/minute"
    assert settings.RATE_LIMIT_METRICS == "30/minute"


@pytest.mark.parametrize("name", ["RATE_LIMIT_SESSION_CREATE", "RATE_LIMIT_SESSION_LOOKUP", "RATE_LIMIT_METRICS"])
def test_invalid_rate_limit_refuses_to_start(monkeypatch, name):
    monkeypatch.setenv(name, "lots")
    with pytest.raises(RuntimeError, match=name):
        reload_config()
    monkeypatch.delenv(name)
    reload_config()


def _run_app(env_overrides, script):
    repo_root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "ALLOWED_ORIGIN": "*", **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env, capture_output=True, text=True, timeout=60,
        cwd=repo_root,
    )


def test_session_create_and_lookup_use_configured_rate_limits():
    script = """
from fastapi.testclient import TestClient
from iron_verdict.main import app
client = TestClient(app)
create = [client.post("/api/sessions", json={"name": "S"}).status_code for _ in range(3)]
lookup = [client.get("/api/sessions/ABCDEFGH").status_code for _ in range(3)]
print(create, lookup)
"""
    result = _run_app(
        {"RATE_LIMIT_SESSION_CREATE": "2/hour", "RATE_LIMIT_SESSION_LOOKUP": "2/minute",
         "PYTHONPATH": "src"},
        script,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[200, 200, 429] [404, 404, 429]"


def test_metrics_token_defaults_to_empty_and_is_stripped(monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    assert reload_config().METRICS_TOKEN == ""
    monkeypatch.setenv("METRICS_TOKEN", "  abc  ")
    assert reload_config().METRICS_TOKEN == "abc"
    monkeypatch.delenv("METRICS_TOKEN")
    reload_config()
