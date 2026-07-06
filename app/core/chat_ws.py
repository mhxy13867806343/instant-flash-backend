from __future__ import annotations

import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # Map user_id to a list of active WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected. Active connections: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected.")

    async def send_personal_message(self, user_id: str, message: dict[str, Any]) -> None:
        """Send message to all active connections of a specific user."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Error sending message to user {user_id}: {e}")

    async def send_private_message(self, sender_id: str, receiver_id: str, message_data: dict[str, Any]) -> None:
        """Push a private message to both the sender and the receiver."""
        payload = {
            "type": "private_message",
            "data": message_data
        }
        await self.send_personal_message(sender_id, payload)
        if sender_id != receiver_id:
            await self.send_personal_message(receiver_id, payload)

    async def broadcast_to_group(self, group_id: str, member_ids: list[str], message_data: dict[str, Any]) -> None:
        """Broadcast a group message to all online group members."""
        payload = {
            "type": "group_message",
            "data": message_data
        }
        for uid in member_ids:
            await self.send_personal_message(uid, payload)

    async def broadcast_system_event(self, user_ids: list[str], event_type: str, data: dict[str, Any]) -> None:
        """Broadcast custom real-time events (like typing, recall, group deletion, mute/unmute)."""
        payload = {
            "type": event_type,
            "data": data
        }
        for uid in user_ids:
            await self.send_personal_message(uid, payload)


# Global connection manager instance
manager = ConnectionManager()
