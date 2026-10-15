import asyncio
import json
import os
import tempfile
import time

import pytest
from iron_verdict.session import SessionManager
from datetime import datetime, timedelta


def test_generate_session_code_creates_8_char_code():
    manager = SessionManager()
    code = manager.generate_session_code()
    assert len(code) == 8
    assert code.isalnum()


def test_generate_session_code_creates_unique_codes():
    manager = SessionManager()
    code1 = manager.generate_session_code()
    code2 = manager.generate_session_code()
    assert code1 != code2


async def test_create_session_returns_code():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert len(code) == 8
    assert code in manager.sessions


async def test_create_session_initializes_structure():
    manager = SessionManager()
    code = await manager.create_session("Test")
    session = manager.sessions[code]

    assert "judges" in session
    assert "left" in session["judges"]
    assert "center" in session["judges"]
    assert "right" in session["judges"]
    assert session["state"] == "waiting"
    assert session["timer_state"] == "idle"
    assert "last_activity" in session


async def test_join_session_as_judge_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")

    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["connected"] is True


def test_join_session_invalid_code_fails():
    manager = SessionManager()
    result = manager.join_session("INVALID", "left_judge")
    assert result["success"] is False
    assert "Session not found" in result["error"]


async def test_join_session_role_already_taken_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")

    result = manager.join_session(code, "left_judge")
    assert result["success"] is False
    assert "already taken" in result["error"]


async def test_join_session_as_display_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")

    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert result["is_head"] is False


async def test_join_session_invalid_role_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")

    result = manager.join_session(code, "admin")
    assert result["success"] is False
    assert "Invalid role" in result["error"]


async def test_lock_vote_succeeds():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")

    result = await manager.lock_vote(code, "left", "white")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "white"
    assert manager.sessions[code]["judges"]["left"]["locked"] is True


async def test_lock_vote_invalid_session_fails():
    manager = SessionManager()
    result = await manager.lock_vote("INVALID", "left", "white")
    assert result["success"] is False


async def test_lock_vote_updates_last_activity():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")

    before = manager.sessions[code]["last_activity"]
    await manager.lock_vote(code, "left", "red")
    after = manager.sessions[code]["last_activity"]

    assert after > before


async def test_all_votes_locked_triggers_results():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "red")
    result = await manager.lock_vote(code, "right", "white")

    assert result["all_locked"] is True
    assert manager.sessions[code]["state"] == "showing_results"


async def test_reset_for_next_lift_clears_votes():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "white")

    await manager.reset_for_next_lift(code)

    session = manager.sessions[code]
    assert session["judges"]["left"]["current_vote"] is None
    assert session["judges"]["left"]["locked"] is False
    assert session["state"] == "waiting"


async def test_get_expired_sessions_returns_old_sessions():
    manager = SessionManager()
    code = await manager.create_session("Test")

    # Manually set old timestamp
    manager.sessions[code]["last_activity"] = datetime.now() - timedelta(hours=5)

    expired = manager.get_expired_sessions(hours=4)
    assert code in expired


async def test_delete_session_removes_from_memory():
    manager = SessionManager()
    code = await manager.create_session("Test")

    manager.delete_session(code)
    assert code not in manager.sessions


async def test_create_session_initializes_settings():
    manager = SessionManager()
    code = await manager.create_session("Test")
    session = manager.sessions[code]
    assert "settings" in session
    assert session["settings"]["show_explanations"] is True
    assert session["settings"]["lift_type"] == "squat"


async def test_update_settings_stores_values():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, False, "bench")
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["show_explanations"] is False
    assert manager.sessions[code]["settings"]["lift_type"] == "bench"


def test_update_settings_invalid_session_fails():
    manager = SessionManager()
    result = manager.update_settings("INVALID", True, "squat")
    assert result["success"] is False
    assert "Session not found" in result["error"]


async def test_update_settings_invalid_lift_type_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, False, "snatch")
    assert result["success"] is False
    assert "Invalid lift type" in result["error"]


