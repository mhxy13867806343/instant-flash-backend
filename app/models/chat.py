from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class GlobalChatSession(TimestampMixin, Base):
    """全局私聊与客服对话会话表。"""

    __tablename__ = "global_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_one_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_two_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GlobalChatMessage(TimestampMixin, Base):
    """全局私聊与客服聊天消息记录表（增强版）。"""

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
    )  # text/image/video/voice/file/product/bargain/forward/location
    product_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    bargain_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 媒体字段
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 图片/视频/语音/文件 URL
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 视频缩略图
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 文件大小(字节)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 音视频时长(秒)
    # 消息操作
    reply_to_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 回复的消息ID
    forward_from_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 转发来源消息ID
    is_recalled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否已撤回


class ChatGroup(TimestampMixin, Base):
    """群聊表。"""

    __tablename__ = "chat_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    announcement: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_members: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 全员禁言
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)


class ChatGroupMember(TimestampMixin, Base):
    """群成员表。"""

    __tablename__ = "chat_group_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_groups.group_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default="member", nullable=False
    )  # owner 群主 / admin 管理员 / member 普通成员
    nickname_in_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_chat_group_members_group_user"),
    )


class ChatGroupMessage(TimestampMixin, Base):
    """群聊消息表。"""

    __tablename__ = "chat_group_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_groups.group_id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(
        String(32), default="text", nullable=False
    )  # text/image/video/voice/file/product/forward/location/system
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_to_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    forward_from_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_recalled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    at_user_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # @的用户ID,逗号分隔


class ChatMessageFavorite(TimestampMixin, Base):
    """消息收藏表。"""

    __tablename__ = "chat_message_favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    favorite_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # private / group
    source_message_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="text", server_default="text", nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

