from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ShareCreate(BaseModel):
    scene: str | None = Field(default=None, max_length=64)
    platform: str | None = Field(default=None, max_length=64)


class ShareOut(BaseModel):
    postId: str
    userId: str
    scene: str | None = None
    platform: str | None = None
    createdAt: datetime

