"""电影票务系统（仿淘票票）数据库模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Movie(TimestampMixin, Base):
    """电影库表。"""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    movie_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    director: Mapped[str] = mapped_column(String(64), nullable=False)
    actors: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # 时长（分钟）
    movie_type: Mapped[str] = mapped_column(String(64), nullable=False)  # 类型，如"动作/科幻"
    release_date: Mapped[str] = mapped_column(String(32), nullable=False)  # 上映时间 "2023-12-15"
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 海报 URL
    language: Mapped[str] = mapped_column(String(32), nullable=False)  # 语言，如"英语"
    status: Mapped[str] = mapped_column(String(32), default="showing", nullable=False, index=True)  # showing 正在上映 / upcoming 即将上映
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Cinema(TimestampMixin, Base):
    """影院表。"""

    __tablename__ = "cinemas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cinema_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    address: Mapped[str] = mapped_column(String(256), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MovieHall(TimestampMixin, Base):
    """影厅表。"""

    __tablename__ = "movie_halls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hall_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    cinema_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cinemas.cinema_id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # 如"1号厅"
    hall_type: Mapped[str] = mapped_column(String(32), default="普通", nullable=False)  # 如"IMAX", "3D", "巨幕"
    # 座位图设计，JSON 结构，例如: {"rows": 8, "cols": 10, "broken": ["1-1", "1-2"]}
    seat_layout: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MovieShowtime(TimestampMixin, Base):
    """放映场次表。"""

    __tablename__ = "movie_showtimes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    showtime_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    movie_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("movies.movie_id", ondelete="CASCADE"), index=True, nullable=False
    )
    cinema_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cinemas.cinema_id", ondelete="CASCADE"), index=True, nullable=False
    )
    hall_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("movie_halls.hall_id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # 售价（分）
    original_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 原价（分）
    language_version: Mapped[str] = mapped_column(String(64), nullable=False)  # 如"国语 3D"
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MovieTicketOrder(TimestampMixin, Base):
    """电影票订单表。"""

    __tablename__ = "movie_ticket_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    showtime_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("movie_showtimes.showtime_id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 购买的座位，JSON 结构，例如: [{"row": 3, "col": 4, "name": "3排4座"}]
    seats: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)  # 实际总价（分）
    # 状态：pending_pay 待支付 / paid 已支付 / cancelled 已取消
    pay_status: Mapped[str] = mapped_column(String(32), default="pending_pay", nullable=False, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 12 位取票码
    expire_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # 超时失效时间
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
