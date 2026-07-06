from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersonaCreatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, max_length=128, description="画像标题")
    content: str = Field(..., min_length=1, description="画像正文内容")
    images: list[str] = Field(default_factory=list, description="图片 URL 列表")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    privacy: str = Field(default="public", pattern="^(public|private)$", description="可见性属性：public 公开 / private 私有")
    duration_minutes: int | None = Field(
        default=None,
        alias="durationMinutes",
        description="公开时的失效倒计时时长（分钟），最少 180 分钟，最多 4320 分钟 (3天)",
    )

    @model_validator(mode="after")
    def validate_duration(self) -> PersonaCreatePayload:
        if self.privacy == "public":
            if self.duration_minutes is None:
                raise ValueError("公开画像必须指定有效时长 durationMinutes")
            if not (180 <= self.duration_minutes <= 4320):
                raise ValueError("公开画像失效时间限制：最少 180 分钟，最大 3 天 (4320 分钟)")
        return self


class PersonaUpdatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, max_length=128, description="画像标题")
    content: str | None = Field(default=None, min_length=1, description="画像正文内容")
    images: list[str] | None = Field(default=None, description="图片 URL 列表")
    tags: list[str] | None = Field(default=None, description="标签列表")
    privacy: str | None = Field(default=None, pattern="^(public|private)$", description="可见性属性")
    duration_minutes: int | None = Field(
        default=None,
        alias="durationMinutes",
        description="变更公开画像时的有效时间（分钟），最少 180 分钟，最多 4320 分钟",
    )

    @model_validator(mode="after")
    def validate_duration(self) -> PersonaUpdatePayload:
        if self.privacy == "public" or (self.privacy is None and self.duration_minutes is not None):
            # Check duration limits if becoming public or duration is updated
            if self.duration_minutes is not None and not (180 <= self.duration_minutes <= 4320):
                raise ValueError("公开画像失效时间限制：最少 180 分钟，最大 3 天 (4320 分钟)")
        return self
        return self


class PersonaCommentCreatePayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000, description="评论正文")


class PersonaCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    commentId: str
    personaId: str
    userId: str
    content: str
    createTime: datetime
    nickname: str | None = None
    avatar: str | None = None


class PersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    personaId: str
    userId: str
    title: str | None = None
    content: str
    images: list[str]
    tags: list[str]
    privacy: str
    expireTime: datetime | None = None
    viewCount: int
    createTime: datetime
    nickname: str | None = None
    avatar: str | None = None
    commentCount: int = 0
    favoriteCount: int = 0
    isFavorited: bool | None = None
