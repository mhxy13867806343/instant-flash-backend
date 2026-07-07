"""电影票务系统 Pydantic 数据模式（Schemas）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict, AliasGenerator
from pydantic.alias_generators import to_camel, to_snake


# ---------------------------------------------------------------------------
# 电影 (Movie)
# ---------------------------------------------------------------------------
class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128, description="电影名称")
    director: str = Field(..., min_length=1, max_length=64, description="导演")
    actors: str | None = Field(default=None, description="演员列表")
    duration: int = Field(..., gt=0, description="时长（分钟）")
    movieType: str = Field(..., alias="movieType", serialization_alias="movieType", min_length=1, max_length=64, description="电影类型")
    releaseDate: str = Field(..., alias="releaseDate", serialization_alias="releaseDate", min_length=1, max_length=32, description="上映时间")
    rating: float = Field(default=0.0, ge=0.0, le=10.0, description="评分")
    introduction: str | None = Field(default=None, description="简介说明")
    poster: str | None = Field(default=None, max_length=512, description="海报 URL")
    language: str = Field(..., min_length=1, max_length=32, description="语言")
    status: str = Field(default="showing", pattern="^(showing|upcoming)$", description="显示状态")


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    director: str | None = Field(default=None, min_length=1, max_length=64)
    actors: str | None = Field(default=None)
    duration: int | None = Field(default=None, gt=0)
    movieType: str | None = Field(default=None, alias="movieType", max_length=64)
    releaseDate: str | None = Field(default=None, alias="releaseDate", max_length=32)
    rating: float | None = Field(default=None, ge=0.0, le=10.0)
    introduction: str | None = Field(default=None)
    poster: str | None = Field(default=None, max_length=512)
    language: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None, pattern="^(showing|upcoming)$")


class MovieOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    id: int
    movieId: str
    title: str
    director: str
    actors: str | None = None
    duration: int
    movieType: str
    releaseDate: str
    rating: float
    introduction: str | None = None
    poster: str | None = None
    language: str
    status: str
    createTime: datetime


# ---------------------------------------------------------------------------
# 影院 (Cinema)
# ---------------------------------------------------------------------------
class CinemaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="影院名称")
    logo: str | None = Field(default=None, max_length=512, description="Logo URL")
    address: str = Field(..., min_length=1, max_length=256, description="地址")
    city: str = Field(..., min_length=1, max_length=64, description="城市")
    longitude: float | None = Field(default=None)
    latitude: float | None = Field(default=None)
    phone: str | None = Field(default=None, max_length=32)


class CinemaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    logo: str | None = Field(default=None, max_length=512)
    address: str | None = Field(default=None, min_length=1, max_length=256)
    city: str | None = Field(default=None, min_length=1, max_length=64)
    longitude: float | None = Field(default=None)
    latitude: float | None = Field(default=None)
    phone: str | None = Field(default=None, max_length=32)


class CinemaOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    id: int
    cinemaId: str
    name: str
    logo: str | None = None
    address: str
    city: str
    longitude: float | None = None
    latitude: float | None = None
    phone: str | None = None
    createTime: datetime


# ---------------------------------------------------------------------------
# 影厅 (MovieHall)
# ---------------------------------------------------------------------------
class MovieHallCreate(BaseModel):
    cinemaId: str = Field(..., alias="cinemaId", description="影院 ID")
    name: str = Field(..., min_length=1, max_length=64, description="放映厅名称")
    hallType: str = Field(default="普通", alias="hallType", description="影厅类型")
    # {"rows": 8, "cols": 10, "broken": ["1-1"]}
    seatLayout: dict[str, Any] = Field(default_factory=dict, alias="seatLayout", description="座位排布")


class MovieHallUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    hallType: str | None = Field(default=None, alias="hallType")
    seatLayout: dict[str, Any] | None = Field(default=None, alias="seatLayout")


class MovieHallOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    id: int
    hallId: str
    cinemaId: str
    name: str
    hallType: str
    seatLayout: dict[str, Any]
    createTime: datetime


# ---------------------------------------------------------------------------
# 放映场次 (MovieShowtime)
# ---------------------------------------------------------------------------
class MovieShowtimeCreate(BaseModel):
    movieId: str = Field(..., alias="movieId")
    cinemaId: str = Field(..., alias="cinemaId")
    hallId: str = Field(..., alias="hallId")
    startTime: datetime = Field(..., alias="startTime", description="开始放映时间")
    endTime: datetime = Field(..., alias="endTime", description="散场时间")
    price: int = Field(..., gt=0, description="售价（分）")
    originalPrice: int = Field(..., gt=0, alias="originalPrice", description="原价（分）")
    languageVersion: str = Field(..., alias="languageVersion", description="放映版本，如国语3D")


class MovieShowtimeUpdate(BaseModel):
    startTime: datetime | None = Field(default=None, alias="startTime")
    endTime: datetime | None = Field(default=None, alias="endTime")
    price: int | None = Field(default=None, gt=0)
    originalPrice: int | None = Field(default=None, gt=0, alias="originalPrice")
    languageVersion: str | None = Field(default=None, alias="languageVersion")


class MovieShowtimeOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    id: int
    showtimeId: str
    movieId: str
    cinemaId: str
    hallId: str
    startTime: datetime
    endTime: datetime
    price: int
    originalPrice: int
    languageVersion: str
    createTime: datetime


# ---------------------------------------------------------------------------
# 实时选座图 (SeatLayoutStateOut)
# ---------------------------------------------------------------------------
class SeatInfo(BaseModel):
    row: int
    col: int
    name: str  # e.g., "3排4座"


class SeatLayoutStateOut(BaseModel):
    rows: int = Field(..., description="总排数")
    cols: int = Field(..., description="每排总列数")
    brokenSeats: list[str] = Field(default_factory=list, description="不可选座位，格式为 ['1-1', '1-2']")
    occupiedSeats: list[str] = Field(default_factory=list, description="已被售出或锁定占用的座位，格式为 ['3-4', '3-5']")


# ---------------------------------------------------------------------------
# 电影票订单 (MovieTicketOrder)
# ---------------------------------------------------------------------------
class MovieOrderCreate(BaseModel):
    showtimeId: str = Field(..., alias="showtimeId", description="场次 ID")
    seats: list[SeatInfo] = Field(..., min_items=1, max_items=6, description="选中的座位列表，单次限购1-6张")


class MovieOrderOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=AliasGenerator(
            validation_alias=to_snake,
        ),
    )

    id: int
    orderId: str
    userId: str
    showtimeId: str
    seats: list[SeatInfo]
    pricePaid: int
    payStatus: str
    paidAt: datetime | None = None
    ticketCode: str | None = None
    expireTime: datetime
    createTime: datetime
