"""WebSocket connection manager for real-time push notifications.

Replaces 30s polling with persistent WebSocket connections.
Auth: first message must be {"type": "auth", "token": "..."}.
"""

import json
from fastapi import WebSocket, WebSocketDisconnect

from .auth import get_current_user_from_token


class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}  # user_id -> [ws, ...]

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        """Register a WebSocket connection for a user."""
        await ws.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)

    def disconnect(self, ws: WebSocket, user_id: int) -> None:
        """Remove a WebSocket connection for a user."""
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, data: dict) -> None:
        """Push JSON data to all active connections for a user."""
        conns = self._connections.get(user_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast(self, data: dict) -> None:
        """Push JSON data to all connected users."""
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, data)

    def get_connected_user_ids(self) -> list[int]:
        """Return list of user IDs with active connections."""
        return list(self._connections.keys())


# Global singleton
ws_manager = ConnectionManager()


async def authenticate_ws(ws: WebSocket) -> int | None:
    """Wait for auth message and return user_id, or None if auth fails."""
    try:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "auth" or not msg.get("token"):
            await ws.send_json({"type": "error", "message": "First message must be auth"})
            return None
        user = get_current_user_from_token(msg["token"])
        if not user:
            await ws.send_json({"type": "error", "message": "Invalid token"})
            return None
        await ws.send_json({"type": "auth_ok", "user_id": user["id"]})
        return user["id"]
    except Exception:
        return None
