from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 全局设置
# ---------------------------------------------------------------------------

class MallSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pointsSwitch: bool = Field(title="积分开关", description="true=仅积分支付；false=允许价格/积分两种方式")
    remark: str | None = Field(default=None)
    updateTime: datetime = Field(title="最近更新时间")


class MallSettingUpdate(BaseModel):
    pointsSwitch: bool = Field(title="积分开关", description="true=仅积分支付，false=允许价格支付")
    remark: str | None = Field(default=None, title="备注")


# ---------------------------------------------------------------------------
# 商品
# ---------------------------------------------------------------------------

class MallProductCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=128, title="商品标题")
    description: str | None = Field(default=None, title="商品描述", description="支持富文本 HTML")
    images: list[str] = Field(
        default_factory=list,
        title="商品图片列表",
        description="图片 URL 列表，最多 9 张",
        max_length=9,
    )
    cover_image: str | None = Field(
        default=None,
        alias="coverImage",
        validation_alias=AliasChoices("coverImage", "cover_image"),
        max_length=512,
        title="封面图",
        description="封面图URL，与封面视频二选一",
    )
    cover_video: str | None = Field(
        default=None,
        alias="coverVideo",
        validation_alias=AliasChoices("coverVideo", "cover_video"),
        max_length=512,
        title="封面视频",
        description="封面视频URL，与封面图二选一",
    )
    original_price: int = Field(
        alias="originalPrice",
        validation_alias=AliasChoices("originalPrice", "original_price"),
        gt=0,
        title="原价（分）",
        description="原价，单位分（整数），必须 > 0",
    )
    current_price: int | None = Field(
        default=None,
        alias="currentPrice",
        validation_alias=AliasChoices("currentPrice", "current_price"),
        gt=0,
        title="现价（分）",
        description="现价，单位分，不传时自动设为原价的一半；必须 > 0",
    )
    points_cost: int = Field(
        default=0,
        alias="pointsCost",
        validation_alias=AliasChoices("pointsCost", "points_cost"),
        ge=0,
        title="积分兑换价",
        description="积分兑换所需积分数，0 表示不支持积分购买",
    )
    points_only: bool = Field(
        default=False,
        alias="pointsOnly",
        validation_alias=AliasChoices("pointsOnly", "points_only"),
        title="仅积分购买",
        description="是否仅允许积分购买（受全局积分开关约束）",
    )
    stock: int = Field(default=1, ge=1, le=999, title="库存数量", description="库存 1~999")
    status: str = Field(
        default="off_shelf",
        pattern="^(on_sale|off_shelf|sold_out)$",
        title="商品状态",
        description="on_sale 上架，off_shelf 下架，sold_out 售罄",
    )
    sort: int = Field(default=0, ge=0, title="排序值")
    remark: str | None = Field(default=None, title="备注")

    @model_validator(mode="after")
    def set_default_current_price(self) -> "MallProductCreate":
        if self.current_price is None:
            self.current_price = max(1, self.original_price // 2)
        return self

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str]) -> list[str]:
        if len(v) > 9:
            raise ValueError("商品图片最多 9 张")
        return v


class MallProductUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, max_length=128, title="商品标题")
    description: str | None = Field(default=None, title="商品描述")
    images: list[str] | None = Field(default=None, title="商品图片列表", description="最多 9 张")
    cover_image: str | None = Field(
        default=None, alias="coverImage",
        validation_alias=AliasChoices("coverImage", "cover_image"),
        max_length=512,
    )
    cover_video: str | None = Field(
        default=None, alias="coverVideo",
        validation_alias=AliasChoices("coverVideo", "cover_video"),
        max_length=512,
    )
    original_price: int | None = Field(
        default=None, alias="originalPrice",
        validation_alias=AliasChoices("originalPrice", "original_price"),
        gt=0,
    )
    current_price: int | None = Field(
        default=None, alias="currentPrice",
        validation_alias=AliasChoices("currentPrice", "current_price"),
        gt=0,
    )
    points_cost: int | None = Field(
        default=None, alias="pointsCost",
        validation_alias=AliasChoices("pointsCost", "points_cost"),
        ge=0,
    )
    points_only: bool | None = Field(
        default=None, alias="pointsOnly",
        validation_alias=AliasChoices("pointsOnly", "points_only"),
    )
    stock: int | None = Field(default=None, ge=1, le=999)
    status: str | None = Field(
        default=None,
        pattern="^(on_sale|off_shelf|sold_out)$",
    )
    sort: int | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None)

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 9:
            raise ValueError("商品图片最多 9 张")
        return v


class MallProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    productId: str = Field(title="商品ID")
    title: str = Field(title="商品标题")
    description: str | None = Field(default=None, title="商品描述")
    images: list[str] = Field(default_factory=list, title="商品图片列表")
    coverImage: str | None = Field(default=None, title="封面图")
    coverVideo: str | None = Field(default=None, title="封面视频")
    originalPrice: int = Field(title="原价（分）")
    currentPrice: int = Field(title="现价（分）")
    pointsCost: int = Field(title="积分兑换价")
    pointsOnly: bool = Field(title="仅积分购买")
    stock: int = Field(title="库存")
    soldCount: int = Field(title="累计销量")
    status: str = Field(title="商品状态")
    sort: int = Field(title="排序值")
    remark: str | None = Field(default=None)
    createTime: datetime = Field(title="创建时间")
    updateTime: datetime = Field(title="更新时间")


