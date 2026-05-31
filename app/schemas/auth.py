from __future__ import annotations

from pydantic import BaseModel, Field


class DevTokenRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=64)
    openid: str | None = Field(default=None, max_length=128)
    unionid: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    nickname: str | None = Field(default=None, max_length=64)
    avatar: str | None = None


class WxLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=64)
    avatar: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    gender: str | None = Field(default=None, max_length=16)
    province: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    userId: str


class WxLoginResponse(BaseModel):
    accessToken: str
    token: str
    tokenType: str = "Bearer"
    user: dict[str, object | None]
