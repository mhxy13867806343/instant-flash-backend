from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    parentId: str | None = Field(default=None, max_length=64)
    replyToUserId: str | None = Field(default=None, max_length=64)


class CommentOut(BaseModel):
    commentId: str
    postId: str
    userId: str
    content: str
    parentId: str | None = None
    replyToUserId: str | None = None
    createdAt: datetime
    updatedAt: datetime

