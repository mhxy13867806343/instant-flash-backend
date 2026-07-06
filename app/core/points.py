from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.core.db_utils import sum_column
from app.models.point_record import PointRecord
from app.models.user import User

CST = timezone(timedelta(hours=8))

POINT_TYPE_LOGIN = 0
POINT_TYPE_INVITER = 1
POINT_TYPE_INVITEE = 2
POINT_TYPE_REGISTER = 3
POINT_TYPE_ACTIVITY = 4
POINT_TYPE_SHARE = 5
POINT_TYPE_COMPENSATION = 6
POINT_TYPE_CHECKIN = 7
POINT_TYPE_OTHER = 8
POINT_TYPE_MALL = 9  # 商城积分兑换（消耗/退还）

POINT_TYPE_NAMES: dict[int, str] = {
    POINT_TYPE_LOGIN: "登录",
    POINT_TYPE_INVITER: "邀请",
    POINT_TYPE_INVITEE: "被邀请",
    POINT_TYPE_REGISTER: "新注册",
    POINT_TYPE_ACTIVITY: "活动获得",
    POINT_TYPE_SHARE: "分享",
    POINT_TYPE_COMPENSATION: "系统补偿",
    POINT_TYPE_CHECKIN: "签到",
    POINT_TYPE_OTHER: "其他",
    POINT_TYPE_MALL: "商城兑换",
}

LOGIN_POINTS = 2
INVITER_POINTS = 5
INVITEE_POINTS = 3
INVITE_DAILY_LIMIT = 3
REGISTER_POINTS_RANGE = (1, 5)
CHECKIN_POINTS_RANGE = (1, 5)


class PointError(Exception):
    """业务级积分错误，供接口层转换为 HTTP 响应。"""


def point_type_name(type_int: int) -> str:
    return POINT_TYPE_NAMES.get(type_int, "其他")


def cst_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(CST)).astimezone(CST)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def sum_point_change(db: Session, user_id: str, positive: bool) -> int:
    """统计用户积分变动总额：positive=True 求获得，False 求消耗（负值）。"""
    condition = PointRecord.change_amount > 0 if positive else PointRecord.change_amount < 0
    return sum_column(db, PointRecord.change_amount, PointRecord.user_id == user_id, condition)


def award_points(
    db: Session,
    user: User,
    type_int: int,
    amount: int,
    title: str | None = None,
    remark: str | None = None,
    source_id: str | None = None,
    direction: str | None = None,
    expire_at: datetime | None = None,
) -> PointRecord:
    resolved_direction = direction or ("consume" if amount < 0 else "earn")
    user.points = (user.points or 0) + amount
    record = PointRecord(
        record_id=new_business_id("pt"),
        user_id=user.user_id,
        type=type_int,
        direction=resolved_direction,
        change_amount=amount,
        balance_after=user.points,
        title=title or point_type_name(type_int),
        remark=remark,
        source_id=source_id,
        expire_at=expire_at,
    )
    db.add(record)
    db.flush()
    return record


def has_awarded_today(db: Session, user_id: str, type_int: int) -> bool:
    start, end = cst_day_bounds()
    return (
        db.query(PointRecord.id)
        .filter(
            PointRecord.user_id == user_id,
            PointRecord.type == type_int,
            PointRecord.create_time >= start,
            PointRecord.create_time < end,
        )
        .first()
        is not None
    )


def count_type_today(db: Session, user_id: str, type_int: int) -> int:
    start, end = cst_day_bounds()
    return (
        db.query(func.count(PointRecord.id))
        .filter(
            PointRecord.user_id == user_id,
            PointRecord.type == type_int,
            PointRecord.create_time >= start,
            PointRecord.create_time < end,
        )
        .scalar()
        or 0
    )


def grant_daily_login(db: Session, user: User) -> PointRecord | None:
    """每日首次登录奖励，当天已发放则返回 None。"""
    if has_awarded_today(db, user.user_id, POINT_TYPE_LOGIN):
        return None
    return award_points(db, user, POINT_TYPE_LOGIN, LOGIN_POINTS, title="每日登录奖励")


def grant_registration(db: Session, user: User) -> PointRecord:
    """新用户注册奖励，随机 1~5 分。调用方需保证仅在首次创建时调用。"""
    amount = random.randint(*REGISTER_POINTS_RANGE)
    return award_points(db, user, POINT_TYPE_REGISTER, amount, title="新用户注册奖励")


def grant_checkin(db: Session, user: User) -> PointRecord:
    """签到奖励，随机 1~5 分，每日一次。"""
    if has_awarded_today(db, user.user_id, POINT_TYPE_CHECKIN):
        raise PointError("今日已签到，请明天再来")
    amount = random.randint(*CHECKIN_POINTS_RANGE)
    return award_points(db, user, POINT_TYPE_CHECKIN, amount, title="每日签到奖励")


def grant_invite(db: Session, inviter: User, invitee: User) -> dict[str, object]:
    """处理邀请奖励：被邀请人固定 +3（仅一次），邀请人 +5（每日上限 3 次）。"""
    if inviter.user_id == invitee.user_id:
        raise PointError("邀请人和被邀请人不能是同一个用户")

    already_invited = (
        db.query(PointRecord.id)
        .filter(PointRecord.user_id == invitee.user_id, PointRecord.type == POINT_TYPE_INVITEE)
        .first()
    )
    if already_invited is not None:
        raise PointError("该被邀请人已通过邀请获得过积分，不能重复邀请")

    invitee_record = award_points(
        db,
        invitee,
        POINT_TYPE_INVITEE,
        INVITEE_POINTS,
        title="被邀请奖励",
        source_id=inviter.user_id,
    )

    inviter_awarded = count_type_today(db, inviter.user_id, POINT_TYPE_INVITER)
    inviter_counted = inviter_awarded < INVITE_DAILY_LIMIT
    inviter_record = None
    if inviter_counted:
        inviter_record = award_points(
            db,
            inviter,
            POINT_TYPE_INVITER,
            INVITER_POINTS,
            title="邀请好友奖励",
            source_id=invitee.user_id,
        )

    return {
        "inviterUserId": inviter.user_id,
        "inviteeUserId": invitee.user_id,
        "inviteePoints": INVITEE_POINTS,
        "inviterPoints": INVITER_POINTS if inviter_counted else 0,
        "inviterCounted": inviter_counted,
        "inviterDailyUsed": inviter_awarded + (1 if inviter_counted else 0),
        "inviterDailyLimit": INVITE_DAILY_LIMIT,
        "inviteeRecordId": invitee_record.record_id,
        "inviterRecordId": inviter_record.record_id if inviter_record else None,
    }
