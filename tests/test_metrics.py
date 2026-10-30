import asyncio
import logging
import time
from unittest.mock import AsyncMock

import httpx
import httpx_ws
import pytest
from fastapi.testclient import TestClient
from httpx_ws.transport import ASGIWebSocketTransport
from prometheus_client.parser import text_string_to_metric_families

from iron_verdict import metrics
from iron_verdict.config import settings
from iron_verdict.main import app, connection_manager, limiter, session_manager

TOKEN = "test-metrics-token"
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    limiter.reset()
    monkeypatch.setattr(settings, "METRICS_TOKEN", TOKEN)
    yield
    session_manager.sessions.clear()
    connection_manager.active_connections.clear()


def _value(name, **labels):
    return metrics.registry.get_sample_value(name, labels) or 0.0


def _scrape():
    """Parse /metrics into {(name, frozenset(labels)): value}."""
    r = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    return {
        (s.name, frozenset(s.labels.items())): s.value
        for family in text_string_to_metric_families(r.text)
        for s in family.samples
    }


def _ws_client():
    return httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")


async def _join(ws, code, role, token=None):
    msg = {"type": "join", "session_code": code, "role": role}
    if token:
        msg["reconnect_token"] = token
    await ws.send_json(msg)
    return await asyncio.wait_for(ws.receive_json(), timeout=1.0)


# ---- Endpoint and token ----

def test_metrics_with_valid_token_returns_prometheus_text():
    r = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "iron_verdict_sessions_active" in r.text


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer wrong"},
    {"Authorization": TOKEN},
    {"Authorization": f"Basic {TOKEN}"},
])
def test_metrics_without_or_with_wrong_token_returns_401_challenge(headers):
    """Grafana's Metrics Endpoint first asks without credentials and sends the
    token only after a 401 with WWW-Authenticate (#185); a 404 made it give up."""
    r = client.get("/metrics", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert "iron_verdict" not in r.text


def test_metrics_disabled_without_token_setting(monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    assert client.get("/metrics").status_code == 404
    assert client.get("/metrics", headers={"Authorization": "Bearer "}).status_code == 404


def test_metrics_rate_limited(monkeypatch):
    for _ in range(30):
        assert client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    assert client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 429


def test_startup_logs_metrics_disabled_without_token(monkeypatch, caplog, tmp_path):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    monkeypatch.setattr(settings, "SNAPSHOT_PATH", str(tmp_path / "sessions.json"))
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        with TestClient(app):
            pass
    assert "metrics_disabled" in [r.getMessage() for r in caplog.records]


def test_startup_logs_metrics_enabled_with_token(monkeypatch, caplog, tmp_path):
    monkeypatch.setattr(settings, "SNAPSHOT_PATH", str(tmp_path / "sessions.json"))
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        with TestClient(app):
            pass
    messages = [r.getMessage() for r in caplog.records]
    assert "metrics_enabled" in messages
    assert TOKEN not in caplog.text


def test_metrics_include_build_info_and_process_metrics():
    samples = _scrape()
    assert samples[("iron_verdict_build_info", frozenset({("version", settings.APP_VERSION)}))] == 1
    assert any(name == "process_resident_memory_bytes" for name, _ in samples)


# ---- Live gauges (counted on scrape) ----

async def test_sessions_active_counted_per_kind():
    await session_manager.create_session("A")
    await session_manager.create_session("B")
    await session_manager.create_session("C", kind="vportal")
    samples = _scrape()
    assert samples[("iron_verdict_sessions_active", frozenset({("kind", "generic")}))] == 2
    assert samples[("iron_verdict_sessions_active", frozenset({("kind", "vportal")}))] == 1


async def test_connected_gauges_follow_join_and_leave():
    code = await session_manager.create_session("A")
    async with _ws_client() as c1, _ws_client() as c2, _ws_client() as c3:
        async with httpx_ws.aconnect_ws("ws://test/ws", c1) as left, \
                   httpx_ws.aconnect_ws("ws://test/ws", c2) as center, \
                   httpx_ws.aconnect_ws("ws://test/ws", c3) as display:
            await _join(left, code, "left_judge")
            await _join(center, code, "center_judge")
            await _join(display, code, "display")
            samples = _scrape()
            assert samples[("iron_verdict_judges_connected", frozenset())] == 2
            assert samples[("iron_verdict_displays_connected", frozenset())] == 1
    for _ in range(50):
        if not connection_manager.active_connections:
            break
        await asyncio.sleep(0.01)
    samples = _scrape()
    assert samples[("iron_verdict_judges_connected", frozenset())] == 0
    assert samples[("iron_verdict_displays_connected", frozenset())] == 0


async def test_labels_contain_no_session_codes_or_names():
    code = await session_manager.create_session("Secret Meet Name")
    r = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert code not in r.text
    assert "Secret Meet Name" not in r.text


# ---- Votes ----

async def test_votes_total_counts_accepted_votes_once():
    code = await session_manager.create_session("A")
    before = _value("iron_verdict_votes_total")
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, code, "left_judge")
            await ws.send_json({"type": "vote_lock", "color": "white", "lift_id": 0})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["type"] == "vote_ack"
            # An idempotent resend is acked but not a second vote.
            await ws.send_json({"type": "vote_lock", "color": "white", "lift_id": 0})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["type"] == "vote_ack"
    assert _value("iron_verdict_votes_total") == before + 1


async def test_votes_rejected_total_counts_per_code():
    code = await session_manager.create_session("A")
    before_invalid = _value("iron_verdict_votes_rejected_total", code="invalid")
    before_lift = _value("iron_verdict_votes_rejected_total", code="lift_changed")
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, code, "left_judge")
            await ws.send_json({"type": "vote_lock", "color": "purple"})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["code"] == "invalid"
            await ws.send_json({"type": "vote_lock", "color": "white", "lift_id": 99})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["code"] == "lift_changed"
    assert _value("iron_verdict_votes_rejected_total", code="invalid") == before_invalid + 1
    assert _value("iron_verdict_votes_rejected_total", code="lift_changed") == before_lift + 1


