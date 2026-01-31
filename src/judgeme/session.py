import random
import string


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def generate_session_code(self) -> str:
        """Generate a unique 6-character alphanumeric session code."""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.sessions:
                return code
