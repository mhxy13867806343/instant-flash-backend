from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AdminTag(TimestampMixin, Base):
    __tablename__ = "admin_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tag_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(32))
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)


class AdminRegion(TimestampMixin, Base):
    __tablename__ = "admin_regions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    region_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)


class AdminDictionary(TimestampMixin, Base):
    __tablename__ = "admin_dictionaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dict_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)


class AdminSystemMessage(TimestampMixin, Base):
    __tablename__ = "admin_system_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="notice", nullable=False)
    target: Mapped[str] = mapped_column(String(32), default="all", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
