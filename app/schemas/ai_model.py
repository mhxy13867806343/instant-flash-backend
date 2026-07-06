from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# AI 模型 CRUD Schemas
# ---------------------------------------------------------------------------


class AiModelCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=128, description="模型名称")
    type: str = Field(
        ...,
        pattern="^(text|video|image|multimodal)$",
        description="模型类型：text/video/image/multimodal",
    )
    icon: str | None = Field(default=None, max_length=512, description="模型图标 URL")
    cover: str | None = Field(default=None, max_length=512, description="模型封面 URL")
    description: str | None = Field(default=None, description="模型说明")
    pointsPerUse: int = Field(
        default=1,
        alias="pointsPerUse",
        validation_alias=AliasChoices("pointsPerUse", "points_per_use"),
        ge=1,
        description="每次使用消耗模型积分",
    )
    channel: str = Field(
        default="standard",
        pattern="^(standard|fast|exclusive)$",
        description="通道：standard/fast/exclusive",
    )
    features: list[str] = Field(default_factory=list, description="特性列表")
    sort: int = Field(default=0, ge=0, description="排序权重")
    status: str = Field(
        default="enabled",
        pattern="^(enabled|disabled)$",
        description="状态",
    )


class AiModelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=128)
    type: str | None = Field(default=None, pattern="^(text|video|image|multimodal)$")
    icon: str | None = Field(default=None, max_length=512)
    cover: str | None = Field(default=None, max_length=512)
    description: str | None = Field(default=None)
    pointsPerUse: int | None = Field(
        default=None,
        alias="pointsPerUse",
        validation_alias=AliasChoices("pointsPerUse", "points_per_use"),
        ge=1,
    )
    channel: str | None = Field(default=None, pattern="^(standard|fast|exclusive)$")
    features: list[str] | None = Field(default=None)
    sort: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(enabled|disabled)$")


class AiModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    modelId: str
    name: str
    type: str
    icon: str | None = None
    cover: str | None = None
    description: str | None = None
    pointsPerUse: int = 1
    channel: str = "standard"
    features: list[str] = []
    sort: int = 0
    status: str = "enabled"
    createTime: datetime
    updateTime: datetime


# ---------------------------------------------------------------------------
# 充值套餐 CRUD Schemas
# ---------------------------------------------------------------------------


class AiModelPlanCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=128, description="套餐名称")
    tier: str = Field(
        ...,
        pattern="^(basic|standard|premium|super)$",
        description="档位：basic/standard/premium/super",
    )
    periodType: str = Field(
        ...,
        alias="periodType",
        validation_alias=AliasChoices("periodType", "period_type"),
        pattern="^(day|month|year)$",
        description="周期：day/month/year",
    )
    durationDays: int = Field(
        ...,
        alias="durationDays",
        validation_alias=AliasChoices("durationDays", "duration_days"),
        ge=1,
        description="有效天数",
    )
    originalPrice: int = Field(
        ...,
        alias="originalPrice",
        validation_alias=AliasChoices("originalPrice", "original_price"),
        ge=0,
        description="原价（分）",
    )
    currentPrice: int = Field(
        ...,
        alias="currentPrice",
        validation_alias=AliasChoices("currentPrice", "current_price"),
        ge=0,
        description="现价（分）",
    )
    pointsMonthly: int = Field(
        default=0,
        alias="pointsMonthly",
        validation_alias=AliasChoices("pointsMonthly", "points_monthly"),
        ge=0,
        description="每月赠送模型积分",
    )
    pointsConversionRate: str | None = Field(
        default=None,
        alias="pointsConversionRate",
        validation_alias=AliasChoices("pointsConversionRate", "points_conversion_rate"),
        max_length=64,
        description="积分兑换比例描述",
    )
    features: list[str] = Field(default_factory=list, description="套餐权益列表")
    badge: str | None = Field(default=None, max_length=64, description="徽章文案")
    isRecommended: bool = Field(
        default=False,
        alias="isRecommended",
        validation_alias=AliasChoices("isRecommended", "is_recommended"),
    )
    sort: int = Field(default=0, ge=0)
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")


class AiModelPlanUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=128)
    tier: str | None = Field(default=None, pattern="^(basic|standard|premium|super)$")
    periodType: str | None = Field(
        default=None,
        alias="periodType",
        validation_alias=AliasChoices("periodType", "period_type"),
        pattern="^(day|month|year)$",
    )
    durationDays: int | None = Field(
        default=None,
        alias="durationDays",
        validation_alias=AliasChoices("durationDays", "duration_days"),
        ge=1,
    )
    originalPrice: int | None = Field(
        default=None,
        alias="originalPrice",
        validation_alias=AliasChoices("originalPrice", "original_price"),
        ge=0,
    )
    currentPrice: int | None = Field(
        default=None,
        alias="currentPrice",
        validation_alias=AliasChoices("currentPrice", "current_price"),
        ge=0,
    )
    pointsMonthly: int | None = Field(
        default=None,
        alias="pointsMonthly",
        validation_alias=AliasChoices("pointsMonthly", "points_monthly"),
        ge=0,
    )
    pointsConversionRate: str | None = Field(
        default=None,
        alias="pointsConversionRate",
        validation_alias=AliasChoices("pointsConversionRate", "points_conversion_rate"),
        max_length=64,
    )
    features: list[str] | None = Field(default=None)
    badge: str | None = Field(default=None, max_length=64)
    isRecommended: bool | None = Field(
        default=None,
        alias="isRecommended",
        validation_alias=AliasChoices("isRecommended", "is_recommended"),
    )
    sort: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(enabled|disabled)$")


class AiModelPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    planId: str
    name: str
    tier: str
    periodType: str
    durationDays: int
    originalPrice: int
    currentPrice: int
    pointsMonthly: int = 0
    pointsConversionRate: str | None = None
    features: list[str] = []
    badge: str | None = None
    isRecommended: bool = False
    sort: int = 0
    status: str = "enabled"
    createTime: datetime
    updateTime: datetime


# ---------------------------------------------------------------------------
# 促销活动 CRUD Schemas
# ---------------------------------------------------------------------------


class AiModelPromotionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=128, description="活动名称")
    description: str | None = Field(default=None, description="活动说明")
    discountRate: int = Field(
        default=100,
        alias="discountRate",
        validation_alias=AliasChoices("discountRate", "discount_rate"),
        ge=1,
        le=100,
        description="折扣百分比，100=无折扣，70=7折",
    )
    extraPointsPct: int = Field(
        default=0,
        alias="extraPointsPct",
        validation_alias=AliasChoices("extraPointsPct", "extra_points_pct"),
        ge=0,
        le=500,
        description="额外赠送积分百分比",
    )
    startTime: datetime | None = Field(
        default=None,
        alias="startTime",
        validation_alias=AliasChoices("startTime", "start_time"),
    )
    endTime: datetime | None = Field(
        default=None,
        alias="endTime",
        validation_alias=AliasChoices("endTime", "end_time"),
    )
    applicablePlans: list[str] = Field(
        default_factory=list,
        alias="applicablePlans",
        validation_alias=AliasChoices("applicablePlans", "applicable_plans"),
        description="适用套餐ID列表，空=全部",
    )
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")


class AiModelPromotionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None)
    discountRate: int | None = Field(
        default=None,
        alias="discountRate",
        validation_alias=AliasChoices("discountRate", "discount_rate"),
        ge=1,
        le=100,
    )
    extraPointsPct: int | None = Field(
        default=None,
        alias="extraPointsPct",
        validation_alias=AliasChoices("extraPointsPct", "extra_points_pct"),
        ge=0,
        le=500,
    )
    startTime: datetime | None = Field(
        default=None,
        alias="startTime",
        validation_alias=AliasChoices("startTime", "start_time"),
    )
    endTime: datetime | None = Field(
        default=None,
        alias="endTime",
        validation_alias=AliasChoices("endTime", "end_time"),
    )
    applicablePlans: list[str] | None = Field(
        default=None,
        alias="applicablePlans",
        validation_alias=AliasChoices("applicablePlans", "applicable_plans"),
    )
    status: str | None = Field(default=None, pattern="^(enabled|disabled)$")


class AiModelPromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    promotionId: str
    name: str
    description: str | None = None
    discountRate: int = 100
    extraPointsPct: int = 0
    startTime: datetime | None = None
    endTime: datetime | None = None
    applicablePlans: list[str] = []
    status: str = "enabled"
    createTime: datetime
    updateTime: datetime


# ---------------------------------------------------------------------------
# 移动端请求 / 响应 Schemas
# ---------------------------------------------------------------------------


class AiModelUseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    modelId: str = Field(
        ...,
        alias="modelId",
        validation_alias=AliasChoices("modelId", "model_id"),
        min_length=1,
        max_length=64,
        description="要使用的模型ID",
    )
    prompt: str = Field(..., min_length=1, max_length=5000, description="用户输入的提示词")


class AiModelUsageRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recordId: str
    userId: str
    modelId: str
    modelName: str
    modelType: str
    prompt: str | None = None
    result: str | None = None
    resultType: str = "text"
    pointsConsumed: int = 0
    status: str = "completed"
    createTime: datetime
    updateTime: datetime


class AiModelSubscribeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    planId: str = Field(
        ...,
        alias="planId",
        validation_alias=AliasChoices("planId", "plan_id"),
        min_length=1,
        max_length=64,
        description="套餐ID",
    )
    payMethod: str = Field(
        default="wechat",
        alias="payMethod",
        validation_alias=AliasChoices("payMethod", "pay_method"),
        pattern="^(wechat|alipay)$",
        description="支付方式",
    )


class AiModelSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscriptionId: str
    userId: str
    planId: str
    planName: str
    periodType: str
    payAmount: int
    originalAmount: int
    discountAmount: int = 0
    promotionId: str | None = None
    payMethod: str | None = None
    payStatus: str = "pending"
    pointsGranted: int = 0
    startTime: datetime | None = None
    endTime: datetime | None = None
    autoRenew: bool = False
    createTime: datetime
    updateTime: datetime


class AiModelPointOverview(BaseModel):
    """模型积分概览。"""

    userId: str
    modelPoints: int = 0  # 充值积分余额（不过期）
    dailyModelPoints: int = 0  # 今日赠送积分余额
    dailyExpireAt: str | None = None  # 今日赠送积分过期时间
    vipLevel: str | None = None  # VIP 等级
    vipExpireTime: str | None = None  # VIP 到期时间
    todayGranted: bool = False  # 今日是否已赠送


class BatchDeleteRequest(BaseModel):
    recordIds: list[str] = Field(
        ...,
        alias="recordIds",
        validation_alias=AliasChoices("recordIds", "record_ids"),
        min_length=1,
        description="要删除的记录ID列表",
    )
