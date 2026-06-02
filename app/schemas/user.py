from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nickname: str | None = Field(default=None, max_length=64, title="昵称", description="用户展示昵称")
    avatar: str | None = Field(default=None, title="头像", description="用户头像 URL")
    gender: str | None = Field(default=None, max_length=16, title="性别", description="男/女/保密等展示值")
    bio: str | None = Field(
        default=None,
        validation_alias=AliasChoices("bio", "signature", "intro"),
        max_length=300,
        title="个性签名",
        description="用户个人简介/个性签名，兼容 signature、intro 字段",
    )
    province: str | None = Field(default=None, max_length=64, title="省份", description="用户所在省份")
    city: str | None = Field(default=None, max_length=64, title="城市", description="用户所在城市")
    district: str | None = Field(default=None, max_length=64, title="区县", description="用户所在区县")
    phone: str | None = Field(default=None, max_length=32, title="手机号", description="用户手机号")


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    userId: str = Field(title="业务用户 ID", description="登录时创建的业务用户 ID")
    openid: str | None = Field(default=None, title="微信 OpenID", description="微信小程序 OpenID")
    unionid: str | None = Field(default=None, title="微信 UnionID", description="微信开放平台 UnionID")
    phone: str | None = Field(default=None, title="手机号", description="用户手机号")
    nickname: str | None = Field(default=None, title="昵称", description="用户昵称")
    avatar: str | None = Field(default=None, title="头像", description="用户头像 URL")
    gender: str | None = Field(default=None, title="性别", description="用户性别")
    bio: str | None = Field(default=None, title="个性签名", description="用户个人简介/个性签名")
    signature: str | None = Field(default=None, title="个性签名兼容字段", description="兼容前端读取的 signature 字段，值同 bio")
    province: str | None = Field(default=None, title="省份", description="用户所在省份")
    city: str | None = Field(default=None, title="城市", description="用户所在城市")
    district: str | None = Field(default=None, title="区县", description="用户所在区县")
    isActive: bool = Field(title="是否启用", description="false 表示用户被后台禁用")
    createTime: datetime = Field(title="创建时间", description="用户创建时间")
    updateTime: datetime = Field(title="更新时间", description="用户资料更新时间")
    lastTime: datetime = Field(title="最近活动时间", description="最近一次业务访问/操作时间")