class MallProductListResponse(BaseModel):
    items: list[MallProductOut]
    total: int


# ---------------------------------------------------------------------------
# 订单
# ---------------------------------------------------------------------------

ORDER_STATUS_LABELS = {
    "pending_pay": "待支付",
    "paid": "已支付",
    "shipped": "已发货",
    "completed": "已完成",
    "cancelled": "已取消",
}


class MallOrderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_id: str = Field(
        alias="productId",
        validation_alias=AliasChoices("productId", "product_id"),
        min_length=1, max_length=64,
        title="商品ID",
    )
    quantity: int = Field(default=1, ge=1, le=999, title="购买数量")
    pay_type: str = Field(
        alias="payType",
        validation_alias=AliasChoices("payType", "pay_type"),
        min_length=1, max_length=32,
        title="支付类型",
        description="支付方式 type 字段値，如 wechat/alipay/points",
    )
    user_remark: str | None = Field(
        default=None,
        alias="userRemark",
        validation_alias=AliasChoices("userRemark", "user_remark", "remark", "note"),
        max_length=256,
        title="下单留言",
        description="用户给卖家的留言，可为空",
    )
    receiver_name: str | None = Field(
        default=None,
        alias="receiverName",
        validation_alias=AliasChoices("receiverName", "receiver_name"),
        max_length=64,
        title="收件人姓名",
        description="实体商品发货需要填写",
    )
    receiver_phone: str | None = Field(
        default=None,
        alias="receiverPhone",
        validation_alias=AliasChoices("receiverPhone", "receiver_phone"),
        max_length=32,
        title="收件人手机号",
    )
    receiver_address: str | None = Field(
        default=None,
        alias="receiverAddress",
        validation_alias=AliasChoices("receiverAddress", "receiver_address", "address"),
        max_length=512,
        title="收件地址",
        description="省/市/区 + 详细地址",
    )


class MallOrderPayRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pay_type: str = Field(
        alias="payType",
        validation_alias=AliasChoices("payType", "pay_type"),
        min_length=1, max_length=32,
        title="支付类型",
    )


class MallOrderStatusUpdate(BaseModel):
    """PC 端修改订单状态请求体。"""
    status: str = Field(
        pattern="^(paid|shipped|completed|cancelled)$",
        title="目标状态",
        description="paid 已支付，shipped 已发货，completed 已完成，cancelled 已取消",
    )
    cancel_reason: str | None = Field(
        default=None,
        alias="cancelReason",
        validation_alias=AliasChoices("cancelReason", "cancel_reason"),
        max_length=256,
        title="取消原因",
        description="status=cancelled 时可传",
    )
    remark: str | None = Field(default=None, title="备注")


class MallOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orderId: str
    userId: str
    productId: str
    productTitle: str
    productImage: str | None = None
    quantity: int
    unitPrice: int = Field(title="成交单价（分）")
    totalPrice: int = Field(title="总价（分）")
    pointsUsed: int = Field(title="使用积分数")
    payType: str | None = None
    payTypeValue: str | None = None
    status: str
    statusLabel: str = Field(title="状态中文名")
    paidAt: str | None = None
    shippedAt: str | None = None
    completedAt: str | None = None
    cancelledAt: str | None = None
    cancelReason: str | None = None
    remark: str | None = None
    # 扩展字段
    expireAt: str | None = Field(default=None, title="超时时间", description="pending_pay 状态的订单超时时间，ISO 格式")
    userRemark: str | None = Field(default=None, title="用户留言")
    receiverName: str | None = Field(default=None, title="收件人")
    receiverPhone: str | None = Field(default=None, title="收件手机号")
    receiverAddress: str | None = Field(default=None, title="收件地址")
    createTime: datetime
    updateTime: datetime


class MallOrderListResponse(BaseModel):
    items: list[MallOrderOut]
    total: int


# ---------------------------------------------------------------------------
# 支付方式
# ---------------------------------------------------------------------------

class MallPaymentMethodCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=64, title="支付方式名称")
    logo: str | None = Field(default=None, max_length=512, title="Logo URL")
    type: str = Field(min_length=1, max_length=64, title="支付类型标识", description="唯一标识，前端传此值，如 wechat/alipay")
    type_value: str | None = Field(
        default=None,
        alias="typeValue",
        validation_alias=AliasChoices("typeValue", "type_value"),
        max_length=256,
        title="附加参数",
        description="商户号/AppID 等",
    )
    status: str = Field(
        default="enabled",
        pattern="^(enabled|disabled)$",
        title="状态",
    )
    sort: int = Field(default=0, ge=0, title="排序值")
    remark: str | None = Field(default=None, title="备注")


class MallPaymentMethodUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=64, title="支付方式名称")
    logo: str | None = Field(default=None, max_length=512, title="Logo URL")
    type_value: str | None = Field(
        default=None, alias="typeValue",
        validation_alias=AliasChoices("typeValue", "type_value"),
        max_length=256,
    )
    status: str | None = Field(default=None, pattern="^(enabled|disabled)$")
    sort: int | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None)


class MallPaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    methodId: str
    name: str
    logo: str | None = None
    type: str
    typeValue: str | None = None
    status: str
    sort: int
    remark: str | None = None
    createTime: datetime
    updateTime: datetime
