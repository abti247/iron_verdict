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

    def join_session(self, code: str, role: str) -> Dict[str, Any]:
        """
        Join a session with specified role.

        Args:
            code: Session code
            role: One of "left_judge", "center_judge", "right_judge", "display"

        Returns:
            Dict with success status and error message if failed
        """
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[code]

        if role == "display":
            return {"success": True, "is_head": False}

        # Parse judge role
        position = role.replace("_judge", "")
        if position not in ["left", "center", "right"]:
            return {"success": False, "error": "Invalid role"}

        judge = session["judges"][position]
        if judge["connected"]:
            return {"success": False, "error": "Role already taken"}

        judge["connected"] = True
        is_head = judge["is_head"]

        return {"success": True, "is_head": is_head}
