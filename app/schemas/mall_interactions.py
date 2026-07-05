from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 物流轨迹
# ---------------------------------------------------------------------------

class LogisticsStepCreate(BaseModel):
    stepTime: str = Field(
        ...,
        description="轨迹记录时间，格式如 2026-07-06T12:00:00Z",
    )
    content: str = Field(..., max_length=256, description="物流轨迹节点描述内容")


class LogisticsStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    logisticsId: str
    orderId: str
    stepTime: str
    content: str
    createTime: datetime


# ---------------------------------------------------------------------------
# 多客服配置
# ---------------------------------------------------------------------------

class CustomerServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="客服姓名/昵称")
    avatar: str | None = Field(default=None, max_length=512, description="客服头像 URL")
    status: str = Field(default="active", pattern="^(active|inactive)$")
    sort: int = Field(default=0, ge=0)


class CustomerServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    avatar: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    sort: int | None = Field(default=None, ge=0)


class CustomerServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    csId: str
    name: str
    avatar: str | None = None
    status: str
    sort: int
    createTime: datetime


# ---------------------------------------------------------------------------
# 商品还价
# ---------------------------------------------------------------------------

class ProductBargainCreate(BaseModel):
    productId: str = Field(..., description="关联还价的商品 ID")
    bargainPrice: int = Field(..., gt=0, description="出价（分）")


class ProductBargainAudit(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$", description="审核结果：approved 同意，rejected 拒绝")


class ProductBargainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bargainId: str
    userId: str
    productId: str
    originalPrice: int
    bargainPrice: int
    status: str
    createTime: datetime


# ---------------------------------------------------------------------------
# 客服会话与聊天消息
# ---------------------------------------------------------------------------

class ChatSessionInit(BaseModel):
    csId: str = Field(..., description="目标客服 csId")
    productId: str | None = Field(default=None, description="可关联并带入对话框的商品 ID")


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sessionId: str
    userId: str
    csId: str
    productId: str | None = None
    isActive: bool
    createTime: datetime
    updateTime: datetime


class ChatMessageCreate(BaseModel):
    sessionId: str = Field(..., description="会话 ID")
    content: str = Field(..., min_length=1, description="消息正文内容")
    msgType: str = Field(default="text", pattern="^(text|bargain|image)$")
    bargainId: str | None = Field(default=None, description="还价卡片绑定 bargainId")


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    messageId: str
    sessionId: str
    senderType: str
    senderId: str
    content: str
    msgType: str
    bargainId: str | None = None
    createTime: datetime
