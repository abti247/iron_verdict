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
