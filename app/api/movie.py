from __future__ import annotations

import random
from typing import Annotated, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.pagination import paginate_with_total
from app.core.response import ok
from app.api.admin import fail
from app.db.session import get_db
from app.models.movie import Movie, Cinema, MovieHall, MovieShowtime, MovieTicketOrder
from app.models.user import User
from app.schemas.movie import (
    MovieOut,
    CinemaOut,
    MovieShowtimeOut,
    MovieOrderCreate,
    MovieOrderOut,
    SeatLayoutStateOut,
)

router = APIRouter(prefix="/api/movie", tags=["电影票务服务"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(dt: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < now


def _cleanup_expired_orders(db: Session) -> None:
    """自动清理并取消超时未支付的电影票订单，释放被锁定的座位。"""
    now = _utc_now()
    db.query(MovieTicketOrder).filter(
        MovieTicketOrder.pay_status == "pending_pay",
        MovieTicketOrder.expire_time < now,
        MovieTicketOrder.is_deleted.is_(False),
    ).update({"pay_status": "cancelled"}, synchronize_session=False)
    db.commit()


# Helper serializers
def _movie_out(m: Movie) -> MovieOut:
    return MovieOut.model_validate(m)


def _cinema_out(c: Cinema) -> CinemaOut:
    return CinemaOut.model_validate(c)


def _showtime_out(s: MovieShowtime) -> MovieShowtimeOut:
    return MovieShowtimeOut.model_validate(s)


# ---------------------------------------------------------------------------
# 1. 电影浏览接口
# ---------------------------------------------------------------------------
@router.get("/movies", summary="获取上映/即将上映电影列表")
def list_movies(
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str, Query(alias="status", pattern="^(showing|upcoming)$")] = "showing",
    query: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    q = db.query(Movie).filter(Movie.is_deleted.is_(False), Movie.status == status_filter)
    if query:
        q = q.filter(Movie.title.ilike(f"%{query}%"))

    if status_filter == "showing":
        q = q.order_by(Movie.rating.desc(), Movie.create_time.desc())
    else:
        q = q.order_by(Movie.release_date.asc())

    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_movie_out(item) for item in items],
        "total": total,
    })


@router.get("/movies/{movie_id}", summary="获取电影详情")
def get_movie_detail(
    movie_id: Annotated[str, Path(description="电影 ID")],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    m = db.query(Movie).filter(Movie.movie_id == movie_id, Movie.is_deleted.is_(False)).first()
    if not m:
        raise fail(status.HTTP_404_NOT_FOUND, "电影未找到")
    return ok(_movie_out(m))


# ---------------------------------------------------------------------------
# 2. 影院排片浏览接口
# ---------------------------------------------------------------------------
@router.get("/cinemas", summary="影院列表（支持按电影/城市筛选）")
def list_cinemas(
    db: Annotated[Session, Depends(get_db)],
    city: Annotated[str | None, Query()] = None,
    movieId: Annotated[str | None, Query(alias="movieId")] = None,
    query: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    # 如果指定了 movieId，我们只返回今天或未来有该电影排片场次的影院
    q = db.query(Cinema).filter(Cinema.is_deleted.is_(False))
    if city:
        q = q.filter(Cinema.city == city)
    if query:
        q = q.filter(Cinema.name.ilike(f"%{query}%"))

    if movieId:
        now = _utc_now()
        # 子查询：有排片的影院 ID 列表
        cinema_ids = db.query(MovieShowtime.cinema_id).filter(
            MovieShowtime.movie_id == movieId,
            MovieShowtime.end_time > now,
            MovieShowtime.is_deleted.is_(False),
        ).subquery()
        q = q.filter(Cinema.cinema_id.in_(cinema_ids))

    q = q.order_by(Cinema.create_time.desc())
    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [_cinema_out(item) for item in items],
        "total": total,
    })


