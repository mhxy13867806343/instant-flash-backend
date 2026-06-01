from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
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
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
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


class AdminAnnouncement(TimestampMixin, Base):
    __tablename__ = "admin_announcements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    announcement_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="info", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(512))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_time: Mapped[str | None] = mapped_column(String(32))
    end_time: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class AdminVersion(TimestampMixin, Base):
    __tablename__ = "admin_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    build: Mapped[str] = mapped_column(String(32), nullable=False)
    force_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="released", nullable=False)
    beta_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes_type: Mapped[str] = mapped_column(String(16), default="text", nullable=False)
    download_url: Mapped[str | None] = mapped_column(String(512))
    release_time: Mapped[str | None] = mapped_column(String(32))


class AdminAccount(TimestampMixin, Base):
    __tablename__ = "admin_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    email: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    remark: Mapped[str | None] = mapped_column(Text)
    password: Mapped[str] = mapped_column(String(128), default="123456", nullable=False)
    last_login: Mapped[str | None] = mapped_column(String(32))


class AdminMenu(TimestampMixin, Base):
    __tablename__ = "admin_menus"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    menu_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    component: Mapped[str | None] = mapped_column(String(128))
    redirect: Mapped[str | None] = mapped_column(String(128))
    icon: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32), default="menu", nullable=False)
    permission: Mapped[str | None] = mapped_column(String(64), index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    keep_alive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    affix: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external_link: Mapped[str | None] = mapped_column(String(512))
    remark: Mapped[str | None] = mapped_column(Text)
