from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MessageOut(BaseModel):
    messageId: str
    userId: str
    senderId: str | None = None
    type: str
    title: str | None = None
    content: str | None = None
    postId: str | None = None
    commentId: str | None = None
    isRead: bool
    createdAt: datetime
    updatedAt: datetime

