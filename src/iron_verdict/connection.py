import asyncio
import time
import logging
from typing import Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("iron_verdict")


class ConnectionManager:
    def __init__(self):
        # Structure: {session_code: {role: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._last_pong: Dict[WebSocket, float] = {}
        # Send time of the latest unanswered ping, for the roundtrip metric (#193).
        # Removed with the connection, so closed sockets leave nothing behind.
        self._ping_sent: Dict[WebSocket, float] = {}

    async def add_connection(self, session_code: str, role: str, websocket: WebSocket):
        """Add a WebSocket connection to a session."""
        async with self._lock:
            if session_code not in self.active_connections:
                self.active_connections[session_code] = {}
            self.active_connections[session_code][role] = websocket
            self._last_pong[websocket] = time.monotonic()

    async def remove_connection(self, session_code: str, role: str):
        """Remove a WebSocket connection from a session."""
        async with self._lock:
            if session_code in self.active_connections:
                ws = self.active_connections[session_code].pop(role, None)
                if ws is not None:
                    self._last_pong.pop(ws, None)
                    self._ping_sent.pop(ws, None)
                if not self.active_connections[session_code]:
                    del self.active_connections[session_code]

    async def remove_connection_if_current(self, session_code: str, role: str, websocket: WebSocket) -> bool:
        """Remove *role* only if it is still held by *websocket*; return whether it was.

        A reconnect may already have registered a newer socket under the same
        role — that one must never be removed on behalf of the old socket.
        """
        async with self._lock:
            roles = self.active_connections.get(session_code, {})
            if roles.get(role) is not websocket:
                return False
            del roles[role]
            self._last_pong.pop(websocket, None)
            self._ping_sent.pop(websocket, None)
            if not roles:
                del self.active_connections[session_code]
            return True

    async def get_connection(self, session_code: str, role: str):
        """Return the registered WebSocket for a role, or None."""
        async with self._lock:
            return self.active_connections.get(session_code, {}).get(role)

    async def broadcast_to_session(self, session_code: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a session."""
        # Get connections under lock to avoid race conditions
        async with self._lock:
            if session_code not in self.active_connections:
                return
            # Create a copy of connections to iterate outside the lock
            connections = list(self.active_connections[session_code].values())

        # Send outside lock to avoid blocking other operations
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("broadcast_send_failed", extra={"reason": str(exc)}, exc_info=True)

    async def send_to_role(self, session_code: str, role: str, message: Dict[str, Any]):
        """Send a message to a specific role in a session."""
        # Get websocket under lock
        async with self._lock:
            if session_code not in self.active_connections:
                return
            websocket = self.active_connections[session_code].get(role)

        # Send outside lock
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("send_to_role_failed", extra={"role": role, "reason": str(exc)}, exc_info=True)

    async def count_displays(self, session_code: str) -> int:
        """Count active display connections in a session."""
        async with self._lock:
            if session_code not in self.active_connections:
                return 0
            return sum(
                1 for role in self.active_connections[session_code]
                if role.startswith("display_")
            )

    async def connected_session_codes(self) -> set[str]:
        """Return the codes of all sessions with at least one registered connection."""
        async with self._lock:
            return set(self.active_connections)

    async def count_connections(self) -> int:
        """Count active connections across all sessions."""
        async with self._lock:
            return sum(len(roles) for roles in self.active_connections.values())

    async def send_to_displays(self, session_code: str, message: Dict[str, Any]):
        """Send a message to all display connections in a session."""
        async with self._lock:
            if session_code not in self.active_connections:
                return
            websockets = [
                ws for role, ws in self.active_connections[session_code].items()
                if role.startswith("display_")
            ]

        for websocket in websockets:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("send_to_display_failed", extra={"reason": str(exc)}, exc_info=True)

    async def broadcast_to_others(
        self,
        session_code: str,
        exclude_ws,
        message: Dict[str, Any],
    ):
        """Broadcast to all connections in a session except exclude_ws."""
        async with self._lock:
            if session_code not in self.active_connections:
                return
            targets = [
                ws for ws in self.active_connections[session_code].values()
                if ws is not exclude_ws
            ]
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.warning("broadcast_to_others_send_failed", extra={"reason": str(exc)}, exc_info=True)

    async def mark_ping(self, websocket: WebSocket, now: float | None = None) -> None:
        """Remember when a ping went out; a newer ping replaces an unanswered one.

        Why no ping id: the protocol stays unchanged during a deploy. Matching a
        pong to the latest ping measures a roundtrip over the 5 s interval too
        short, which is acceptable for trends (decided in #193).
        """
        async with self._lock:
            if websocket in self._last_pong:
                self._ping_sent[websocket] = time.monotonic() if now is None else now

    async def mark_pong(self, websocket: WebSocket, now: float | None = None) -> float | None:
        """Record a pong; return the seconds since the ping it answers, or None.

        Only the first pong after a ping is measured.
        """
        now = time.monotonic() if now is None else now
        async with self._lock:
            if websocket not in self._last_pong:
                return None
            self._last_pong[websocket] = now
            sent = self._ping_sent.pop(websocket, None)
            return None if sent is None else now - sent

    async def get_last_pong(self, websocket: WebSocket) -> float | None:
        async with self._lock:
            return self._last_pong.get(websocket)

    async def get_all_connections(self) -> list[tuple[str, str, WebSocket]]:
        """Return (session_code, role, websocket) for every active connection."""
        async with self._lock:
            return [
                (code, role, ws)
                for code, roles in self.active_connections.items()
                for role, ws in roles.items()
            ]
