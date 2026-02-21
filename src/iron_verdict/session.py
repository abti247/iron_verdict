import asyncio
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List

VALID_LIFT_TYPES = {"squat", "bench", "deadlift"}


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def generate_session_code(self) -> str:
        """Generate a unique 8-character alphanumeric session code."""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if code not in self.sessions:
                return code

    async def create_session(self, name: str) -> str:
        """Create a new session and return its code."""
        async with self._lock:
            code = self.generate_session_code()
            self.sessions[code] = {
                "name": name,
                "judges": {
                    "left": {
                        "connected": False,
                        "is_head": False,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                    },
                    "center": {
                        "connected": False,
                        "is_head": True,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                    },
                    "right": {
                        "connected": False,
                        "is_head": False,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                    },
                },
                "state": "waiting",
                "timer_state": "idle",
                "timer_started_at": None,
                "settings": {
                    "show_explanations": False,
                    "lift_type": "squat",
                },
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
        # Validate role
        valid_roles = {"left_judge", "center_judge", "right_judge", "display"}
        if not role or role not in valid_roles:
            return {"success": False, "error": "Invalid role"}

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

    async def lock_vote(self, code: str, position: str, color: str, reason: str | None = None) -> Dict[str, Any]:
        """
        Lock in a judge's vote.

        Args:
            code: Session code
            position: Judge position ("left", "center", "right")
            color: Vote color ("white", "red", "blue", "yellow")
            reason: Optional reason string for a red/yellow card; None if no reason given

        Returns:
            Dict with success status and all_locked flag
        """
        async with self._lock:
            if code not in self.sessions:
                return {"success": False, "error": "Session not found"}

            session = self.sessions[code]
            judge = session["judges"][position]

            judge["current_vote"] = color
            judge["current_reason"] = reason
            judge["locked"] = True
            session["last_activity"] = datetime.now()

            # Check if all judges locked
            all_locked = all(
                j["locked"] for j in session["judges"].values() if j["connected"]
            )

            if all_locked:
                session["state"] = "showing_results"

            return {"success": True, "all_locked": all_locked}

    async def reset_for_next_lift(self, code: str) -> Dict[str, Any]:
        """Reset session state for next lift."""
        async with self._lock:
            if code not in self.sessions:
                return {"success": False, "error": "Session not found"}

            session = self.sessions[code]

            for judge in session["judges"].values():
                judge["current_vote"] = None
                judge["current_reason"] = None
                judge["locked"] = False

            session["state"] = "waiting"
            session["timer_started_at"] = None
            session["last_activity"] = datetime.now()

            return {"success": True}

    def update_settings(self, code: str, show_explanations: bool, lift_type: str) -> Dict[str, Any]:
        """Update head judge display settings."""
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}
        if lift_type not in VALID_LIFT_TYPES:
            return {"success": False, "error": "Invalid lift type"}
        session = self.sessions[code]
        session["settings"]["show_explanations"] = show_explanations
        session["settings"]["lift_type"] = lift_type
        session["last_activity"] = datetime.now()
        return {"success": True}

    def get_expired_sessions(self, hours: int = 4) -> List[str]:
        """Get list of session codes that have expired."""
        cutoff = datetime.now() - timedelta(hours=hours)
        expired = []

        for code, session in self.sessions.items():
            if session["last_activity"] < cutoff:
                expired.append(code)

        return expired

    def delete_session(self, code: str) -> None:
        """Delete a session from memory."""
        if code in self.sessions:
            del self.sessions[code]

    def cleanup_expired(self, hours: int) -> None:
        """Delete all sessions inactive for longer than `hours`."""
        expired = self.get_expired_sessions(hours)
        for code in expired:
            self.delete_session(code)
