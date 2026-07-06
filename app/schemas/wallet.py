from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# 支付方式标签映射
PAY_METHOD_LABELS = {
    "alipay": "支付宝",
    "wechat": "微信支付",
    "bank_card": "银行卡",
    "apple_pay": "Apple Pay",
    "other": "其他",
}


class UserWalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    walletId: str
    userId: str
    balance: int = Field(title="当前余额（分）")
    frozenBalance: int = Field(title="冻结余额（分）")
    status: str = Field(title="状态：normal/frozen")
    createTime: datetime
    updateTime: datetime


class WalletRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recordId: str
    userId: str
    type: str = Field(title="类型：recharge/consume/refund/withdraw/adjust")
    typeLabel: str = Field(title="类型展示标签")
    direction: str = Field(title="方向：earn/consume")
    changeAmount: int = Field(title="变动金额（分）")
    balanceAfter: int = Field(title="变动后余额（分）")
    title: str
    remark: str | None = None
    sourceId: str | None = None
    payMethod: str | None = Field(default=None, title="支付方式")
    payMethodLabel: str | None = Field(default=None, title="支付方式展示标签")
    createTime: datetime


class WalletRecordListResponse(BaseModel):
    items: list[WalletRecordOut]
    total: int


class WalletRechargeRequest(BaseModel):
    amount: int = Field(
        gt=0,
        le=99999900,
        title="充值金额（分）",
        description="充值金额，单位：分。最低 1 分 (0.01元)，最高 99999900 分 (999999.00元)",
    )
    payMethod: str = Field(
        default="alipay",
        description="支付方式：alipay 支付宝 / wechat 微信支付 / bank_card 银行卡 / apple_pay / other",
    )
    remark: str | None = Field(default=None, max_length=256, title="充值备注")

    @field_validator("amount")
    @classmethod
    def validate_amount_range(cls, v: int) -> int:
        if v < 1:
            raise ValueError("充值金额最低 0.01 元（1 分）")
        if v > 99999900:
            raise ValueError("充值金额最高 999999.00 元（99999900 分）")
        return v


class WalletAdjustRequest(BaseModel):
    amount: int = Field(title="变动金额（分）", description="正数增加余额，负数扣减余额，不能为 0")
    remark: str = Field(min_length=1, max_length=256, title="变动备注/原因")

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("变动金额不能为 0")
        return v
