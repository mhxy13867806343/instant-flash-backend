"""用户足迹数据传输模型 (Schemas)。
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, AliasGenerator
from pydantic.alias_generators import to_snake


class FootprintCreate(BaseModel):
    """新建足迹数据。"""

    title: str = Field(..., min_length=1, max_length=128, description="足迹标题")
    description: str | None = Field(default=None, description="足迹描述（可选）")
    latitude: float = Field(..., description="纬度坐标")
    longitude: float = Field(..., description="经度坐标")
    locationName: str | None = Field(default=None, description="位置名称/地址")
    images: list[str] = Field(default_factory=list, description="图片地址列表")


class FootprintUpdate(BaseModel):
    """更新足迹数据。"""

    title: str | None = Field(default=None, min_length=1, max_length=128, description="足迹标题")
    description: str | None = Field(default=None, description="足迹描述")
    latitude: float | None = Field(default=None, description="纬度坐标")
    longitude: float | None = Field(default=None, description="经度坐标")
    locationName: str | None = Field(default=None, description="位置名称/地址")
    images: list[str] | None = Field(default=None, description="图片地址列表")


class FootprintOut(BaseModel):
    """足迹出参数据。"""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    footprintId: str
    userId: str
    title: str
    description: str | None = None
    latitude: float
    longitude: float
    locationName: str | None = None
    images: list[str] = Field(default_factory=list, description="图片地址列表")
    createTime: datetime
