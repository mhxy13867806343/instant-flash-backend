from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.admin import AdminResponse, fail, format_time, get_admin_subject, ok
from app.api.serializers import point_record_item
from app.api.user_identity import normalize_phone, phone_from_user_id
from app.api.utils import new_business_id
from app.core.points import POINT_TYPE_COMPENSATION, award_points
from app.core.wallet import get_or_create_wallet
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
    wallet = get_or_create_wallet(db, user.user_id)
    return {
        "userId": user.user_id,
        "nickname": user.nickname or "即闪用户",
        "avatar": user.avatar or "",
        "phone": phone,
        "points": user.points or 0,
        "totalEarned": total_earned,
        "totalConsumed": total_consumed,
        "recordCount": record_count,
        "walletBalance": wallet.balance,
        "walletStatus": wallet.status,
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


# ---------------------------------------------------------------------------
# 手动积分调整（管理员增减用户积分）
# ---------------------------------------------------------------------------

class PointsAdjustPayload(BaseModel):
    amount: int = Field(
        title="调整积分数",
        description="正数表示增加积分，负数表示扣减积分，不能为 0",
    )
    remark: str = Field(
        min_length=1, max_length=256,
        title="调整原因",
        description="后台操作说明，会记录在积分明细中",
    )

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("调整积分数不能为 0")
        return v


@router.post(
    "/users/{user_id}/adjust",
    summary="手动调整用户积分",
    description=(
        "管理员对指定用户手动增减积分。"
        "amount > 0 为增加（如活动奖励/补偿），amount < 0 为扣减（如违规处罚）。"
        "操作结果会记录在积分明细中，类型为'系统补偿'，来源 ID 为操作备注摘要。"
    ),
)
def adjust_user_points(
    user_id: Annotated[str, Path(description="用户业务 ID")],
    payload: PointsAdjustPayload,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户不存在")

    # 扣减校验：余额不能为负
    if payload.amount < 0 and (user.points or 0) + payload.amount < 0:
        raise fail(
            status.HTTP_400_BAD_REQUEST,
            f"积分不足，当前余额 {user.points or 0}，不能扣减 {abs(payload.amount)} 分",
        )

    action = "增加" if payload.amount > 0 else "扣减"
    record = award_points(
        db,
        user,
        POINT_TYPE_COMPENSATION,
        payload.amount,
        title=f"管理员{action}积分",
        remark=payload.remark,
        source_id=f"admin:{admin_subject}",
    )
    db.commit()
    db.refresh(user)

    return ok(
        {
            "userId": user.user_id,
            "adjustAmount": payload.amount,
            "balanceBefore": record.balance_after - payload.amount,
            "balanceAfter": record.balance_after,
            "recordId": record.record_id,
            "remark": payload.remark,
        },
        f"积分{action}成功",
    )
