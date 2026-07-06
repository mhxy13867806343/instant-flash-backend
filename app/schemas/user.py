from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nickname: str | None = Field(default=None, max_length=64, title="昵称", description="用户展示昵称")
    avatar: str | None = Field(default=None, title="头像", description="用户头像 URL")
    gender: str | None = Field(default=None, max_length=16, title="性别", description="男/女/保密等展示值")
    bio: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "bio",
            "signature",
            "intro",
            "sign",
            "personalSignature",
            "personal_signature",
            "description",
            "desc",
            "summary",
        ),
        max_length=300,
        title="个性签名",
        description="用户个人简介/个性签名，兼容 signature、intro、sign、personalSignature、description 等字段",
    )
    province: str | None = Field(default=None, max_length=64, title="省份", description="用户所在省份")
    city: str | None = Field(default=None, max_length=64, title="城市", description="用户所在城市")
    district: str | None = Field(default=None, max_length=64, title="区县", description="用户所在区县")
    phone: str | None = Field(default=None, max_length=32, title="手机号", description="用户手机号")
    client_type: str | None = Field(
        default=None,
        alias="clientType",
        validation_alias=AliasChoices("clientType", "client_type", "platform", "appPlatform"),
        max_length=32,
        title="移动端类型",
        description="移动端来源类型：android、ios、harmonyos、miniprogram、h5",
    )
    client_subtype: str | None = Field(
        default=None,
        alias="clientSubtype",
        validation_alias=AliasChoices("clientSubtype", "client_subtype", "miniProgramType", "mpType"),
        max_length=64,
        title="小程序类型",
        description="当 clientType 为 miniprogram 时可传：wechat、alipay、douyin、qq、baidu 等",
    )


class UserBindPhoneRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    new_phone: str = Field(
        alias="newPhone",
        validation_alias=AliasChoices("newPhone", "new_phone", "phone", "phoneNumber", "mobile", "mobilePhone", "targetPhone", "target_phone"),
        max_length=32,
        title="新手机号",
        description="需要换绑的新手机号",
    )
    code: str = Field(
        validation_alias=AliasChoices("code", "verifyCode", "verificationCode", "smsCode"),
        max_length=16,
        title="验证码",
        description="测试环境固定验证码：123456",
    )


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    userId: str = Field(title="业务用户 ID", description="登录时创建的业务用户 ID")
    openid: str | None = Field(default=None, title="微信 OpenID", description="微信小程序 OpenID")
    unionid: str | None = Field(default=None, title="微信 UnionID", description="微信开放平台 UnionID")
    phone: str | None = Field(default=None, title="手机号", description="用户手机号")
    newPhone: str | None = Field(default=None, title="新手机号", description="用户绑定的新手机号；绑定后登录使用该手机号")
    clientType: str | None = Field(default=None, title="移动端类型", description="android/ios/harmonyos/miniprogram/h5")
    clientSubtype: str | None = Field(default=None, title="小程序类型", description="wechat/alipay/douyin/qq/baidu 等")
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

    deactivationStatus: str | None = Field(default=None, title="注销状态", description="pending/deactivated/None")
    deactivationReason: str | None = Field(default=None, title="注销原因")
    deactivationApplyTime: datetime | None = Field(default=None, title="申请注销时间")
    deactivationEndTime: datetime | None = Field(default=None, title="注销保留截止时间")


class ThirdPartyBindPayload(BaseModel):
    platform: str = Field(
        ...,
        pattern="^(wechat|qq|alipay|[a-zA-Z0-9_-]{2,32})$",
        description="第三方平台标识，默认支持 wechat / qq / alipay，也支持自定义平台",
    )
    openid: str = Field(..., min_length=1, max_length=128, description="第三方平台用户标识 openid")
    unionid: str | None = Field(default=None, max_length=128, description="可选第三方平台统一标识 unionid")
    nickname: str | None = Field(default=None, max_length=64, description="第三方账户昵称快照")
    avatar: str | None = Field(default=None, max_length=512, description="第三方账户头像快照")
    extraData: dict | None = Field(default=None, description="平台特定的额外参数，例如 JSON 自定义配置")


class ThirdPartyUnbindPayload(BaseModel):
    platform: str = Field(..., description="要解绑的第三方平台标识，例如 wechat / qq / alipay")


class ThirdPartyBindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bindingId: str
    userId: str
    platform: str
    openid: str
    unionid: str | None = None
    nickname: str | None = None
    avatar: str | None = None
    createTime: datetime


class BatchFollowRequest(BaseModel):
    followingIds: list[str] = Field(..., min_items=1, max_items=100, description="批量关注/取消关注的用户 ID 列表")


class FollowedUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    userId: str
    nickname: str | None = None
    avatar: str | None = None
    gender: str | None = None
    bio: str | None = None
    createTime: datetime


class UserSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    userId: str
    nickname: str | None = None
    avatar: str | None = None
    gender: str | None = None
    bio: str | None = None
    isFollowing: bool = False
    isFollower: bool = False
    isMutual: bool = False


class UserDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500, description="注销原因，最低10个字，最高500字")

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