@router.get("/cinemas/{cinema_id}/showtimes", summary="获取指定影院的放映场次排片")
def get_cinema_showtimes(
    cinema_id: Annotated[str, Path(description="影院 ID")],
    db: Annotated[Session, Depends(get_db)],
    movieId: Annotated[str | None, Query(alias="movieId")] = None,
) -> dict:
    # 确认影院存在
    cin = db.query(Cinema).filter(Cinema.cinema_id == cinema_id, Cinema.is_deleted.is_(False)).first()
    if not cin:
        raise fail(status.HTTP_404_NOT_FOUND, "影院未找到")

    now = _utc_now()
    q = db.query(MovieShowtime).filter(
        MovieShowtime.cinema_id == cinema_id,
        MovieShowtime.end_time > now,
        MovieShowtime.is_deleted.is_(False),
    )
    if movieId:
        q = q.filter(MovieShowtime.movie_id == movieId)

    q = q.order_by(MovieShowtime.start_time.asc())
    showtimes = q.all()
    return ok([_showtime_out(s) for s in showtimes])


# ---------------------------------------------------------------------------
# 3. 选座、占座状态渲染与订单核心接口
# ---------------------------------------------------------------------------
@router.get("/showtimes/{showtime_id}/seats", response_model=dict, summary="获取排片场次实时座位图")
def get_showtime_seats(
    showtime_id: Annotated[str, Path(description="放映场次 ID")],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    _cleanup_expired_orders(db)

    s = db.query(MovieShowtime).filter(MovieShowtime.showtime_id == showtime_id, MovieShowtime.is_deleted.is_(False)).first()
    if not s:
        raise fail(status.HTTP_404_NOT_FOUND, "场次不存在")

    hall = db.query(MovieHall).filter(MovieHall.hall_id == s.hall_id, MovieHall.is_deleted.is_(False)).first()
    if not hall:
        raise fail(status.HTTP_404_NOT_FOUND, "影厅不存在")

    # 查询当前场次中已被售出(paid)或支付中锁定(pending_pay)的订单
    orders = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.showtime_id == showtime_id,
        MovieTicketOrder.pay_status.in_(["paid", "pending_pay"]),
        MovieTicketOrder.is_deleted.is_(False),
    ).all()

    occupied = []
    for o in orders:
        for seat in o.seats:
            occupied.append(f"{seat.get('row')}-{seat.get('col')}")

    layout = hall.seat_layout or {}
    broken = layout.get("broken", [])

    return ok(
        SeatLayoutStateOut(
            rows=layout.get("rows", 0),
            cols=layout.get("cols", 0),
            brokenSeats=broken,
            occupiedSeats=occupied,
        )
    )


