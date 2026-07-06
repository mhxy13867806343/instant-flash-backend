from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.models.chat import GlobalChatSession
from app.core.chat_ws import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["聊天系统 WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing token")
        return

    user_id = decode_access_token(token)
    if not user_id:
        await websocket.accept()
        await websocket.close(code=4002, reason="Invalid token")
        return

    user = db.query(User).filter(User.user_id == user_id, User.is_active.is_(True)).one_or_none()
    if not user:
        await websocket.accept()
        await websocket.close(code=4003, reason="User not active")
        return

    # Store connection in manager
    await manager.connect(user_id, websocket)

    try:
        while True:
            # Expect client messages in JSON format
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif action == "typing":
                # Handle typing indicator events
                target_id = data.get("targetId")
                target_type = data.get("targetType", "private")
                if target_id:
                    if target_type == "private":
                        session = db.query(GlobalChatSession).filter(
                            GlobalChatSession.session_id == target_id
                        ).first()
                        if session:
                            receiver_id = session.user_two_id if session.user_one_id == user_id else session.user_one_id
                            await manager.broadcast_system_event(
                                [receiver_id],
                                "typing",
                                {"sessionId": target_id, "userId": user_id, "isTyping": data.get("isTyping", True)}
                            )
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.warning(f"Error in websocket loop for user {user_id}: {e}")
        manager.disconnect(user_id, websocket)
