from judgeme.session import SessionManager
from datetime import datetime


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
