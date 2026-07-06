from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AiModel(TimestampMixin, Base):
    """AI 模型配置表（后台管理）。"""

    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # text / video / image / multimodal
    icon: Mapped[str | None] = mapped_column(String(512))
    cover: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    points_per_use: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    channel: Mapped[str] = mapped_column(
        String(32), default="standard", nullable=False
    )  # standard / fast / exclusive
    features: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )  # e.g. ["去水印", "高清", "快速通道"]
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="enabled", nullable=False
    )  # enabled / disabled


class AiModelPlan(TimestampMixin, Base):
    """充值套餐配置表（按天/月/年）。"""

    __tablename__ = "ai_model_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. "基础会员"
    tier: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # basic / standard / premium / super
    period_type: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # day / month / year
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    original_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 原价（分）
    current_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 现价（分）
    points_monthly: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 每月赠送模型积分
    points_conversion_rate: Mapped[str | None] = mapped_column(
        String(64)
    )  # e.g. "¥10=110积分"
    features: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )  # 套餐权益列表
    badge: Mapped[str | None] = mapped_column(String(64))  # e.g. "低至7折"
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)


class AiModelPromotion(TimestampMixin, Base):
    """促销活动配置（春节优惠等）。"""

    __tablename__ = "ai_model_promotions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    promotion_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    discount_rate: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False
    )  # 折扣百分比，100=无折扣，70=7折
    extra_points_pct: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 额外赠送积分百分比
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applicable_plans: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )  # 适用套餐 plan_id 列表，空=全部
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)


class AiModelUsageRecord(TimestampMixin, Base):
    """用户模型使用记录（历史记录）。"""

    __tablename__ = "ai_model_usage_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", onupdate="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)  # 冗余快照
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # text/video/image/multimodal
    prompt: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)  # 生成结果或链接
    result_type: Mapped[str] = mapped_column(
        String(32), default="text", nullable=False
    )  # text / image / video
    points_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="completed", nullable=False
    )  # pending / completed / failed
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 发现与社交互动扩展字段
    title: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(32), default="private", nullable=False)  # public / private
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AiModelPointGrant(TimestampMixin, Base):
    """每日赠送模型积分记录。"""

    __tablename__ = "ai_model_point_grants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    grant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", onupdate="CASCADE"), index=True, nullable=False
    )
    grant_date: Mapped[datetime] = mapped_column(Date, index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )  # active / expired


class AiModelSubscription(TimestampMixin, Base):
    """用户订阅 / 充值订单。"""

    __tablename__ = "ai_model_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", onupdate="CASCADE"), index=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    pay_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 实付（分）
    original_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 原价（分）
    discount_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 优惠（分）
    promotion_id: Mapped[str | None] = mapped_column(String(64), index=True)
    pay_method: Mapped[str | None] = mapped_column(String(32))  # wechat / alipay
    pay_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending / paid / failed / refunded
    points_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AiModelUsageRecordLike(TimestampMixin, Base):
    """AI 作品点赞记录。"""

    __tablename__ = "ai_model_usage_record_likes"
    __table_args__ = (UniqueConstraint("record_id", "user_id", name="uq_aim_record_like"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_model_usage_records.record_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )


class AiModelUsageRecordFavorite(TimestampMixin, Base):
    """AI 作品收藏记录。"""

    __tablename__ = "ai_model_usage_record_favorites"
    __table_args__ = (UniqueConstraint("record_id", "user_id", name="uq_aim_record_fav"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_model_usage_records.record_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )


class AiModelUsageRecordComment(TimestampMixin, Base):
    """AI 作品评论记录。"""

    __tablename__ = "ai_model_usage_record_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    record_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_model_usage_records.record_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

