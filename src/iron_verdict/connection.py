import asyncio
import logging
from typing import Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("iron_verdict")


class ConnectionManager:
    def __init__(self):
        # Structure: {session_code: {role: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, session_code: str, role: str, websocket: WebSocket):
        """Add a WebSocket connection to a session."""
        async with self._lock:
            if session_code not in self.active_connections:
                self.active_connections[session_code] = {}
            self.active_connections[session_code][role] = websocket

    async def remove_connection(self, session_code: str, role: str):
        """Remove a WebSocket connection from a session."""
        async with self._lock:
            if session_code in self.active_connections:
                self.active_connections[session_code].pop(role, None)
                if not self.active_connections[session_code]:
                    del self.active_connections[session_code]

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
