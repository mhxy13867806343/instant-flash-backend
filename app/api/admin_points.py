from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.admin import AdminResponse, fail, format_time, get_admin_subject, ok
from app.api.serializers import point_record_item
from app.api.user_identity import normalize_phone, phone_from_user_id
from app.db.session import get_db
from app.models.point_record import PointRecord
from app.models.user import User

router = APIRouter(prefix="/api/admin/points", tags=["后台管理"])


def _sum_change(db: Session, user_id: str, positive: bool) -> int:
    query = db.query(func.coalesce(func.sum(PointRecord.change_amount), 0)).filter(
        PointRecord.user_id == user_id
    )
    if positive:
        query = query.filter(PointRecord.change_amount > 0)
    else:
        query = query.filter(PointRecord.change_amount < 0)
    return int(query.scalar() or 0)


def points_user_item(db: Session, user: User) -> dict[str, Any]:
    phone = user.phone or phone_from_user_id(user.user_id) or ""
    total_earned = _sum_change(db, user.user_id, positive=True)
    total_consumed = abs(_sum_change(db, user.user_id, positive=False))
    record_count = (
        db.query(func.count(PointRecord.id)).filter(PointRecord.user_id == user.user_id).scalar() or 0
    )
    return {
        "userId": user.user_id,
        "nickname": user.nickname or "即闪用户",
        "avatar": user.avatar or "",
        "phone": phone,
        "points": user.points or 0,
        "totalEarned": total_earned,
        "totalConsumed": total_consumed,
        "recordCount": record_count,
        "status": "normal" if user.is_active else "banned",
        "regTime": format_time(user.create_time),
    }


@router.get(
    "/users",
    response_model=AdminResponse,
    summary="用户积分列表",
    description="后台用户积分管理列表，展示每个用户的当前积分、累计获得与累计消耗。支持按用户 ID、昵称、手机号筛选，按积分排序。",
)
def list_points_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: Annotated[str | None, Query(description="业务用户 ID，精确匹配")] = None,
    nickname: Annotated[str | None, Query(description="用户昵称，模糊匹配")] = None,
    phone: Annotated[str | None, Query(description="手机号，模糊匹配")] = None,
    sort: Annotated[str, Query(pattern="^(points_desc|points_asc|recent)$", description="排序：points_desc 积分降序，points_asc 积分升序，recent 注册时间倒序")] = "points_desc",
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(User)
    if userId:
        query = query.filter(User.user_id == userId)
    if nickname:
        query = query.filter(User.nickname.ilike(f"%{nickname}%"))
    if phone:
        phone_value = normalize_phone(phone) or phone
        query = query.filter(or_(User.phone.ilike(f"%{phone_value}%"), User.user_id.ilike(f"%{phone_value}%")))

    if sort == "points_asc":
        query = query.order_by(User.points.asc(), User.create_time.desc())
    elif sort == "recent":
        query = query.order_by(User.create_time.desc())
    else:
        query = query.order_by(User.points.desc(), User.create_time.desc())

    total = query.count()
    users = query.offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [points_user_item(db, user) for user in users], "total": total})


@router.get(
    "/users/{userId}/records",
    response_model=AdminResponse,
    summary="用户积分明细",
    description="后台查询指定用户的积分明细列表，支持按积分类型 type(0-8) 筛选。",
)
def list_points_user_records(
    userId: Annotated[str, Path(description="业务用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    type: Annotated[int | None, Query(ge=0, le=8, description="积分类型：0登录 1邀请 2被邀请 3新注册 4活动 5分享 6系统补偿 7签到 8其他")] = None,
    direction: Annotated[str | None, Query(pattern="^(earn|consume)$", description="方向：earn 获得，consume 消耗")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == userId).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户不存在")

    query = db.query(PointRecord).filter(PointRecord.user_id == userId)
    if type is not None:
        query = query.filter(PointRecord.type == type)
    if direction == "earn":
        query = query.filter(PointRecord.change_amount > 0)
    elif direction == "consume":
        query = query.filter(PointRecord.change_amount < 0)

    total = query.count()
    records = (
        query.order_by(PointRecord.create_time.desc(), PointRecord.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ok(
        {
            "userId": user.user_id,
            "nickname": user.nickname or "即闪用户",
            "points": user.points or 0,
            "list": [point_record_item(record) for record in records],
            "total": total,
        }
    )
