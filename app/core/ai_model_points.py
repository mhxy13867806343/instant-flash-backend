"""AI 模型积分核心业务逻辑。

- 每日赠送模型积分（当天 23:59:59 CST 过期）
- 消耗积分（优先每日赠送 → 再扣充值积分）
- 过期清零
- 充值套餐价格计算
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.models.ai_model import AiModelPointGrant, AiModelPromotion
from app.models.user import User

CST = timezone(timedelta(hours=8))

# 每日赠送模型积分数量（后台可通过传参覆盖）
DEFAULT_DAILY_GRANT_AMOUNT = 50


def cst_now() -> datetime:
    """返回当前 CST 时间。"""
    return datetime.now(CST)


def today_expire_at() -> datetime:
    """返回今天 23:59:59 CST 的 UTC datetime。"""
    now = cst_now()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return end_of_day


def today_cst() -> date:
    """返回今天的 CST 日期。"""
    return cst_now().date()


def grant_daily_model_points(
    db: Session,
    user: User,
    amount: int = DEFAULT_DAILY_GRANT_AMOUNT,
) -> AiModelPointGrant | None:
    """每日赠送模型积分。如果今天已赠送则返回 None。

    1. 先过期旧的赠送积分
    2. 检查今天是否已发放
    3. 发放并更新 user.daily_model_points
    """
    expire_old_grants(db, user)

    today = today_cst()
    existing = (
        db.query(AiModelPointGrant)
        .filter(
            AiModelPointGrant.user_id == user.user_id,
            AiModelPointGrant.grant_date == today,
        )
        .first()
    )
    if existing is not None:
        return None  # 今日已赠送

    grant = AiModelPointGrant(
        grant_id=new_business_id("mpg"),
        user_id=user.user_id,
        grant_date=today,
        amount=amount,
        remaining=amount,
        expire_at=today_expire_at(),
        status="active",
    )
    db.add(grant)

    user.daily_model_points = (user.daily_model_points or 0) + amount
    db.flush()
    return grant


def expire_old_grants(db: Session, user: User) -> int:
    """过期该用户所有已到期的赠送积分，返回被清除的积分总量。"""
    now = cst_now()
    active_grants = (
        db.query(AiModelPointGrant)
        .filter(
            AiModelPointGrant.user_id == user.user_id,
            AiModelPointGrant.status == "active",
            AiModelPointGrant.expire_at < now,
        )
        .all()
    )
    total_expired = 0
    for g in active_grants:
        total_expired += g.remaining
        g.remaining = 0
        g.status = "expired"

    if total_expired > 0:
        user.daily_model_points = max(0, (user.daily_model_points or 0) - total_expired)
        db.flush()

    return total_expired


def consume_model_points(db: Session, user: User, amount: int) -> dict:
    """消耗模型积分。

    优先级：
    1. 今日赠送积分 (daily_model_points)
    2. 充值积分 (model_points)

    Returns dict with {dailyUsed, paidUsed, totalUsed}
    Raises ValueError if insufficient points.
    """
    if amount <= 0:
        raise ValueError("消耗积分数量必须大于 0")

    # 先过期旧的
    expire_old_grants(db, user)

    daily_balance = user.daily_model_points or 0
    paid_balance = user.model_points or 0
    total_available = daily_balance + paid_balance

    if total_available < amount:
        raise ValueError(
            f"模型积分不足，当前可用 {total_available}（赠送 {daily_balance} + 充值 {paid_balance}），需要 {amount}"
        )

    daily_used = 0
    paid_used = 0
    remaining_to_deduct = amount

    # 1. 先从今日赠送积分扣
    if daily_balance > 0 and remaining_to_deduct > 0:
        daily_used = min(daily_balance, remaining_to_deduct)
        remaining_to_deduct -= daily_used
        user.daily_model_points = daily_balance - daily_used

        # 同步更新 grant 记录
        _deduct_from_active_grants(db, user.user_id, daily_used)

    # 2. 剩余从充值积分扣
    if remaining_to_deduct > 0:
        paid_used = remaining_to_deduct
        user.model_points = paid_balance - paid_used

    db.flush()
    return {"dailyUsed": daily_used, "paidUsed": paid_used, "totalUsed": amount}


def _deduct_from_active_grants(db: Session, user_id: str, amount: int) -> None:
    """从活跃的赠送记录中按时间顺序扣减积分。"""
    grants = (
        db.query(AiModelPointGrant)
        .filter(
            AiModelPointGrant.user_id == user_id,
            AiModelPointGrant.status == "active",
            AiModelPointGrant.remaining > 0,
        )
        .order_by(AiModelPointGrant.expire_at.asc())
        .all()
    )
    remaining = amount
    for g in grants:
        if remaining <= 0:
            break
        deduct = min(g.remaining, remaining)
        g.remaining -= deduct
        remaining -= deduct
        if g.remaining == 0:
            g.status = "expired"
    db.flush()


def calculate_plan_price(
    plan_current_price: int,
    plan_original_price: int,
    promotion: AiModelPromotion | None = None,
) -> dict:
    """计算套餐实际价格（应用促销折扣）。

    Returns: {finalPrice, originalPrice, discountAmount, extraPointsPct}
    """
    final_price = plan_current_price

    extra_points_pct = 0

    if promotion is not None:
        now = cst_now()
        # 检查促销活动是否在有效期内
        if promotion.status == "enabled":
            in_range = True
            if promotion.start_time and now < promotion.start_time:
                in_range = False
            if promotion.end_time and now > promotion.end_time:
                in_range = False

            if in_range:
                final_price = plan_current_price * promotion.discount_rate // 100
                extra_points_pct = promotion.extra_points_pct

    discount_amount = plan_original_price - final_price

    return {
        "finalPrice": final_price,
        "originalPrice": plan_original_price,
        "discountAmount": max(0, discount_amount),
        "extraPointsPct": extra_points_pct,
    }


def get_active_promotion(db: Session, plan_id: str | None = None) -> AiModelPromotion | None:
    """获取当前生效的促销活动（如有）。"""
    now = cst_now()
    query = db.query(AiModelPromotion).filter(
        AiModelPromotion.status == "enabled",
    )
    results = query.all()

    for promo in results:
        # 检查时间范围
        if promo.start_time and now < promo.start_time:
            continue
        if promo.end_time and now > promo.end_time:
            continue
        # 检查适用套餐
        if promo.applicable_plans and plan_id and plan_id not in promo.applicable_plans:
            continue
        return promo  # 返回第一个匹配的

    return None
