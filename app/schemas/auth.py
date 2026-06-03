from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class DevTokenRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str | None = Field(
        default=None,
        alias="userId",
        validation_alias=AliasChoices("userId", "user_id"),
        max_length=64,
        title="业务用户 ID",
        description="开发调试指定的用户 ID，不传则自动生成",
    )
    openid: str | None = Field(default=None, max_length=128, title="微信 OpenID", description="开发调试用 OpenID")
    unionid: str | None = Field(default=None, max_length=128, title="微信 UnionID", description="开发调试用 UnionID")
    phone: str | None = Field(default=None, max_length=32, title="手机号", description="用户手机号")
    code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("code", "verifyCode", "verificationCode", "smsCode"),
        max_length=16,
        title="验证码",
        description="手机号登录验证码；测试环境固定 123456",
    )
    nickname: str | None = Field(default=None, max_length=64, title="昵称", description="用户昵称")
    avatar: str | None = Field(default=None, title="头像", description="用户头像 URL")
    bio: str | None = Field(default=None, max_length=300, title="个性签名", description="用户个人简介/个性签名")
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


class WxLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(min_length=1, max_length=256, title="微信登录 code", description="小程序 uni.login/wx.login 返回的临时 code")
    nickname: str | None = Field(default=None, max_length=64, title="昵称", description="微信授权昵称")
    avatar: str | None = Field(default=None, title="头像", description="微信头像 URL")
    phone: str | None = Field(default=None, max_length=32, title="手机号", description="授权手机号")
    gender: str | None = Field(default=None, max_length=16, title="性别", description="性别展示值")
    bio: str | None = Field(default=None, max_length=300, title="个性签名", description="用户个人简介/个性签名")
    province: str | None = Field(default=None, max_length=64, title="省份", description="省份")
    city: str | None = Field(default=None, max_length=64, title="城市", description="城市")
    district: str | None = Field(default=None, max_length=64, title="区县", description="区县")
    client_type: str | None = Field(
        default="miniprogram",
        alias="clientType",
        validation_alias=AliasChoices("clientType", "client_type", "platform", "appPlatform"),
        max_length=32,
        title="移动端类型",
        description="移动端来源类型：android、ios、harmonyos、miniprogram、h5",
    )
    client_subtype: str | None = Field(
        default="wechat",
        alias="clientSubtype",
        validation_alias=AliasChoices("clientSubtype", "client_subtype", "miniProgramType", "mpType"),
        max_length=64,
        title="小程序类型",
        description="当 clientType 为 miniprogram 时可传：wechat、alipay、douyin、qq、baidu 等",
    )


class TokenResponse(BaseModel):
    accessToken: str = Field(title="访问令牌", description="Bearer Token")
    tokenType: str = Field(default="Bearer", title="令牌类型", description="固定为 Bearer")
    userId: str = Field(title="业务用户 ID", description="当前登录用户 ID")


class WxLoginResponse(BaseModel):
    accessToken: str = Field(title="访问令牌", description="Bearer Token")
    token: str = Field(title="兼容 Token", description="兼容前端读取的 token 字段，值同 accessToken")
    tokenType: str = Field(default="Bearer", title="令牌类型", description="固定为 Bearer")
    user: dict[str, object | None] = Field(title="用户信息", description="当前登录用户资料")