# ---- Disconnects ----

async def _wait_until_released(code):
    for _ in range(100):
        if code not in connection_manager.active_connections:
            return
        await asyncio.sleep(0.01)


async def test_client_disconnect_counted():
    code = await session_manager.create_session("A")
    before = _value("iron_verdict_ws_disconnects_total", reason="client")
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, code, "left_judge")
    await _wait_until_released(code)
    assert _value("iron_verdict_ws_disconnects_total", reason="client") == before + 1


async def test_flood_disconnect_counted_as_flood_not_client():
    code = await session_manager.create_session("A")
    before_flood = _value("iron_verdict_ws_disconnects_total", reason="flood")
    before_client = _value("iron_verdict_ws_disconnects_total", reason="client")
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, code, "left_judge")
            for _ in range(25):
                try:
                    await ws.send_json({"type": "pong"})
                except Exception:
                    break
    await _wait_until_released(code)
    assert _value("iron_verdict_ws_disconnects_total", reason="flood") == before_flood + 1
    assert _value("iron_verdict_ws_disconnects_total", reason="client") == before_client


async def test_reconnect_with_token_counts_replaced_once(caplog):
    code = await session_manager.create_session("A")
    before_replaced = _value("iron_verdict_ws_disconnects_total", reason="replaced")
    before_client = _value("iron_verdict_ws_disconnects_total", reason="client")
    with caplog.at_level(logging.INFO, logger="iron_verdict"):
        async with _ws_client() as c1, _ws_client() as c2:
            async with httpx_ws.aconnect_ws("ws://test/ws", c1) as old_ws:
                token = (await _join(old_ws, code, "left_judge"))["reconnect_token"]
                async with httpx_ws.aconnect_ws("ws://test/ws", c2) as new_ws:
                    assert (await _join(new_ws, code, "left_judge", token))["type"] == "join_success"
                    assert _value("iron_verdict_ws_disconnects_total", reason="replaced") == before_replaced + 1
        # Wait until the replaced socket's handler has ended (it logs this on its way out).
        for _ in range(100):
            if "stale_disconnect_ignored" in [r.getMessage() for r in caplog.records]:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("replaced socket's handler did not end")
    await _wait_until_released(code)
    # Only the new socket's close counts as client; the replaced one is not counted again.
    assert _value("iron_verdict_ws_disconnects_total", reason="client") == before_client + 1
    assert _value("iron_verdict_ws_disconnects_total", reason="replaced") == before_replaced + 1


async def test_heartbeat_disconnects_counted_by_reason():
    from iron_verdict.connection import ConnectionManager
    from iron_verdict.main import PONG_STALE_SECONDS, heartbeat_sweep

    manager = ConnectionManager()
    stale, dead = AsyncMock(), AsyncMock()
    dead.send_json.side_effect = RuntimeError("gone")
    await manager.add_connection("ABCD1234", "display_1", stale)
    await manager.add_connection("ABCD1234", "display_2", dead)
    now = time.monotonic()
    manager._last_pong[stale] = now - (PONG_STALE_SECONDS + 1)
    before_stale = _value("iron_verdict_ws_disconnects_total", reason="heartbeat_stale")
    before_dead = _value("iron_verdict_ws_disconnects_total", reason="heartbeat_send_failed")

    await heartbeat_sweep(manager, now)
    await heartbeat_sweep(manager, now)

    assert _value("iron_verdict_ws_disconnects_total", reason="heartbeat_stale") == before_stale + 1
    assert _value("iron_verdict_ws_disconnects_total", reason="heartbeat_send_failed") == before_dead + 1


