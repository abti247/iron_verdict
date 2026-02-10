from judgeme.session import SessionManager
from datetime import datetime, timedelta


def test_generate_session_code_creates_6_char_code():
    manager = SessionManager()
    code = manager.generate_session_code()
    assert len(code) == 6
    assert code.isalnum()


def test_generate_session_code_creates_unique_codes():
    manager = SessionManager()
    code1 = manager.generate_session_code()
    code2 = manager.generate_session_code()
    assert code1 != code2


def test_create_session_returns_code():
    manager = SessionManager()
    code = manager.create_session()
    assert len(code) == 6
    assert code in manager.sessions


def test_create_session_initializes_structure():
    manager = SessionManager()
    code = manager.create_session()
    session = manager.sessions[code]

    assert "judges" in session
    assert "left" in session["judges"]
    assert "center" in session["judges"]
    assert "right" in session["judges"]
    assert "displays" in session
    assert session["state"] == "waiting"
    assert session["timer_state"] == "idle"
    assert "last_activity" in session


def test_join_session_as_judge_succeeds():
    manager = SessionManager()
    code = manager.create_session()

    result = manager.join_session(code, "left_judge")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["connected"] is True


def test_join_session_invalid_code_fails():
    manager = SessionManager()
    result = manager.join_session("INVALID", "left_judge")
    assert result["success"] is False
    assert "Session not found" in result["error"]


def test_join_session_role_already_taken_fails():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    result = manager.join_session(code, "left_judge")
    assert result["success"] is False
    assert "already taken" in result["error"]


def test_join_session_as_display_succeeds():
    manager = SessionManager()
    code = manager.create_session()

    result = manager.join_session(code, "display")
    assert result["success"] is True
    assert len(manager.sessions[code]["displays"]) == 1


def test_join_session_invalid_role_fails():
    manager = SessionManager()
    code = manager.create_session()

    result = manager.join_session(code, "admin")
    assert result["success"] is False
    assert "Invalid role" in result["error"]


def test_lock_vote_succeeds():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    result = manager.lock_vote(code, "left", "white")
    assert result["success"] is True
    assert manager.sessions[code]["judges"]["left"]["current_vote"] == "white"
    assert manager.sessions[code]["judges"]["left"]["locked"] is True


def test_lock_vote_invalid_session_fails():
    manager = SessionManager()
    result = manager.lock_vote("INVALID", "left", "white")
    assert result["success"] is False


def test_lock_vote_updates_last_activity():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")

    before = manager.sessions[code]["last_activity"]
    manager.lock_vote(code, "left", "red")
    after = manager.sessions[code]["last_activity"]

    assert after > before


def test_all_votes_locked_triggers_results():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")
    manager.join_session(code, "center_judge")
    manager.join_session(code, "right_judge")

    manager.lock_vote(code, "left", "white")
    manager.lock_vote(code, "center", "red")
    result = manager.lock_vote(code, "right", "white")

    assert result["all_locked"] is True
    assert manager.sessions[code]["state"] == "showing_results"


def test_reset_for_next_lift_clears_votes():
    manager = SessionManager()
    code = manager.create_session()
    manager.join_session(code, "left_judge")
    manager.lock_vote(code, "left", "white")

    manager.reset_for_next_lift(code)

    session = manager.sessions[code]
    assert session["judges"]["left"]["current_vote"] is None
    assert session["judges"]["left"]["locked"] is False
    assert session["state"] == "waiting"


def test_get_expired_sessions_returns_old_sessions():
    manager = SessionManager()
    code = manager.create_session()

    # Manually set old timestamp
    manager.sessions[code]["last_activity"] = datetime.now() - timedelta(hours=5)

    expired = manager.get_expired_sessions(hours=4)
    assert code in expired


def test_delete_session_removes_from_memory():
    manager = SessionManager()
    code = manager.create_session()

    manager.delete_session(code)
    assert code not in manager.sessions


def test_create_session_initializes_settings():
    manager = SessionManager()
    code = manager.create_session()
    session = manager.sessions[code]
    assert "settings" in session
    assert session["settings"]["show_explanations"] is False
    assert session["settings"]["lift_type"] == "squat"


def test_update_settings_stores_values():
    manager = SessionManager()
    code = manager.create_session()
    result = manager.update_settings(code, True, "bench")
    assert result["success"] is True
    assert manager.sessions[code]["settings"]["show_explanations"] is True
    assert manager.sessions[code]["settings"]["lift_type"] == "bench"


def test_update_settings_invalid_session_fails():
    manager = SessionManager()
    result = manager.update_settings("INVALID", True, "squat")
    assert result["success"] is False
