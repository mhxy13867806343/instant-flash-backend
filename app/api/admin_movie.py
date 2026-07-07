from __future__ import annotations

from typing import Annotated, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.admin import get_admin_subject, fail
from app.api.utils import new_business_id
from app.core.pagination import paginate_with_total
from app.core.response import ok
from app.db.session import get_db
from app.models.movie import Movie, Cinema, MovieHall, MovieShowtime, MovieTicketOrder
from app.schemas.movie import (
    MovieCreate,
    MovieUpdate,
    MovieOut,
    CinemaCreate,
    CinemaUpdate,
    CinemaOut,
    MovieHallCreate,
    MovieHallUpdate,
    MovieHallOut,
    MovieShowtimeCreate,
    MovieShowtimeUpdate,
    MovieShowtimeOut,
)

router = APIRouter(prefix="/api/admin/movies", tags=["电影后台管理"])


# Helper serializers
def _movie_out(m: Movie) -> MovieOut:
    return MovieOut.model_validate(m)


def _cinema_out(c: Cinema) -> CinemaOut:
    return CinemaOut.model_validate(c)


def _hall_out(h: MovieHall) -> MovieHallOut:
    return MovieHallOut.model_validate(h)


def _showtime_out(s: MovieShowtime) -> MovieShowtimeOut:
    return MovieShowtimeOut.model_validate(s)


# ---------------------------------------------------------------------------
# 1. 电影 CRUD (Movies)
# ---------------------------------------------------------------------------
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="新增电影")
def admin_create_movie(
    payload: MovieCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    m = Movie(
        movie_id=new_business_id("mov"),
        title=payload.title,
        director=payload.director,
        actors=payload.actors,
        duration=payload.duration,
        movie_type=payload.movieType,
        release_date=payload.releaseDate,
        rating=payload.rating,
        introduction=payload.introduction,
        poster=payload.poster,
        language=payload.language,
        status=payload.status,
        is_deleted=False,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ok(_movie_out(m), "电影添加成功")


@router.get("", summary="电影列表（带分页与筛选）")
def admin_list_movies(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    query: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(Movie).filter(Movie.is_deleted.is_(False))
    if status_filter:
        q = q.filter(Movie.status == status_filter)
    if query:
        q = q.filter(Movie.title.ilike(f"%{query}%"))
    q = q.order_by(Movie.create_time.desc())
    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_movie_out(item) for item in items],
        "total": total,
    })


