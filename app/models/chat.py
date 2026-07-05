from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class GlobalChatSession(TimestampMixin, Base):
    """全局私聊与客服对话会话表。"""

    __tablename__ = "global_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_one_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # 会话参与方 1 (用户ID)
    user_two_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # 会话参与方 2 (用户ID，或客服 cs_id)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # 最后一条消息预览
    last_message_time: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # 最后一条消息时间
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GlobalChatMessage(TimestampMixin, Base):
    """全局私聊与客服聊天消息记录表。"""

    __tablename__ = "global_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("global_chat_sessions.session_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sender_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(
        String(32), default="text", nullable=False
    )  # text / image / product / bargain
    product_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )  # 卡片带入商品 ID
    bargain_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )  # 还价申请 ID
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
