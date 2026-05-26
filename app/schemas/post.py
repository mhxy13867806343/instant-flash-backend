from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    content: str = Field(min_length=1)
    images: list[Any] = Field(default_factory=list)


class PostUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    images: list[Any] | None = None
    status: str | None = Field(default=None, max_length=32)


class PostOut(BaseModel):
    postId: str
    userId: str
    nickname: str | None = None
    avatar: str | None = None
    content: str
    images: list[Any]
    likeCount: int
    commentCount: int
    shareCount: int
    status: str
    isLiked: bool = False
    isOwner: bool = False
    canEdit: bool = False
    canDelete: bool = False
    createdAt: datetime
    updatedAt: datetime


class PostListResponse(BaseModel):
    items: list[PostOut]
    total: int
    limit: int
    offset: int


class LikeResponse(BaseModel):
    postId: str
    isLiked: bool
    likeCount: int

