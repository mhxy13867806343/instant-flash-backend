from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)
    avatar: str | None = None
    gender: str | None = Field(default=None, max_length=16)
    province: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    userId: str
    openid: str | None = None
    unionid: str | None = None
    phone: str | None = None
    nickname: str | None = None
    avatar: str | None = None
    gender: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    isActive: bool
    createTime: datetime
    updateTime: datetime
    lastTime: datetime

