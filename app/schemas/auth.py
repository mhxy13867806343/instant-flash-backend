from __future__ import annotations

from pydantic import BaseModel, Field


class DevTokenRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=64)
    openid: str | None = Field(default=None, max_length=128)
    unionid: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    nickname: str | None = Field(default=None, max_length=64)
    avatar: str | None = None


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    userId: str

