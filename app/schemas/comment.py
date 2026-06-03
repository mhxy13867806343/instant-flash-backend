from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(min_length=1, title="评论内容", description="评论或回复的文字内容")
    parentId: str | None = Field(
        default=None,
        validation_alias=AliasChoices("parentId", "parent_id", "replyToCommentId", "replyCommentId", "commentId"),
        max_length=64,
        title="父评论 ID",
        description="回复评论时传父评论 commentId，兼容 replyToCommentId/replyCommentId/commentId",
    )
    replyToUserId: str | None = Field(
        default=None,
        validation_alias=AliasChoices("replyToUserId", "reply_to_user_id", "toUserId", "targetUserId"),
        max_length=64,
        title="被回复用户 ID",
        description="回复某个用户时的业务用户 ID",
    )


class CommentOut(BaseModel):
    commentId: str = Field(title="评论 ID", description="业务评论 ID")
    postId: str = Field(title="内容 ID", description="所属内容 ID")
    userId: str = Field(title="评论人用户 ID", description="评论人的业务用户 ID")
    nickname: str | None = Field(default=None, title="评论人昵称", description="评论人的展示昵称")
    avatar: str | None = Field(default=None, title="评论人头像", description="评论人的头像 URL")
    content: str = Field(title="评论内容", description="评论文字")
    parentId: str | None = Field(default=None, title="父评论 ID", description="父级评论 ID")
    replyToUserId: str | None = Field(default=None, title="被回复用户 ID", description="被回复人的业务用户 ID")
    replyToNickname: str | None = Field(default=None, title="被回复人昵称", description="被回复人的展示昵称")
    children: list["CommentOut"] = Field(default_factory=list, title="下级回复", description="当前评论下的回复列表")
    replies: list["CommentOut"] = Field(default_factory=list, title="下级回复兼容字段", description="兼容前端读取的 replies 字段，值同 children")
    replyCount: int = Field(default=0, title="回复数量", description="当前评论下的直接回复数量")
    createdAt: datetime = Field(title="创建时间", description="评论创建时间")
    updatedAt: datetime = Field(title="更新时间", description="评论更新时间")
