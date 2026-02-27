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
    assert session["settings"]["show_explanations"] is False
    assert session["settings"]["lift_type"] == "squat"


async def test_update_settings_stores_values():
    manager = SessionManager()
    code = await manager.create_session("Test")
    result = manager.update_settings(code, True, "bench")
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["show_explanations"] is True
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
    import time
    manager.sessions[code]["timer_started_at"] = time.time()
    await manager.reset_for_next_lift(code)
    assert manager.sessions[code]["timer_started_at"] is None


async def test_lock_vote_stores_reason():
    manager = SessionManager()
    code = await manager.create_session("Test")
    manager.join_session(code, "left_judge")
    result = await manager.lock_vote(code, "left", "yellow", reason="Buttocks up")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_reason"] == "Buttocks up"


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
    await manager.lock_vote(code, "left", "yellow", reason="Buttocks up")
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


import json
import tempfile
import os


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
