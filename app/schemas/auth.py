from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.configs import TOKEN_TYPE_BEARER


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
    tokenType: str = Field(default=TOKEN_TYPE_BEARER, title="令牌类型", description="固定为 Bearer")
    userId: str = Field(title="业务用户 ID", description="当前登录用户 ID")


class WxLoginResponse(BaseModel):
    accessToken: str = Field(title="访问令牌", description="Bearer Token")
    token: str = Field(title="兼容 Token", description="兼容前端读取的 token 字段，值同 accessToken")
    tokenType: str = Field(default=TOKEN_TYPE_BEARER, title="令牌类型", description="固定为 Bearer")
    user: dict[str, object | None] = Field(title="用户信息", description="当前登录用户资料")


class ThirdPartyLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    platform: str = Field(
        ...,
        pattern="^(wechat|qq|alipay|[a-zA-Z0-9_-]{2,32})$",
        description="第三方平台标识，例如 wechat / qq / alipay，或自定义平台",
    )
    openid: str = Field(..., min_length=1, max_length=128, description="第三方平台用户标识 openid")
    unionid: str | None = Field(default=None, max_length=128, description="可选第三方平台统一标识 unionid")
    nickname: str | None = Field(default=None, max_length=64, description="第三方账户昵称，注册时作为初始昵称")
    avatar: str | None = Field(default=None, max_length=512, description="第三方账户头像，注册时作为初始头像")
    gender: str | None = Field(default=None, max_length=16, description="性别")
    bio: str | None = Field(default=None, max_length=300, description="个人签名")
    province: str | None = Field(default=None, max_length=64, description="所在省份")
    city: str | None = Field(default=None, max_length=64, description="所在城市")
    district: str | None = Field(default=None, max_length=64, description="所在区县")
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


class ThirdPartyLoginResponse(BaseModel):
    accessToken: str = Field(title="访问令牌", description="Bearer Token")
    token: str = Field(title="兼容 Token", description="兼容前端读取的 token 字段，值同 accessToken")
    tokenType: str = Field(default=TOKEN_TYPE_BEARER, title="令牌类型")
    isNewUser: bool = Field(title="是否为新用户", description="首次登录自动注册成功返回 true")
    user: dict[str, object | None] = Field(title="用户信息", description="当前登录用户资料")


class PhoneLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    phone: str = Field(..., max_length=32, title="手机号", description="登录用户的手机号")
    code: str = Field(
        ...,
        validation_alias=AliasChoices("code", "verifyCode", "verificationCode", "smsCode"),
        max_length=16,
        title="短信验证码",
        description="手机号验证码，测试环境固定 123456",
    )
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
    )


class PhoneLoginResponse(BaseModel):
    accessToken: str = Field(title="访问令牌", description="Bearer Token")
    token: str = Field(title="兼容 Token", description="值同 accessToken")
    tokenType: str = Field(default=TOKEN_TYPE_BEARER, title="令牌类型")
    isNewUser: bool = Field(title="是否为新用户", description="首次登录自动注册成功返回 true")
    user: dict[str, object | None] = Field(title="用户信息", description="当前登录用户资料")


class QrCodeCreateResponse(BaseModel):
    qrId: str = Field(title="二维码 ID", description="PC 端轮询状态所用的唯一标识")
    ticket: str = Field(title="扫码票据", description="供手机 App 扫码后回传的票据")
    content: str = Field(title="二维码内容", description="二维码承载的原始字符串，前端据此渲染二维码图片")
    expireIn: int = Field(title="有效期(秒)", description="二维码有效期，固定 120 秒，过期后需刷新")
    status: str = Field(title="状态", description="初始状态为 pending")


class QrCodeScanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        alias="qrId",
        validation_alias=AliasChoices("qrId", "qr_id"),
        title="二维码 ID",
        description="扫码内容中携带的 qrId",
    )
    ticket: str = Field(
        ...,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("ticket", "qrTicket"),
        title="扫码票据",
        description="手机 App 扫码得到的 ticket",
    )


class QrCodeScanResponse(BaseModel):
    qrId: str = Field(title="二维码 ID")
    status: str = Field(title="状态", description="扫码成功后为 scanned")
    message: str = Field(title="提示信息")


class QrCodeConfirmRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    qr_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        alias="qrId",
        validation_alias=AliasChoices("qrId", "qr_id"),
        title="二维码 ID",
        description="扫码内容中携带的 qrId",
    )
    ticket: str = Field(
        ...,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("ticket", "qrTicket"),
        title="扫码票据",
        description="手机 App 扫码得到的 ticket",
    )
    action: str = Field(
        default="confirm",
        pattern="^(confirm|cancel)$",
        title="操作",
        description="confirm 确认登录，cancel 取消登录",
    )


class QrCodeConfirmResponse(BaseModel):
    qrId: str = Field(title="二维码 ID")
    status: str = Field(title="状态", description="确认后为 confirmed，取消后为 cancelled")
    message: str = Field(title="提示信息")


class QrCodeStatusResponse(BaseModel):
    qrId: str = Field(title="二维码 ID")
    status: str = Field(
        title="状态",
        description="pending 待扫码 / scanned 已扫码待确认 / confirmed 已确认 / cancelled 已取消 / expired 已过期",
    )
    accessToken: str | None = Field(default=None, title="访问令牌", description="仅在 confirmed 时返回一次")
    token: str | None = Field(default=None, title="兼容 Token", description="值同 accessToken")
    tokenType: str = Field(default=TOKEN_TYPE_BEARER, title="令牌类型")
    user: dict[str, object | None] | None = Field(default=None, title="用户信息", description="仅在 confirmed 时返回")