async def test_create_session_stores_name():
    manager = SessionManager()
    code = await manager.create_session("Platform A")
    assert manager.sessions[code]["name"] == "Platform A"


async def test_cleanup_expired_removes_stale_keeps_fresh():
    manager = SessionManager()
    old_code = await manager.create_session("Old")
    new_code = await manager.create_session("New")
    manager.sessions[old_code]["last_activity"] = datetime.now() - timedelta(hours=5)

    manager.cleanup_expired(hours=4)

    assert old_code not in manager.sessions
    assert new_code in manager.sessions


async def test_create_session_includes_timer_started_at():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["timer_started_at"] is None


async def test_reset_for_next_lift_clears_timer_started_at():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.sessions[code]["timer_started_at"] = time.time()
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["timer_started_at"] is None


async def test_lock_vote_stores_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    result = await manager.lock_vote(code, "left", "yellow", reason="reasons.bench.yellow.buttocksUp")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_reason"] == "reasons.bench.yellow.buttocksUp"


async def test_lock_vote_reason_defaults_to_none():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "white")
    assert manager.sessions[code]["judges"]["left"]["current_reason"] is None


async def test_session_judges_have_current_reason_field():
    manager = SessionManager()
    code = await manager.create_session("Test")
    for judge in manager.sessions[code]["judges"].values():
        assert "current_reason" in judge
        assert judge["current_reason"] is None


async def test_reset_for_next_lift_clears_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    await manager.lock_vote(code, "left", "yellow", reason="reasons.bench.yellow.buttocksUp")
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["judges"]["left"]["current_reason"] is None


async def test_session_settings_has_require_reasons():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert "require_reasons" in manager.sessions[code]["settings"]
    assert manager.sessions[code]["settings"]["require_reasons"] is False


async def test_update_settings_stores_require_reasons():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, True, "bench", require_reasons=True)
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["require_reasons"] is True


async def test_join_session_returns_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert "reconnect_token" in result
    assert isinstance(result["reconnect_token"], str)
    assert len(result["reconnect_token"]) == 32  # 16 hex bytes


async def test_reconnect_token_stored_in_judge_state():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    stored = manager.sessions[code]["judges"]["left"]["reconnect_token"]
    assert stored == result["reconnect_token"]


async def test_reconnect_token_survives_reset_for_next_lift():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "left_judge")
    token = result["reconnect_token"]
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["judges"]["left"]["reconnect_token"] == token


async def test_snapshot_excludes_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "sessions.json")
        manager.save_snapshot(path)
        with open(path) as f:
            data = json.load(f)
    for judge in data[code]["judges"].values():
        assert "reconnect_token" not in judge


async def test_display_join_returns_no_reconnect_token():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert result.get("reconnect_token") is None


async def test_lock_vote_rejects_already_locked_judge():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")

    await manager.lock_vote(code, "left", "blue")
    result = await manager.lock_vote(code, "left", "red")  # second attempt

    assert result["success"] is False
    assert "already locked" in result["error"].lower()
    # original vote must not be overwritten
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "blue"


async def test_lock_vote_invalid_position_fails():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = await manager.lock_vote(code, "invalid", "white")
    assert result["success"] is False
    assert "invalid position" in result["error"].lower()


async def test_lock_vote_sets_phase_results_when_all_locked():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    result = await manager.lock_vote(code, "right", "white")

    assert result["all_locked"] is True
    assert manager.sessions[code]["phase"] == "results"


async def test_lock_vote_computes_timer_frozen_ms_when_timer_running():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")
    manager.sessions[code]["timer_started_at"] = time.time() - 10  # 10s elapsed

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    frozen = manager.sessions[code]["timer_frozen_ms"]
    assert frozen is not None
    assert 49000 < frozen < 51000  # ~50s remaining
    assert manager.sessions[code]["timer_started_at"] is None


async def test_lock_vote_timer_frozen_ms_none_when_no_timer():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")
    # timer_started_at remains None

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    assert manager.sessions[code]["timer_frozen_ms"] is None