@router.put("/{movie_id}", summary="编辑电影")
def admin_update_movie(
    movie_id: Annotated[str, Path(description="电影 ID")],
    payload: MovieUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    m = db.query(Movie).filter(Movie.movie_id == movie_id, Movie.is_deleted.is_(False)).first()
    if not m:
        raise fail(status.HTTP_404_NOT_FOUND, "电影不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        field_map = {
            "movieType": "movie_type",
            "releaseDate": "release_date",
        }
        db_col = field_map.get(k, k)
        setattr(m, db_col, v)

    db.commit()
    db.refresh(m)
    return ok(_movie_out(m), "电影信息已修改")


@router.delete("/{movie_id}", summary="删除电影")
def admin_delete_movie(
    movie_id: Annotated[str, Path(description="电影 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    m = db.query(Movie).filter(Movie.movie_id == movie_id, Movie.is_deleted.is_(False)).first()
    if not m:
        raise fail(status.HTTP_404_NOT_FOUND, "电影不存在")
    m.is_deleted = True
    db.commit()
    return ok(None, "电影已下架/删除")


# ---------------------------------------------------------------------------
# 2. 影院 CRUD (Cinemas)
# ---------------------------------------------------------------------------
@router.post("/cinemas", response_model=dict, status_code=status.HTTP_201_CREATED, summary="新增影院")
def admin_create_cinema(
    payload: CinemaCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    c = Cinema(
        cinema_id=new_business_id("cin"),
        name=payload.name,
        logo=payload.logo,
        address=payload.address,
        city=payload.city,
        longitude=payload.longitude,
        latitude=payload.latitude,
        phone=payload.phone,
        is_deleted=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return ok(_cinema_out(c), "影院创建成功")


@router.get("/cinemas", summary="影院列表")
def admin_list_cinemas(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    city: Annotated[str | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(Cinema).filter(Cinema.is_deleted.is_(False))
    if city:
        q = q.filter(Cinema.city == city)
    if query:
        q = q.filter(Cinema.name.ilike(f"%{query}%"))
    q = q.order_by(Cinema.create_time.desc())
    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_cinema_out(item) for item in items],
        "total": total,
    })


@router.put("/cinemas/{cinema_id}", summary="修改影院")
def admin_update_cinema(
    cinema_id: Annotated[str, Path(description="影院 ID")],
    payload: CinemaUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    c = db.query(Cinema).filter(Cinema.cinema_id == cinema_id, Cinema.is_deleted.is_(False)).first()
    if not c:
        raise fail(status.HTTP_404_NOT_FOUND, "影院不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)

    db.commit()
    db.refresh(c)
    return ok(_cinema_out(c), "影院信息已修改")


@router.delete("/cinemas/{cinema_id}", summary="删除影院")
def admin_delete_cinema(
    cinema_id: Annotated[str, Path(description="影院 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    c = db.query(Cinema).filter(Cinema.cinema_id == cinema_id, Cinema.is_deleted.is_(False)).first()
    if not c:
        raise fail(status.HTTP_404_NOT_FOUND, "影院不存在")
    c.is_deleted = True
    db.commit()
    return ok(None, "影院已删除")


# ---------------------------------------------------------------------------
# 3. 影厅 CRUD (Halls)
# ---------------------------------------------------------------------------
@router.post("/halls", response_model=dict, status_code=status.HTTP_201_CREATED, summary="新增影厅")
def admin_create_hall(
    payload: MovieHallCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    # 检查影院存在性
    c = db.query(Cinema).filter(Cinema.cinema_id == payload.cinemaId, Cinema.is_deleted.is_(False)).first()
    if not c:
        raise fail(status.HTTP_404_NOT_FOUND, "影院不存在")

    h = MovieHall(
        hall_id=new_business_id("hal"),
        cinema_id=payload.cinemaId,
        name=payload.name,
        hall_type=payload.hallType,
        seat_layout=payload.seatLayout,
        is_deleted=False,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return ok(_hall_out(h), "影厅添加成功")


@router.get("/halls", summary="影厅列表")
def admin_list_halls(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    cinemaId: Annotated[str | None, Query(alias="cinemaId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(MovieHall).filter(MovieHall.is_deleted.is_(False))
    if cinemaId:
        q = q.filter(MovieHall.cinema_id == cinemaId)
    q = q.order_by(MovieHall.create_time.desc())
    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_hall_out(item) for item in items],
        "total": total,
    })


@router.put("/halls/{hall_id}", summary="修改影厅")
def admin_update_hall(
    hall_id: Annotated[str, Path(description="影厅 ID")],
    payload: MovieHallUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    h = db.query(MovieHall).filter(MovieHall.hall_id == hall_id, MovieHall.is_deleted.is_(False)).first()
    if not h:
        raise fail(status.HTTP_404_NOT_FOUND, "影厅不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        field_map = {
            "hallType": "hall_type",
            "seatLayout": "seat_layout",
        }
        db_col = field_map.get(k, k)
        setattr(h, db_col, v)

    db.commit()
    db.refresh(h)
    return ok(_hall_out(h), "影厅信息已修改")


@router.delete("/halls/{hall_id}", summary="删除影厅")
def admin_delete_hall(
    hall_id: Annotated[str, Path(description="影厅 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    h = db.query(MovieHall).filter(MovieHall.hall_id == hall_id, MovieHall.is_deleted.is_(False)).first()
    if not h:
        raise fail(status.HTTP_404_NOT_FOUND, "影厅不存在")
    h.is_deleted = True
    db.commit()
    return ok(None, "影厅已删除")


# ---------------------------------------------------------------------------
# 4. 场次排片 CRUD (Showtimes)
# ---------------------------------------------------------------------------
def _check_showtime_conflict(
    db: Session,
    hall_id: str,
    start_time: datetime,
    end_time: datetime,
    exclude_showtime_id: str | None = None,
) -> bool:
    # 查询同一放映厅、未删除的所有场次，是否有时间交叉
    q = db.query(MovieShowtime).filter(
        MovieShowtime.hall_id == hall_id,
        MovieShowtime.is_deleted.is_(False),
        MovieShowtime.start_time < end_time,
        MovieShowtime.end_time > start_time,
    )
    if exclude_showtime_id:
        q = q.filter(MovieShowtime.showtime_id != exclude_showtime_id)
    return q.first() is not None


@router.post("/showtimes", response_model=dict, status_code=status.HTTP_201_CREATED, summary="新增场次")
def admin_create_showtime(
    payload: MovieShowtimeCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    # 校验依赖性
    mov = db.query(Movie).filter(Movie.movie_id == payload.movieId, Movie.is_deleted.is_(False)).first()
    if not mov:
        raise fail(status.HTTP_404_NOT_FOUND, "电影不存在")
    cin = db.query(Cinema).filter(Cinema.cinema_id == payload.cinemaId, Cinema.is_deleted.is_(False)).first()
    if not cin:
        raise fail(status.HTTP_404_NOT_FOUND, "影院不存在")
    hal = db.query(MovieHall).filter(
        MovieHall.hall_id == payload.hallId,
        MovieHall.cinema_id == payload.cinemaId,
        MovieHall.is_deleted.is_(False),
    ).first()
    if not hal:
        raise fail(status.HTTP_444_NOT_FOUND if hasattr(status, "HTTP_444_NOT_FOUND") else status.HTTP_400_BAD_REQUEST, "所选影院中不存在此影厅")

    if payload.startTime >= payload.endTime:
        raise fail(status.HTTP_400_BAD_REQUEST, "开场时间必须早于散场时间")

    # 冲突校验
    if _check_showtime_conflict(db, payload.hallId, payload.startTime, payload.endTime):
        raise fail(status.HTTP_400_BAD_REQUEST, "排片时间与该影厅的已有放映场次存在冲突")

    s = MovieShowtime(
        showtime_id=new_business_id("sht"),
        movie_id=payload.movieId,
        cinema_id=payload.cinemaId,
        hall_id=payload.hallId,
        start_time=payload.startTime,
        end_time=payload.endTime,
        price=payload.price,
        original_price=payload.originalPrice,
        language_version=payload.languageVersion,
        is_deleted=False,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return ok(_showtime_out(s), "排片场次添加成功")


@router.get("/showtimes", summary="场次列表")
def admin_list_showtimes(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    cinemaId: Annotated[str | None, Query(alias="cinemaId")] = None,
    movieId: Annotated[str | None, Query(alias="movieId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(MovieShowtime).filter(MovieShowtime.is_deleted.is_(False))
    if cinemaId:
        q = q.filter(MovieShowtime.cinema_id == cinemaId)
    if movieId:
        q = q.filter(MovieShowtime.movie_id == movieId)
    q = q.order_by(MovieShowtime.start_time.asc())
    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_showtime_out(item) for item in items],
        "total": total,
    })


@router.put("/showtimes/{showtime_id}", summary="修改场次排片")
def admin_update_showtime(
    showtime_id: Annotated[str, Path(description="场次 ID")],
    payload: MovieShowtimeUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    s = db.query(MovieShowtime).filter(MovieShowtime.showtime_id == showtime_id, MovieShowtime.is_deleted.is_(False)).first()
    if not s:
        raise fail(status.HTTP_404_NOT_FOUND, "放映场次不存在")

    data = payload.model_dump(exclude_unset=True)
    new_start = data.get("startTime", s.start_time)
    new_end = data.get("endTime", s.end_time)

    if new_start >= new_end:
        raise fail(status.HTTP_400_BAD_REQUEST, "开场时间必须早于散场时间")

    # 冲突校验
    if _check_showtime_conflict(db, s.hall_id, new_start, new_end, exclude_showtime_id=showtime_id):
        raise fail(status.HTTP_400_BAD_REQUEST, "排片时间与该影厅的已有放映场次存在冲突")

    for k, v in data.items():
        field_map = {
            "startTime": "start_time",
            "endTime": "end_time",
            "originalPrice": "original_price",
            "languageVersion": "language_version",
        }
        db_col = field_map.get(k, k)
        setattr(s, db_col, v)

    db.commit()
    db.refresh(s)
    return ok(_showtime_out(s), "放映场次已修改")


@router.delete("/showtimes/{showtime_id}", summary="删除场次")
def admin_delete_showtime(
    showtime_id: Annotated[str, Path(description="场次 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    s = db.query(MovieShowtime).filter(MovieShowtime.showtime_id == showtime_id, MovieShowtime.is_deleted.is_(False)).first()
    if not s:
        raise fail(status.HTTP_404_NOT_FOUND, "放映场次不存在")
    s.is_deleted = True
    db.commit()
    return ok(None, "放映场次已取消/删除")


# ---------------------------------------------------------------------------
# 5. 电影票订单监管与统计 (Orders & Stats)
# ---------------------------------------------------------------------------
@router.get("/stats", summary="票房数据大盘统计")
def admin_get_ticketing_stats(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict:
    # 累计总票房 (paid 状态的总金额)
    total_box_office = db.query(func.sum(MovieTicketOrder.price_paid)).filter(
        MovieTicketOrder.pay_status == "paid",
        MovieTicketOrder.is_deleted.is_(False),
    ).scalar() or 0

    # 累计已售出电影票数量 (paid 状态的所有订单座位总数)
    # 在 SQLite/Postgres 下可以通过加载订单并对座位长度求和，或简单在内存聚合
    orders = db.query(MovieTicketOrder.seats).filter(
        MovieTicketOrder.pay_status == "paid",
        MovieTicketOrder.is_deleted.is_(False),
    ).all()
    total_tickets_sold = sum(len(o.seats) for o in orders)

    # 订单总笔数
    total_orders = db.query(func.count(MovieTicketOrder.id)).filter(
        MovieTicketOrder.is_deleted.is_(False),
    ).scalar() or 0

    return ok({
        "totalBoxOffice": total_box_office,
        "totalTicketsSold": total_tickets_sold,
        "totalOrders": total_orders,
    })


@router.get("/orders", summary="票务订单列表查询")
def admin_list_ticket_orders(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: Annotated[str | None, Query(alias="userId")] = None,
    showtimeId: Annotated[str | None, Query(alias="showtimeId")] = None,
    payStatus: Annotated[str | None, Query(alias="payStatus")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(MovieTicketOrder).filter(MovieTicketOrder.is_deleted.is_(False))
    if userId:
        q = q.filter(MovieTicketOrder.user_id == userId)
    if showtimeId:
        q = q.filter(MovieTicketOrder.showtime_id == showtimeId)
    if payStatus:
        q = q.filter(MovieTicketOrder.pay_status == payStatus)
    q = q.order_by(MovieTicketOrder.create_time.desc())

    items, total = paginate_with_total(q, page, limit)
    # 动态将 Pydantic validation 转化输出
    from app.schemas.movie import MovieOrderOut
    return ok({
        "list": [MovieOrderOut.model_validate(item) for item in items],
        "total": total,
    })
