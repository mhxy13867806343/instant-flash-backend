"""用户足迹表。

用于存储用户的足迹记录，包含坐标（经纬度）、位置名称、标题、描述。
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserFootprint(TimestampMixin, Base):
    """用户足迹表。"""

    __tablename__ = "user_footprints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    footprint_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