async def test_reset_for_next_lift_clears_phase_and_frozen_ms():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    await manager.lock_vote(code, "left", "white")
    await manager.lock_vote(code, "center", "white")
    await manager.lock_vote(code, "right", "white")

    await manager.reset_for_next_lift(code)

    assert manager.sessions[code]["phase"] == "voting"
    assert manager.sessions[code]["timer_frozen_ms"] is None


async def test_create_session_has_voting_phase():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["phase"] == "voting"
    assert manager.sessions[code]["timer_frozen_ms"] is None


async def test_disconnected_judge_without_vote_blocks_results():
    """Results must not show if a judge disconnected before voting (IPF rule).

    The positive case — all 3 judges lock → results show — is covered by
    test_all_votes_locked_triggers_results.
    """
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    # Simulate right judge disconnecting without voting
    manager.sessions[code]["judges"]["right"]["connected"] = False

    first = await manager.lock_vote(code, "left", "white")
    assert first["success"] is True
    result = await manager.lock_vote(code, "center", "white")

    assert result["all_locked"] is False
    assert manager.sessions[code]["state"] != "showing_results"


async def test_create_session_defaults_kind_to_generic():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["kind"] == "generic"


async def test_create_session_accepts_vportal_kind():
    manager = SessionManager()
    code = await manager.create_session("Test", kind="vportal")
    assert manager.sessions[code]["kind"] == "vportal"


async def test_create_session_rejects_unknown_kind():
    manager = SessionManager()
    with pytest.raises(ValueError):
        await manager.create_session("Test", kind="bogus")


async def test_new_session_starts_at_lift_id_zero():
    manager = SessionManager()
    code = await manager.create_session("Test")
    assert manager.sessions[code]["lift_id"] == 0


async def test_reset_for_next_lift_increments_lift_id():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.reset_for_next_lift(code)
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["lift_id"] == 2


async def test_lock_vote_rejects_stale_lift_id():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.reset_for_next_lift(code)

    result = await manager.lock_vote(code, "left", "white", lift_id=0)

    assert result["success"] is False
    assert result["error"] == "Lift changed"
    assert manager.sessions[code]["judges"]["left"]["locked"] is False


async def test_lock_vote_stale_lift_id_wins_over_missing_mandatory_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.reset_for_next_lift(code)
    manager.sessions[code]["settings"]["require_reasons"] = True

    result = await manager.lock_vote(code, "left", "red", lift_id=0)

    assert result["success"] is False
    assert result["error"] == "Lift changed"
    assert manager.sessions[code]["judges"]["left"]["locked"] is False


async def test_lock_vote_rejects_missing_reason_when_mandatory():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.sessions[code]["settings"]["require_reasons"] = True

    result = await manager.lock_vote(code, "left", "yellow", lift_id=0)

    assert result["success"] is False
    assert result["error"] == "Reason required"
    assert manager.sessions[code]["judges"]["left"]["locked"] is False


async def test_lock_vote_resend_of_stored_vote_is_not_blocked_by_mandatory_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.lock_vote(code, "left", "red")
    manager.sessions[code]["settings"]["require_reasons"] = True

    result = await manager.lock_vote(code, "left", "red")

    assert result["error"] == "Vote already locked"
    assert result["current_vote"] == "red"


async def test_lock_vote_accepts_matching_lift_id():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.reset_for_next_lift(code)

    result = await manager.lock_vote(code, "left", "white", lift_id=1)

    assert result["success"] is True


async def test_lock_vote_without_lift_id_skips_check():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.reset_for_next_lift(code)

    result = await manager.lock_vote(code, "left", "white")

    assert result["success"] is True


async def test_lock_vote_already_locked_returns_stored_vote():
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.lock_vote(code, "left", "red", reason="reasons.squat.red.depth")

    result = await manager.lock_vote(code, "left", "white")

    assert result["current_vote"] == "red"
    assert result["current_reason"] == "reasons.squat.red.depth"


