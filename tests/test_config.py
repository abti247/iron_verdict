import importlib
import os

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
