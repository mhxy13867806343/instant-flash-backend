from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    messageId: str = Field(title="消息 ID", description="业务消息 ID")
    userId: str = Field(title="接收人用户 ID", description="消息接收人的业务用户 ID")
    senderId: str | None = Field(default=None, title="发送人用户 ID", description="触发消息的用户 ID")
    type: str = Field(title="消息类型", description="消息类型，例如 like/comment/system")
    title: str | None = Field(default=None, title="消息标题", description="消息标题")
    content: str | None = Field(default=None, title="消息内容", description="消息正文")
    postId: str | None = Field(default=None, title="关联内容 ID", description="消息关联的内容 ID")
    commentId: str | None = Field(default=None, title="关联评论 ID", description="消息关联的评论 ID")
    isRead: bool = Field(title="是否已读", description="消息是否已读")
    createdAt: datetime = Field(title="创建时间", description="消息创建时间")
    updatedAt: datetime = Field(title="更新时间", description="消息更新时间")
