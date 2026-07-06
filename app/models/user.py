from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    openid: Mapped[str | None] = mapped_column(String(128), unique=True)
    unionid: Mapped[str | None] = mapped_column(String(128), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    new_phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(String(16))
    bio: Mapped[str | None] = mapped_column(Text)
    client_type: Mapped[str | None] = mapped_column(String(32), index=True)
    client_subtype: Mapped[str | None] = mapped_column(String(64))
    province: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(64))
    district: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    third_party_bindings = relationship("UserThirdPartyBinding", back_populates="user", cascade="all, delete-orphan")


class UserThirdPartyBinding(TimestampMixin, Base):
    """用户第三方账号绑定表。"""

    __tablename__ = "user_third_party_bindings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    binding_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # qq / wechat / alipay / feishu 等
    openid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    user = relationship("User", back_populates="third_party_bindings")

    __table_args__ = (
        UniqueConstraint("platform", "openid", name="uq_user_third_party_platform_openid"),
        UniqueConstraint("user_id", "platform", name="uq_user_third_party_user_platform"),
    )
