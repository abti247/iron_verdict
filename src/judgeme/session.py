import random
import string
from datetime import datetime
from typing import Dict, Any


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def generate_session_code(self) -> str:
        """Generate a unique 6-character alphanumeric session code."""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.sessions:
                return code

    def create_session(self) -> str:
        """Create a new session and return its code."""
        code = self.generate_session_code()
        self.sessions[code] = {
            "judges": {
                "left": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
                "center": {
                    "connected": False,
                    "is_head": True,
                    "current_vote": None,
                    "locked": False,
                },
                "right": {
                    "connected": False,
                    "is_head": False,
                    "current_vote": None,
                    "locked": False,
                },
            },
            "displays": [],
            "state": "waiting",
            "timer_state": "idle",
            "last_activity": datetime.now(),
        }
        return code
