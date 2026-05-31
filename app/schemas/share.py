from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ShareCreate(BaseModel):
    scene: str | None = Field(default=None, max_length=64, title="分享场景", description="例如 detail/feed/profile")
    platform: str | None = Field(default=None, max_length=64, title="分享平台", description="例如 h5/wechat/weixin")


class ShareOut(BaseModel):
    postId: str = Field(title="内容 ID", description="被分享的内容 ID")
    userId: str = Field(title="分享人用户 ID", description="登录分享时为业务用户 ID，游客分享为空字符串")
    scene: str | None = Field(default=None, title="分享场景", description="分享发生的页面或业务场景")
    platform: str | None = Field(default=None, title="分享平台", description="分享目标平台")
    createdAt: datetime = Field(title="创建时间", description="分享记录创建时间")