async def test_session_end_is_not_counted_as_disconnect():
    code = await session_manager.create_session("A")
    before = {r: _value("iron_verdict_ws_disconnects_total", reason=r) for r in metrics.DISCONNECT_REASONS}
    async with _ws_client() as ac:
        async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
            await _join(ws, code, "center_judge")
            await ws.send_json({"type": "end_session_confirmed"})
            assert (await asyncio.wait_for(ws.receive_json(), timeout=1.0))["type"] == "session_ended"
    await _wait_until_released(code)
    after = {r: _value("iron_verdict_ws_disconnects_total", reason=r) for r in metrics.DISCONNECT_REASONS}
    assert after == before


# ---- Snapshot ----

async def test_snapshot_last_ok_set_even_without_change(tmp_path):
    from iron_verdict.main import cleanup_loop
    from iron_verdict.session import SessionManager

    manager = SessionManager()
    path = str(tmp_path / "s.json")
    manager.load_snapshot(path)  # nothing on disk: snapshot already up to date
    metrics.snapshot_last_ok.set(0)
    ticks = 0

    async def one_tick(_):
        nonlocal ticks
        ticks += 1
        if ticks > 1:
            raise asyncio.CancelledError

    start = time.time()
    with pytest.raises(asyncio.CancelledError):
        await cleanup_loop(manager, path, 4, sleep=one_tick)
    assert not (tmp_path / "s.json").exists()
    assert _value("iron_verdict_snapshot_last_ok_timestamp_seconds") >= start


async def test_snapshot_failure_counted_and_last_ok_unchanged(tmp_path):
    from iron_verdict.main import cleanup_loop
    from iron_verdict.session import SessionManager

    manager = SessionManager()
    await manager.create_session("A")
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    path = str(blocker / "s.json")
    metrics.snapshot_last_ok.set(123)
    before = _value("iron_verdict_snapshot_failures_total")
    ticks = 0

    async def one_tick(_):
        nonlocal ticks
        ticks += 1
        if ticks > 1:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await cleanup_loop(manager, path, 4, sleep=one_tick)
    assert _value("iron_verdict_snapshot_failures_total") == before + 1
    assert _value("iron_verdict_snapshot_last_ok_timestamp_seconds") == 123


# ---- HTTP status classes and exceptions ----

def test_http_requests_counted_by_status_class():
    before_2xx = _value("iron_verdict_http_requests_total", status_class="2xx")
    before_4xx = _value("iron_verdict_http_requests_total", status_class="4xx")
    assert client.get("/health").status_code == 200
    assert client.get("/api/sessions/AAAAAAAA").status_code == 404
    assert client.get("/api/sessions/bad").status_code == 422
    assert _value("iron_verdict_http_requests_total", status_class="2xx") == before_2xx + 1
    assert _value("iron_verdict_http_requests_total", status_class="4xx") == before_4xx + 2


def test_unhandled_http_exception_counts_5xx_and_exception(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(session_manager, "create_session", boom)
    before_5xx = _value("iron_verdict_http_requests_total", status_class="5xx")
    before_exc = _value("iron_verdict_unhandled_exceptions_total")
    r = TestClient(app, raise_server_exceptions=False).post("/api/sessions", json={"name": "X"})
    assert r.status_code == 500
    assert _value("iron_verdict_http_requests_total", status_class="5xx") == before_5xx + 1
    assert _value("iron_verdict_unhandled_exceptions_total") == before_exc + 1


async def test_unhandled_websocket_exception_counted_as_exception_and_error_disconnect(monkeypatch):
    async def boom(code):
        raise RuntimeError("boom")
    monkeypatch.setattr(session_manager, "reset_for_next_lift", boom)
    code = await session_manager.create_session("A")
    before = _value("iron_verdict_unhandled_exceptions_total")
    before_error = _value("iron_verdict_ws_disconnects_total", reason="error")
    before_client = _value("iron_verdict_ws_disconnects_total", reason="client")
    with pytest.raises(Exception):
        async with _ws_client() as ac:
            async with httpx_ws.aconnect_ws("ws://test/ws", ac) as ws:
                await _join(ws, code, "center_judge")
                await ws.send_json({"type": "next_lift"})
                await asyncio.wait_for(ws.receive_json(), timeout=1.0)
    assert _value("iron_verdict_unhandled_exceptions_total") == before + 1
    assert _value("iron_verdict_ws_disconnects_total", reason="error") == before_error + 1
    assert _value("iron_verdict_ws_disconnects_total", reason="client") == before_client
