import asyncio
from typing import Dict, Any
from fastapi import WebSocket


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

    async def broadcast_to_session(self, session_code: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a session."""
        if session_code not in self.active_connections:
            return

        for websocket in self.active_connections[session_code].values():
            try:
                await websocket.send_json(message)
            except Exception:
                # Silently skip failed connections
                pass

    async def send_to_role(self, session_code: str, role: str, message: Dict[str, Any]):
        """Send a message to a specific role in a session."""
        if session_code in self.active_connections:
            websocket = self.active_connections[session_code].get(role)
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception:
                    # Silently skip failed connections
                    pass
