from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PointRecord(TimestampMixin, Base):
    __tablename__ = "point_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", onupdate="CASCADE"), index=True, nullable=False
    )
    type: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="earn", nullable=False)
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # 积分有效期，NULL 表示永不过期
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
