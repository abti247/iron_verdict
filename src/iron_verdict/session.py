import asyncio
import json
import logging
import math
import os
import secrets
import string
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger("iron_verdict")

VALID_LIFT_TYPES = {"squat", "bench", "deadlift"}
VALID_SESSION_KINDS = {"generic", "vportal"}
# A pause lasts at most 12 h: a typo in the end time (13:00 instead of 14:00)
# would otherwise make a pause of almost 24 h (#163).
PAUSE_MAX_SECONDS = 12 * 60 * 60


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        # Snapshot content last written to (or loaded from) disk; None = unknown, write next time.
        self._last_snapshot: str | None = None
        # Serializes file writes: the shutdown save may run while a periodic write is in its thread.
        self._write_lock = threading.Lock()

    def generate_session_code(self) -> str:
        """Generate a unique 8-character alphanumeric session code."""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if code not in self.sessions:
                return code

    async def create_session(self, name: str, kind: str = "generic") -> str:
        """Create a new session and return its code."""
        if kind not in VALID_SESSION_KINDS:
            raise ValueError(f"Invalid session kind: {kind}")
        async with self._lock:
            code = self.generate_session_code()
            self.sessions[code] = {
                "name": name,
                "kind": kind,
                "judges": {
                    "left": {
                        "connected": False,
                        "is_head": False,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                        "reconnect_token": None,
                    },
                    "center": {
                        "connected": False,
                        "is_head": True,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                        "reconnect_token": None,
                    },
                    "right": {
                        "connected": False,
                        "is_head": False,
                        "current_vote": None,
                        "locked": False,
                        "current_reason": None,
                        "reconnect_token": None,
                    },
                },
                "state": "waiting",
                "timer_state": "idle",
                "timer_started_at": None,
                "phase": "voting",
                "timer_frozen_ms": None,
                "lift_id": 0,
                "settings": {
                    "show_explanations": True,
                    "lift_type": "squat",
                    "require_reasons": False,
                },
                "pause": None,
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

        Deliberately synchronous: the "role free?" check and the write that takes the
        role must stay without an await in between, so two concurrent joins on the
        event loop cannot both pass the check (#57). Do not make this async or add
        an await here; if that becomes necessary, take self._lock around check and write.
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
        token = secrets.token_hex(16)
        judge["reconnect_token"] = token
        return {"success": True, "is_head": is_head, "reconnect_token": token}

    async def lock_vote(
        self, code: str, position: str, color: str, reason: str | None = None, lift_id: int | None = None
    ) -> Dict[str, Any]:
        """
        Lock in a judge's vote.

        Args:
            code: Session code
            position: Judge position ("left", "center", "right")
            color: Vote color ("white", "red", "blue", "yellow")
            reason: Optional reason string for a red/yellow card; None if no reason given
            lift_id: Lift the client voted for; a mismatch rejects the vote ("Lift changed").
                None skips the check (clients from before lift_id existed).

        Checks run in this order: session, position, lift, already locked,
        mandatory reason (red/yellow/blue without reason while require_reasons is on).

        Returns:
            Dict with success status and all_locked flag. Failure errors the caller maps:
            "Lift changed", "Reason required", and "Vote already locked" (carries the
            stored current_vote/current_reason).
        """
        async with self._lock:
            if code not in self.sessions:
                return {"success": False, "error": "Session not found"}

            session = self.sessions[code]

            if position not in session["judges"]:
                return {"success": False, "error": "Invalid position"}

            if lift_id is not None and lift_id != session["lift_id"]:
                return {"success": False, "error": "Lift changed"}

            judge = session["judges"][position]

            if judge["locked"]:
                return {
                    "success": False,
                    "error": "Vote already locked",
                    "current_vote": judge["current_vote"],
                    "current_reason": judge["current_reason"],
                }

            # After the lift and already-locked checks: a stale vote is "Lift changed"
            # and a resend of a stored vote stays idempotent, even if reasons became mandatory meanwhile.
            if session["settings"].get("require_reasons", False) and color != "white" and not reason:
                return {"success": False, "error": "Reason required"}

            judge["current_vote"] = color
            judge["current_reason"] = reason
            judge["locked"] = True
            session["last_activity"] = datetime.now()

            # All three panel positions must lock, regardless of connection state (IPF rule).
            all_locked = all(
                j["locked"] for j in session["judges"].values()
            )

            if all_locked:
                session["state"] = "showing_results"
                session["phase"] = "results"
                if session["timer_started_at"] is not None:
                    elapsed_ms = (time.time() - session["timer_started_at"]) * 1000
                    session["timer_frozen_ms"] = max(0, 60000 - elapsed_ms)
                session["timer_started_at"] = None

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
            session["phase"] = "voting"
            session["timer_frozen_ms"] = None
            session["lift_id"] = session.get("lift_id", 0) + 1
            session["last_activity"] = datetime.now()

            return {"success": True, "lift_id": session["lift_id"]}

    def update_settings(self, code: str, show_explanations: bool, lift_type: str, require_reasons: bool = False) -> Dict[str, Any]:
        """Update head judge display settings."""
        if code not in self.sessions:
            return {"success": False, "error": "Session not found"}
        if lift_type not in VALID_LIFT_TYPES:
            return {"success": False, "error": "Invalid lift type"}
        session = self.sessions[code]
        session["settings"]["show_explanations"] = show_explanations
        session["settings"]["lift_type"] = lift_type
        session["settings"]["require_reasons"] = require_reasons
        session["last_activity"] = datetime.now()
        return {"success": True}

    def start_pause(
        self,
        code: str,
        minutes=None,
        end_at_ms=None,
        next_lift=None,
        now: float | None = None,
    ) -> Dict[str, Any]:
        """Start (or replace) the session's pause, shown on every display (#163).

        Exactly one of *minutes* (end computed with the server clock) or
        *end_at_ms* (a time of day the display converted with its own clock)
        gives the end, stored as epoch seconds. *next_lift* is shown only.

        Errors: "invalid" (malformed input), "past" (end not in the future),
        "too_long" (more than PAUSE_MAX_SECONDS), "Session not found".
        """
        session = self.sessions.get(code)
        if session is None:
            return {"success": False, "error": "Session not found"}
        now = time.time() if now is None else now
        invalid = {"success": False, "error": "invalid"}
        try:
            if next_lift not in VALID_LIFT_TYPES | {None}:
                return invalid
        except TypeError:  # unhashable, e.g. a list
            return invalid
        if (minutes is None) == (end_at_ms is None):
            return invalid
        value = minutes if end_at_ms is None else end_at_ms
        if not _is_number(value) or (minutes is not None and minutes < 1):
            return invalid
        end_at = now + minutes * 60 if end_at_ms is None else end_at_ms / 1000
        if end_at <= now:
            return {"success": False, "error": "past"}
        if end_at - now > PAUSE_MAX_SECONDS:
            return {"success": False, "error": "too_long"}

        session["pause"] = {
            "id": secrets.token_hex(4),
            "end_at": end_at,
            "mode": "minutes" if end_at_ms is None else "until",
            "next_lift": next_lift,
        }
        session["last_activity"] = datetime.now()
        return {"success": True, "pause": session["pause"]}

    def end_pause(self, code: str, pause_id: str | None = None) -> bool:
        """End the session's pause; with *pause_id* only if that pause still runs.

        Returns whether a pause was ended.
        """
        session = self.sessions.get(code)
        if not session or not session.get("pause"):
            return False
        if pause_id is not None and session["pause"]["id"] != pause_id:
            return False
        session["pause"] = None
        session["last_activity"] = datetime.now()
        return True

    def get_expired_sessions(self, hours: int = 4) -> List[str]:
        """Get list of session codes that have expired.

        A session with a running pause never expires: a pause may last longer
        than the timeout (up to PAUSE_MAX_SECONDS) without any other activity.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        now = time.time()
        expired = []

        for code, session in self.sessions.items():
            pause = session.get("pause")
            if pause is not None and pause["end_at"] > now:
                continue
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

    def _serialize_snapshot(self) -> str:
        """Serialize all sessions to a JSON string (reconnect tokens excluded)."""
        data = {}
        for code, session in self.sessions.items():
            s = dict(session)
            s["last_activity"] = session["last_activity"].isoformat()
            s["judges"] = {
                pos: {k: v for k, v in j.items() if k != "reconnect_token"}
                for pos, j in session["judges"].items()
            }
            data[code] = s
        return json.dumps(data)

    def _write_snapshot(self, path: str, content: str, session_count: int) -> None:
        """Atomically write serialized snapshot content to `path`."""
        with self._write_lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, path)
        logger.info("snapshot_saved", extra={"session_count": session_count})

    def save_snapshot(self, path: str) -> None:
        """Write all sessions to a JSON file unconditionally and synchronously (shutdown path)."""
        content = self._serialize_snapshot()
        self._write_snapshot(path, content, len(self.sessions))
        self._last_snapshot = content

    async def save_snapshot_if_changed(self, path: str) -> bool:
        """Write the snapshot in a worker thread if it differs from the last one written.

        Serialization happens here in the event loop, so the thread never reads
        session state that is being mutated concurrently. Returns True if written.
        """
        content = self._serialize_snapshot()
        if content == self._last_snapshot:
            return False
        await asyncio.to_thread(self._write_snapshot, path, content, len(self.sessions))
        self._last_snapshot = content
        return True

    def load_snapshot(self, path: str) -> None:
        """Load sessions from a JSON snapshot file."""
        if not os.path.exists(path):
            # Nothing on disk matches "no sessions": no need to write an empty snapshot.
            self._last_snapshot = self._serialize_snapshot()
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for code, s in data.items():
                s["last_activity"] = datetime.fromisoformat(s["last_activity"])
                # Reset connected state — WebSocket connections are gone after restart
                for judge in s["judges"].values():
                    judge["connected"] = False
                    judge.setdefault("reconnect_token", None)
                s.setdefault("phase", "voting")
                s.setdefault("timer_frozen_ms", None)
                s.setdefault("lift_id", 0)
                s.setdefault("pause", None)
                self.sessions[code] = s
            # Baseline is the restored state: the flags reset above are reset again on every load,
            # so the file needs no rewrite until something actually changes.
            self._last_snapshot = self._serialize_snapshot()
            logger.info("snapshot_loaded", extra={"session_count": len(self.sessions)})
        except Exception:
            logger.exception("snapshot_load_failed")
