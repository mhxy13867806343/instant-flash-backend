from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.serializers import point_record_item
from app.core.points import (
    POINT_TYPE_NAMES,
    PointError,
    grant_checkin,
    grant_invite,
    has_awarded_today,
    POINT_TYPE_CHECKIN,
)
from app.db.session import get_db
from app.models.point_record import PointRecord
from app.models.user import User

router = APIRouter(prefix="/api/user/points", tags=["用户端积分"])


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data if data is not None else {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


class InviteRequest(BaseModel):
    inviter_user_id: str = Field(alias="inviterUserId", min_length=1, max_length=64, title="邀请人用户ID")
    invitee_user_id: str = Field(alias="inviteeUserId", min_length=1, max_length=64, title="被邀请人用户ID")

    model_config = {"populate_by_name": True}


def _sum_change(db: Session, user_id: str, positive: bool) -> int:
    query = db.query(func.coalesce(func.sum(PointRecord.change_amount), 0)).filter(
        PointRecord.user_id == user_id
    )
    if positive:
        query = query.filter(PointRecord.change_amount > 0)
    else:
        query = query.filter(PointRecord.change_amount < 0)
    return int(query.scalar() or 0)


@router.get(
    "",
    summary="我的积分概览",
    description="获取当前登录用户的积分余额、累计获得、累计消耗以及今日是否已签到。",
)
def points_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    total_earned = _sum_change(db, current_user.user_id, positive=True)
    total_consumed = abs(_sum_change(db, current_user.user_id, positive=False))
    return ok(
        {
            "userId": current_user.user_id,
            "points": current_user.points or 0,
            "balance": current_user.points or 0,
            "totalEarned": total_earned,
            "totalConsumed": total_consumed,
            "todaySigned": has_awarded_today(db, current_user.user_id, POINT_TYPE_CHECKIN),
            "typeNames": POINT_TYPE_NAMES,
        }
    )


@router.get(
    "/records",
    summary="我的积分明细",
    description="分页查询当前登录用户的积分明细。支持按积分类型 type(0-8) 和方向 direction(earn 获得/consume 消耗) 筛选。",
)
def points_records(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    type: Annotated[int | None, Query(ge=0, le=8, description="积分类型：0登录 1邀请 2被邀请 3新注册 4活动 5分享 6系统补偿 7签到 8其他")] = None,
    direction: Annotated[str | None, Query(pattern="^(earn|consume)$", description="方向：earn 获得，consume 消耗")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, object]:
    query = db.query(PointRecord).filter(PointRecord.user_id == current_user.user_id)
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
    return ok({"list": [point_record_item(record) for record in records], "total": total})


@router.post(
    "/checkin",
    summary="每日签到",
    description="用户端每日签到，随机获得 1~5 积分，每日仅可签到一次。",
)
def points_checkin(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    try:
        record = grant_checkin(db, current_user)
    except PointError as exc:
        raise fail(status.HTTP_400_BAD_REQUEST, str(exc))
    db.commit()
    db.refresh(current_user)
    return ok(
        {
            "points": current_user.points or 0,
            "gained": record.change_amount,
            "record": point_record_item(record),
        },
        "签到成功",
    )


@router.post(
    "/invite",
    summary="邀请奖励发放",
    description="邀请关系成立后发放积分。前端传邀请人 inviterUserId 和被邀请人 inviteeUserId：被邀请人 +3，邀请人 +5（每日上限 3 次，超出不计入）。",
)
def points_invite(
    payload: InviteRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    inviter = db.query(User).filter(User.user_id == payload.inviter_user_id).one_or_none()
    if inviter is None:
        raise fail(status.HTTP_404_NOT_FOUND, "邀请人不存在")
    invitee = db.query(User).filter(User.user_id == payload.invitee_user_id).one_or_none()
    if invitee is None:
        raise fail(status.HTTP_404_NOT_FOUND, "被邀请人不存在")

    try:
        result = grant_invite(db, inviter, invitee)
    except PointError as exc:
        raise fail(status.HTTP_400_BAD_REQUEST, str(exc))
    db.commit()
    return ok(result, "邀请奖励发放成功")