@router.post("/orders", response_model=dict, status_code=status.HTTP_201_CREATED, summary="锁定座位创建选座订单")
def create_ticket_order(
    payload: MovieOrderCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    _cleanup_expired_orders(db)

    # 1. 验证放映场次
    s = db.query(MovieShowtime).filter(MovieShowtime.showtime_id == payload.showtimeId, MovieShowtime.is_deleted.is_(False)).first()
    if not s:
        raise fail(status.HTTP_404_NOT_FOUND, "放映场次未找到")

    # 2. 获取影厅座位配置
    hall = db.query(MovieHall).filter(MovieHall.hall_id == s.hall_id, MovieHall.is_deleted.is_(False)).first()
    if not hall:
        raise fail(status.HTTP_404_NOT_FOUND, "影厅不存在")
    layout = hall.seat_layout or {}
    total_rows = layout.get("rows", 0)
    total_cols = layout.get("cols", 0)
    broken = layout.get("broken", [])

    # 3. 校验所选座席是否在合法范围内，及是否被破坏不可选
    requested_seat_keys = set()
    for seat in payload.seats:
        if seat.row < 1 or seat.row > total_rows or seat.col < 1 or seat.col > total_cols:
            raise fail(status.HTTP_400_BAD_REQUEST, f"所选座位 {seat.name} 超出影厅座位大小范围")
        key = f"{seat.row}-{seat.col}"
        if key in broken:
            raise fail(status.HTTP_400_BAD_REQUEST, f"所选座位 {seat.name} 属于故障或过道座位，不可选")
        requested_seat_keys.add(key)

    # 4. 校验所选座席是否已经被他人锁定或购买
    occupied_orders = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.showtime_id == payload.showtimeId,
        MovieTicketOrder.pay_status.in_(["paid", "pending_pay"]),
        MovieTicketOrder.is_deleted.is_(False),
    ).all()

    for o in occupied_orders:
        for occupied_seat in o.seats:
            key = f"{occupied_seat.get('row')}-{occupied_seat.get('col')}"
            if key in requested_seat_keys:
                raise fail(status.HTTP_400_BAD_REQUEST, f"很抱歉，座位 {occupied_seat.get('name')} 刚刚已被其他用户选定，请选择其他座位")

    # 5. 计算价格并创建订单（锁定 15 分钟）
    seat_count = len(payload.seats)
    total_price = s.price * seat_count
    expire = _utc_now() + timedelta(minutes=15)

    order = MovieTicketOrder(
        order_id=new_business_id("mto"),
        user_id=current_user.user_id,
        showtime_id=payload.showtimeId,
        seats=[{"row": st.row, "col": st.col, "name": st.name} for st in payload.seats],
        price_paid=total_price,
        pay_status="pending_pay",
        expire_time=expire,
        is_deleted=False,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return ok(MovieOrderOut.model_validate(order), "锁座创建订单成功，请于15分钟内完成支付")


@router.post("/orders/{order_id}/pay", response_model=dict, summary="模拟支付并自动出票")
def pay_ticket_order(
    order_id: Annotated[str, Path(description="订单 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    order = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.order_id == order_id,
        MovieTicketOrder.user_id == current_user.user_id,
        MovieTicketOrder.is_deleted.is_(False),
    ).first()

    if not order:
        raise fail(status.HTTP_404_NOT_FOUND, "订单未找到")

    if order.pay_status == "paid":
        return ok(MovieOrderOut.model_validate(order), "订单已支付，请勿重复发起")

    if order.pay_status == "cancelled":
        raise fail(status.HTTP_400_BAD_REQUEST, "订单已失效取消，无法发起支付")

    # 校验是否超时
    if _is_expired(order.expire_time):
        order.pay_status = "cancelled"
        db.commit()
        raise fail(status.HTTP_400_BAD_REQUEST, "订单支付已超时失效，占用的座位已被释放")

    # 模拟支付扣款成功 -> 生成 12 位纯数字电子凭证取票码
    code = "".join(str(random.randint(0, 9)) for _ in range(12))
    order.pay_status = "paid"
    order.paid_at = _utc_now()
    order.ticket_code = code

    db.commit()
    db.refresh(order)
    return ok(MovieOrderOut.model_validate(order), "模拟支付并出票成功")


@router.get("/orders/my", summary="查看当前用户的电影票根/订单")
def list_my_ticket_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    _cleanup_expired_orders(db)

    q = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.user_id == current_user.user_id,
        MovieTicketOrder.is_deleted.is_(False),
    ).order_by(MovieTicketOrder.create_time.desc())

    items, total = paginate_with_total(q, page, limit)
    return ok({
        "list": [MovieOrderOut.model_validate(item) for item in items],
        "total": total,
    })


@router.get("/orders/{order_id}", summary="获取电影订单票务凭证详情")
def get_ticket_order_detail(
    order_id: Annotated[str, Path(description="订单 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    order = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.order_id == order_id,
        MovieTicketOrder.user_id == current_user.user_id,
        MovieTicketOrder.is_deleted.is_(False),
    ).first()

    if not order:
        raise fail(status.HTTP_404_NOT_FOUND, "订单未找到")
    return ok(MovieOrderOut.model_validate(order))


@router.post("/orders/{order_id}/cancel", summary="用户手动取消待支付订单")
def cancel_ticket_order(
    order_id: Annotated[str, Path(description="订单 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    order = db.query(MovieTicketOrder).filter(
        MovieTicketOrder.order_id == order_id,
        MovieTicketOrder.user_id == current_user.user_id,
        MovieTicketOrder.is_deleted.is_(False),
    ).first()

    if not order:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")

    if order.pay_status == "paid":
        raise fail(status.HTTP_400_BAD_REQUEST, "已支付订单不能直接取消")
    if order.pay_status == "cancelled":
        return ok(None, "订单已被取消，无需重复操作")

    order.pay_status = "cancelled"
    db.commit()
    return ok(None, "选座订单已成功取消，锁定座位已释放")
