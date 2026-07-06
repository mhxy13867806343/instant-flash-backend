from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 私聊消息增强
# ---------------------------------------------------------------------------

class PrivateMessageCreate(BaseModel):
    sessionId: str = Field(..., description="会话 ID")
    content: str = Field(..., min_length=1, description="消息内容")
    msgType: str = Field(default="text", pattern="^(text|image|video|voice|file|product|bargain|forward|location)$")
    productId: str | None = Field(default=None)
    bargainId: str | None = Field(default=None)
    mediaUrl: str | None = Field(default=None, max_length=512, description="媒体文件 URL")
    thumbnailUrl: str | None = Field(default=None, max_length=512)
    fileName: str | None = Field(default=None, max_length=256)
    fileSize: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0, description="音视频时长(秒)")
    replyToId: str | None = Field(default=None, description="回复的消息 ID")


class PrivateMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    messageId: str
    sessionId: str
    senderId: str
    receiverId: str
    content: str
    msgType: str
    productId: str | None = None
    bargainId: str | None = None
    mediaUrl: str | None = None
    thumbnailUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    duration: int | None = None
    replyToId: str | None = None
    forwardFromId: str | None = None
    isRead: bool
    isRecalled: bool = False
    createTime: datetime


# ---------------------------------------------------------------------------
# 群聊
# ---------------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="群名称")
    avatar: str | None = Field(default=None, max_length=512)
    memberIds: list[str] = Field(default_factory=list, description="初始邀请的成员用户 ID 列表")
    region: str | None = Field(default=None, max_length=128, description="群聊所属地区")


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    avatar: str | None = Field(default=None, max_length=512)
    announcement: str | None = Field(default=None, max_length=1000)
    isMuted: bool | None = Field(default=None, description="全员禁言")
    region: str | None = Field(default=None, max_length=128)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    groupId: str
    name: str
    avatar: str | None = None
    ownerId: str
    announcement: str | None = None
    maxMembers: int
    memberCount: int
    isMuted: bool
    lastMessage: str | None = None
    lastMessageTime: str | None = None
    status: str
    region: str | None = None
    createTime: datetime
    updateTime: datetime


class GroupJoinRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    requestId: str
    groupId: str
    userId: str
    message: str | None = None
    status: str
    createTime: datetime
    nickname: str | None = None
    avatar: str | None = None



class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    userId: str
    role: str
    nicknameInGroup: str | None = None
    isMuted: bool
    nickname: str | None = Field(default=None, title="用户真实昵称")
    avatar: str | None = Field(default=None, title="用户头像")
    createTime: datetime


class GroupInvite(BaseModel):
    userIds: list[str] = Field(..., min_length=1, description="要邀请的用户 ID 列表")


class GroupMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    msgType: str = Field(default="text", pattern="^(text|image|video|voice|file|product|forward|location)$")
    mediaUrl: str | None = Field(default=None, max_length=512)
    thumbnailUrl: str | None = Field(default=None, max_length=512)
    fileName: str | None = Field(default=None, max_length=256)
    fileSize: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0)
    replyToId: str | None = Field(default=None)
    atUserIds: list[str] | None = Field(default=None, description="@的用户ID列表")


class GroupMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    messageId: str
    groupId: str
    senderId: str
    content: str
    msgType: str
    mediaUrl: str | None = None
    thumbnailUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    duration: int | None = None
    replyToId: str | None = None
    forwardFromId: str | None = None
    isRecalled: bool = False
    atUserIds: list[str] | None = None
    senderName: str | None = Field(default=None, title="发送者昵称")
    senderAvatar: str | None = Field(default=None, title="发送者头像")
    createTime: datetime


# ---------------------------------------------------------------------------
# 消息操作
# ---------------------------------------------------------------------------

class MessageForward(BaseModel):
    messageIds: list[str] = Field(..., min_length=1, max_length=20, description="要转发的消息 ID 列表")
    targetType: str = Field(..., pattern="^(private|group)$", description="转发目标类型")
    targetId: str = Field(..., description="目标会话 ID 或群 ID")
    mergeForward: bool = Field(default=False, description="是否合并转发")


class MessageFavoriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    favoriteId: str
    userId: str
    sourceType: str
    sourceMessageId: str
    content: str
    msgType: str
    category: str = "text"
    mediaUrl: str | None = None
    senderId: str
    senderName: str | None = None
    createTime: datetime



class MessageRecall(BaseModel):
    messageType: str = Field(..., pattern="^(private|group)$", description="消息类型：private 私聊 / group 群聊")


class JoinByLinkPayload(BaseModel):
    token: str = Field(..., description="邀请链接的加密 Token")

