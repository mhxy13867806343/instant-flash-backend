from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    content: str = Field(min_length=1, title="内容正文", description="用户发布的文字内容")
    images: list[Any] = Field(default_factory=list, title="图片列表", description="内容附带的图片 URL 或图片对象列表")
    videos: list[Any] = Field(default_factory=list, title="视频列表", description="内容附带的视频 URL 或视频对象列表")
    media: list[Any] = Field(default_factory=list, title="媒体列表", description="内容附带的图片/视频统一媒体列表")
    topics: list[Any] = Field(default_factory=list, title="关联话题", description="发布内容关联的话题列表，支持多个")
    location: str | None = Field(default=None, max_length=128, title="发布地点", description="内容发布地点名称，例如 杭州·西湖")
    province: str | None = Field(default=None, max_length=64, title="省份", description="内容发布省份")
    city: str | None = Field(default=None, max_length=64, title="城市", description="内容发布城市")
    district: str | None = Field(default=None, max_length=64, title="区县", description="内容发布区县")
    visibility: Literal["public", "friends", "private"] = Field(
        default="public",
        title="可见范围",
        description="public 公开，friends 仅好友可见，private 仅自己可见",
    )
    status: Literal["online", "published", "draft"] = Field(
        default="online",
        title="发布状态",
        description="online/published 为发布动态，draft 为保存草稿",
    )


class PostUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, title="内容正文", description="更新后的文字内容")
    images: list[Any] | None = Field(default=None, title="图片列表", description="更新后的图片列表")
    videos: list[Any] | None = Field(default=None, title="视频列表", description="更新后的视频列表")
    media: list[Any] | None = Field(default=None, title="媒体列表", description="更新后的图片/视频统一媒体列表")
    topics: list[Any] | None = Field(default=None, title="关联话题", description="更新后的关联话题列表，支持多个")
    location: str | None = Field(default=None, max_length=128, title="发布地点", description="更新后的发布地点名称")
    province: str | None = Field(default=None, max_length=64, title="省份", description="更新后的省份")
    city: str | None = Field(default=None, max_length=64, title="城市", description="更新后的城市")
    district: str | None = Field(default=None, max_length=64, title="区县", description="更新后的区县")
    visibility: Literal["public", "friends", "private"] | None = Field(
        default=None,
        title="可见范围",
        description="public 公开，friends 仅好友可见，private 仅自己可见",
    )
    status: Literal["online", "published", "draft", "offline"] | None = Field(
        default=None,
        title="内容状态",
        description="online/published 为发布，draft 为草稿，offline 为下架",
    )


class PostOut(BaseModel):
    postId: str = Field(title="内容 ID", description="业务内容 ID")
    userId: str = Field(title="发布者用户 ID", description="发布者业务用户 ID")
    nickname: str | None = Field(default=None, title="发布者昵称", description="发布者展示昵称")
    avatar: str | None = Field(default=None, title="发布者头像", description="发布者头像 URL")
    content: str = Field(title="内容正文", description="内容文字")
    images: list[Any] = Field(title="图片列表", description="内容图片列表")
    videos: list[Any] = Field(default_factory=list, title="视频列表", description="内容视频列表")
    media: list[Any] = Field(default_factory=list, title="媒体列表", description="内容图片/视频统一媒体列表")
    topics: list[Any] = Field(default_factory=list, title="关联话题", description="内容关联的话题列表")
    location: str | None = Field(default=None, title="发布地点", description="内容发布地点名称")
    province: str | None = Field(default=None, title="省份", description="内容发布省份")
    city: str | None = Field(default=None, title="城市", description="内容发布城市")
    district: str | None = Field(default=None, title="区县", description="内容发布区县")
    visibility: str = Field(title="可见范围", description="public 公开，friends 仅好友可见，private 仅自己可见")
    likeCount: int = Field(title="点赞数", description="当前内容点赞数量")
    commentCount: int = Field(title="评论数", description="当前内容评论数量")
    shareCount: int = Field(title="分享数", description="当前内容分享数量")
    status: str = Field(title="内容状态", description="online 为上架，offline 为下架")
    isLiked: bool = Field(default=False, title="是否已点赞", description="当前登录用户是否已点赞")
    isOwner: bool = Field(default=False, title="是否本人发布", description="当前登录用户是否为发布者")
    canEdit: bool = Field(default=False, title="是否可编辑", description="当前登录用户是否可以编辑")
    canDelete: bool = Field(default=False, title="是否可删除", description="当前登录用户是否可以删除")
    createdAt: datetime = Field(title="创建时间", description="内容发布时间")
    updatedAt: datetime = Field(title="更新时间", description="内容最近更新时间")


class PostListResponse(BaseModel):
    items: list[PostOut] = Field(title="内容列表", description="当前页内容数据")
    total: int = Field(title="总数", description="符合条件的内容总数")
    limit: int = Field(title="每页数量", description="本次返回数量上限")
    offset: int = Field(title="偏移量", description="分页偏移量")


class LikeResponse(BaseModel):
    postId: str = Field(title="内容 ID", description="被点赞或取消点赞的内容 ID")
    isLiked: bool = Field(title="是否已点赞", description="操作后的点赞状态")
    likeCount: int = Field(title="点赞数", description="操作后的点赞总数")
