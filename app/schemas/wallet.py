from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


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
    createTime: datetime


class WalletRecordListResponse(BaseModel):
    items: list[WalletRecordOut]
    total: int


class WalletRechargeRequest(BaseModel):
    amount: int = Field(gt=0, title="充值金额（分）", description="充值金额，单位：分，必须大于 0")
    remark: str | None = Field(default=None, max_length=256, title="充值备注")


class WalletAdjustRequest(BaseModel):
    amount: int = Field(title="变动金额（分）", description="正数增加余额，负数扣减余额，不能为 0")
    remark: str = Field(min_length=1, max_length=256, title="变动备注/原因")

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("变动金额不能为 0")
        return v