async def test_load_snapshot_defaults_missing_lift_id(tmp_path):
    path = str(tmp_path / "snap.json")
    manager = SessionManager()
    code = await manager.create_session("Test")
    del manager.sessions[code]["lift_id"]
    manager.save_snapshot(path)

    restored = SessionManager()
    restored.load_snapshot(path)

    assert restored.sessions[code]["lift_id"] == 0


async def test_load_snapshot_keeps_stored_show_explanations(tmp_path):
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.update_settings(code, False, "squat")
    path = str(tmp_path / "sessions.json")
    manager.save_snapshot(path)

    restored = SessionManager()
    restored.load_snapshot(path)
    assert restored.sessions[code]["settings"]["show_explanations"] is False


async def test_save_snapshot_if_changed_skips_unchanged_state(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    await manager.create_session("Test")
    assert await manager.save_snapshot_if_changed(path) is True
    os.remove(path)

    assert await manager.save_snapshot_if_changed(path) is False
    assert not os.path.exists(path)


async def test_save_snapshot_if_changed_writes_after_mutation(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.save_snapshot_if_changed(path)

    await manager.lock_vote(code, "left", "white")

    assert await manager.save_snapshot_if_changed(path) is True
    with open(path) as f:
        assert json.load(f)[code]["judges"]["left"]["current_vote"] == "white"


async def test_save_snapshot_if_changed_writes_empty_once_after_last_session_deleted(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.save_snapshot_if_changed(path)

    manager.delete_session(code)

    assert await manager.save_snapshot_if_changed(path) is True
    with open(path) as f:
        assert json.load(f) == {}
    assert await manager.save_snapshot_if_changed(path) is False


async def test_save_snapshot_if_changed_writes_in_thread(tmp_path, monkeypatch):
    import iron_verdict.session as session_module

    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    await manager.create_session("Test")
    calls = []
    real_to_thread = asyncio.to_thread

    async def recording_to_thread(func, *args, **kwargs):
        calls.append(func)
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(session_module.asyncio, "to_thread", recording_to_thread)

    await manager.save_snapshot_if_changed(path)

    assert calls == [manager._write_snapshot]
    assert os.path.exists(path)


async def test_save_snapshot_if_changed_skips_fresh_start_without_sessions(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    manager.load_snapshot(path)

    assert await manager.save_snapshot_if_changed(path) is False
    assert not os.path.exists(path)


async def test_save_snapshot_if_changed_skips_right_after_restore(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    manager.save_snapshot(path)

    restored = SessionManager()
    restored.load_snapshot(path)

    assert await restored.save_snapshot_if_changed(path) is False
    assert code in restored.sessions


async def test_save_snapshot_if_changed_skips_after_unconditional_save(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    await manager.create_session("Test")
    manager.save_snapshot(path)

    assert await manager.save_snapshot_if_changed(path) is False


async def test_snapshot_written_in_thread_restores_sessions(tmp_path):
    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    code = await manager.create_session("Test")
    await manager.lock_vote(code, "center", "red")
    await manager.save_snapshot_if_changed(path)

    restored = SessionManager()
    restored.load_snapshot(path)

    assert restored.sessions[code]["judges"]["center"]["current_vote"] == "red"
    assert restored.sessions[code]["last_activity"] == manager.sessions[code]["last_activity"]


def _ticks(n):
    """Fake sleep for cleanup_loop: returns n times, then stops the loop."""
    calls = {"count": 0}

    async def sleep(_seconds):
        calls["count"] += 1
        if calls["count"] > n:
            raise asyncio.CancelledError

    return sleep


async def test_cleanup_loop_saves_changed_snapshot_in_thread_and_skips_idle_ticks(tmp_path, monkeypatch):
    from iron_verdict.main import cleanup_loop
    import iron_verdict.session as session_module

    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    await manager.create_session("Test")
    writes = []
    real_to_thread = asyncio.to_thread

    async def recording_to_thread(func, *args, **kwargs):
        writes.append(func)
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(session_module.asyncio, "to_thread", recording_to_thread)
    monkeypatch.setattr(manager, "save_snapshot", lambda _path: pytest.fail("sync save in loop"))

    with pytest.raises(asyncio.CancelledError):
        await cleanup_loop(manager, path, 4, sleep=_ticks(3))

    assert writes == [manager._write_snapshot]
    assert os.path.exists(path)


async def test_cleanup_loop_logs_failed_snapshot_write_and_retries_next_tick(tmp_path, monkeypatch, caplog):
    import logging
    from iron_verdict.main import cleanup_loop

    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    await manager.create_session("Test")
    real_write = manager._write_snapshot
    calls = {"count": 0}

    def failing_once_write(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("No space left on device")
        real_write(*args)

    monkeypatch.setattr(manager, "_write_snapshot", failing_once_write)

    with caplog.at_level(logging.ERROR, logger="iron_verdict"):
        with pytest.raises(asyncio.CancelledError):
            await cleanup_loop(manager, path, 4, sleep=_ticks(2))

    assert calls["count"] == 2
    assert os.path.exists(path)
    failures = [r for r in caplog.records if r.getMessage() == "snapshot_save_failed"]
    assert len(failures) == 1
    assert failures[0].exc_info[0] is OSError


async def test_cleanup_loop_keeps_running_after_cleanup_expired_fails(tmp_path, monkeypatch, caplog):
    import logging
    from iron_verdict.main import cleanup_loop

    manager = SessionManager()
    cleanups = []

    def failing_cleanup(hours):
        cleanups.append(hours)
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "cleanup_expired", failing_cleanup)

    with caplog.at_level(logging.ERROR, logger="iron_verdict"):
        with pytest.raises(asyncio.CancelledError):
            await cleanup_loop(manager, str(tmp_path / "sessions.json"), 4, sleep=_ticks(60))

    assert cleanups == [4, 4]
    assert [r.getMessage() for r in caplog.records].count("session_cleanup_failed") == 2


async def test_lifespan_shutdown_completes_after_failed_snapshot_write(tmp_path, monkeypatch):
    import functools
    import iron_verdict.main as main_module

    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    real_write = manager._write_snapshot
    loop = asyncio.get_running_loop()
    failed = asyncio.Event()
    calls = {"count": 0}

    def failing_once_write(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            loop.call_soon_threadsafe(failed.set)
            raise OSError("Read-only file system")
        real_write(*args)

    async def fast_sleep(_seconds):
        await asyncio.sleep(0)

    monkeypatch.setattr(manager, "_write_snapshot", failing_once_write)
    monkeypatch.setattr(main_module, "session_manager", manager)
    monkeypatch.setattr(main_module.settings, "SNAPSHOT_PATH", path)
    monkeypatch.setattr(main_module, "cleanup_loop", functools.partial(main_module.cleanup_loop, sleep=fast_sleep))

    async with main_module.lifespan(main_module.app):
        await manager.create_session("Changed after startup load")
        await asyncio.wait_for(failed.wait(), timeout=5)
        await asyncio.sleep(0.05)  # let the loop task get past the failed write before shutdown

    # The fallback shutdown save ran: the snapshot on disk holds the session.
    with open(path, encoding="utf-8") as f:
        assert list(json.load(f)) == list(manager.sessions)


def test_save_snapshot_waits_for_in_flight_write(tmp_path):
    import threading

    path = str(tmp_path / "sessions.json")
    manager = SessionManager()
    manager._write_lock.acquire()
    shutdown = threading.Thread(target=manager.save_snapshot, args=(path,))
    try:
        shutdown.start()
        shutdown.join(timeout=0.2)
        assert shutdown.is_alive()
        assert not os.path.exists(path)
    finally:
        manager._write_lock.release()
    shutdown.join(timeout=5)

    assert not shutdown.is_alive()
    with open(path) as f:
        assert json.load(f) == {}
