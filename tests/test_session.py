from judgeme.session import SessionManager


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
