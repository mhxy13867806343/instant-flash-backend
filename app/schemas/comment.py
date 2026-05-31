from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, title="评论内容", description="评论或回复的文字内容")
    parentId: str | None = Field(default=None, max_length=64, title="父评论 ID", description="回复评论时传父评论 comment_id")
    replyToUserId: str | None = Field(default=None, max_length=64, title="被回复用户 ID", description="回复某个用户时的业务用户 ID")


class CommentOut(BaseModel):
    commentId: str = Field(title="评论 ID", description="业务评论 ID")
    postId: str = Field(title="内容 ID", description="所属内容 ID")
    userId: str = Field(title="评论人用户 ID", description="评论人的业务用户 ID")
    content: str = Field(title="评论内容", description="评论文字")
    parentId: str | None = Field(default=None, title="父评论 ID", description="父级评论 ID")
    replyToUserId: str | None = Field(default=None, title="被回复用户 ID", description="被回复人的业务用户 ID")
    createdAt: datetime = Field(title="创建时间", description="评论创建时间")
    updatedAt: datetime = Field(title="更新时间", description="评论更新时间")
