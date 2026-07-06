from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.api.admin import fail
from app.api.deps import get_current_user_required
from app.core.pagination import paginate_with_total
from app.core.response import ok
from app.api.utils import new_business_id
from app.db.session import get_db
from app.models.ai_model import AiModel, AiModelPlan, AiModelUsageRecord, AiModelSubscription
from app.models.user import User
from app.schemas.ai_model import AiModelUseRequest, BatchDeleteRequest, AiModelSubscribeRequest
from app.core.ai_model_points import (
    grant_daily_model_points,
    consume_model_points,
    expire_old_grants,
    calculate_plan_price,
    get_active_promotion,
    today_expire_at,
)

router = APIRouter(prefix="/api/ai-model", tags=["AI模型服务"])


def _model_out(m: AiModel) -> dict:
    return {
        "modelId": m.model_id,
        "name": m.name,
        "type": m.type,
        "icon": m.icon,
        "cover": m.cover,
        "description": m.description,
        "pointsPerUse": m.points_per_use,
        "channel": m.channel,
        "features": m.features or [],
        "sort": m.sort,
        "status": m.status,
    }


def _usage_record_out(r: AiModelUsageRecord) -> dict:
    return {
        "recordId": r.record_id,
        "userId": r.user_id,
        "modelId": r.model_id,
        "modelName": r.model_name,
        "modelType": r.model_type,
        "prompt": r.prompt,
        "result": r.result,
        "resultType": r.result_type,
        "pointsConsumed": r.points_consumed,
        "status": r.status,
        "createTime": r.create_time.isoformat() if r.create_time else None,
        "updateTime": r.update_time.isoformat() if r.update_time else None,
    }


def _subscription_out(s: AiModelSubscription) -> dict:
    return {
        "subscriptionId": s.subscription_id,
        "userId": s.user_id,
        "planId": s.plan_id,
        "planName": s.plan_name,
        "periodType": s.period_type,
        "payAmount": s.pay_amount,
        "originalAmount": s.original_amount,
        "discountAmount": s.discount_amount,
        "promotionId": s.promotion_id,
        "payMethod": s.pay_method,
        "payStatus": s.pay_status,
        "pointsGranted": s.points_granted,
        "startTime": s.start_time.isoformat() if s.start_time else None,
        "endTime": s.end_time.isoformat() if s.end_time else None,
        "autoRenew": s.auto_renew,
        "createTime": s.create_time.isoformat() if s.create_time else None,
        "updateTime": s.update_time.isoformat() if s.update_time else None,
    }


# ---------------------------------------------------------------------------
# 模型浏览
# ---------------------------------------------------------------------------


@router.get("/list", summary="可用模型列表")
def list_available_models(
    db: Annotated[Session, Depends(get_db)],
    type: str | None = Query(default=None, description="按类型筛选: text/video/image/multimodal"),
):
    query = db.query(AiModel).filter(AiModel.status == "enabled")
    if type:
        query = query.filter(AiModel.type == type)
    query = query.order_by(AiModel.sort.asc(), AiModel.create_time.desc())
    models = query.all()
    return ok([_model_out(m) for m in models])


@router.get("/details/{modelId}", summary="模型详情")
def get_model_detail(
    modelId: str,
    db: Annotated[Session, Depends(get_db)],
):
    m = db.query(AiModel).filter(AiModel.model_id == modelId, AiModel.status == "enabled").first()
    if not m:
        raise fail(404, "未找到该模型或已下架")
    return ok(_model_out(m))


# ---------------------------------------------------------------------------
# 使用模型
# ---------------------------------------------------------------------------


@router.post("/use", summary="使用模型生成内容")
def use_model(
    payload: AiModelUseRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    m = db.query(AiModel).filter(AiModel.model_id == payload.modelId, AiModel.status == "enabled").first()
    if not m:
        raise fail(404, "模型未找到或不可用")

    try:
        points_info = consume_model_points(db, current_user, m.points_per_use)
    except ValueError as e:
        raise fail(400, str(e))

    # 根据模型类型生成 Mock 结果
    mock_result = ""
    res_type = "text"
    if m.type == "text":
        mock_result = f"这是对 '{payload.prompt[:20]}...' 的AI文本生成结果（模拟）。"
        res_type = "text"
    elif m.type == "image":
        mock_result = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=600"
        res_type = "image"
    elif m.type == "video":
        mock_result = "https://www.w3schools.com/html/mov_bbb.mp4"
        res_type = "video"
    else:
        mock_result = f"这是多模态融合生成结果（模拟）。提示词为: {payload.prompt}"
        res_type = "text"

    record = AiModelUsageRecord(
        record_id=new_business_id("amr"),
        user_id=current_user.user_id,
        model_id=m.model_id,
        model_name=m.name,
        model_type=m.type,
        prompt=payload.prompt,
        result=mock_result,
        result_type=res_type,
        points_consumed=m.points_per_use,
        status="completed",
        is_deleted=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ok(
        {
            "record": _usage_record_out(record),
            "pointsInfo": points_info,
        },
        "生成成功",
    )


@router.get("/enter", summary="进入模型页面（自动激活每日赠送积分）")
def enter_model_page(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    # 发放每日赠送积分（函数内部也会先过期旧积分）
    grant = grant_daily_model_points(db, current_user)
    db.commit()

    expire_at_str = today_expire_at().isoformat()
    return ok({
        "userId": current_user.user_id,
        "modelPoints": current_user.model_points or 0,
        "dailyModelPoints": current_user.daily_model_points or 0,
        "dailyExpireAt": expire_at_str,
        "vipLevel": current_user.model_vip_level,
        "vipExpireTime": current_user.model_vip_expire_time.isoformat() if current_user.model_vip_expire_time else None,
        "todayGranted": grant is not None,
    })


# ---------------------------------------------------------------------------
# 使用历史记录
# ---------------------------------------------------------------------------


@router.get("/history", summary="我的使用历史列表")
def list_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModelUsageRecord).filter(
        AiModelUsageRecord.user_id == current_user.user_id,
        AiModelUsageRecord.is_deleted == False,
    ).order_by(AiModelUsageRecord.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_usage_record_out(r) for r in items], "total": total})


@router.post("/history/batch-delete", summary="批量删除历史记录")
def batch_delete_history(
    payload: BatchDeleteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    records = db.query(AiModelUsageRecord).filter(
        AiModelUsageRecord.record_id.in_(payload.recordIds),
        AiModelUsageRecord.user_id == current_user.user_id,
    ).all()

    for r in records:
        r.is_deleted = True

    db.commit()
    return ok(message=f"成功删除 {len(records)} 条历史记录")


@router.delete("/history/clear", summary="清空所有历史记录")
def clear_all_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    db.query(AiModelUsageRecord).filter(
        AiModelUsageRecord.user_id == current_user.user_id,
    ).update({"is_deleted": True}, synchronize_session=False)

    db.commit()
    return ok(message="历史记录已全部清空")


@router.get("/history/{recordId}", summary="使用历史详情")
def get_history_detail(
    recordId: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    r = db.query(AiModelUsageRecord).filter(
        AiModelUsageRecord.record_id == recordId,
        AiModelUsageRecord.user_id == current_user.user_id,
        AiModelUsageRecord.is_deleted == False,
    ).first()
    if not r:
        raise fail(404, "未找到该历史记录")
    return ok(_usage_record_out(r))


@router.delete("/history/{recordId}", summary="删除单条历史记录")
def delete_single_history(
    recordId: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    r = db.query(AiModelUsageRecord).filter(
        AiModelUsageRecord.record_id == recordId,
        AiModelUsageRecord.user_id == current_user.user_id,
        AiModelUsageRecord.is_deleted == False,
    ).first()
    if not r:
        raise fail(404, "未找到该历史记录")

    r.is_deleted = True
    db.commit()
    return ok(message="删除成功")


# ---------------------------------------------------------------------------
# 充值与订阅
# ---------------------------------------------------------------------------


@router.get("/plans", summary="获取可用充值套餐列表")
def list_available_plans(
    db: Annotated[Session, Depends(get_db)],
):
    plans = db.query(AiModelPlan).filter(AiModelPlan.status == "enabled").order_by(AiModelPlan.sort.asc(), AiModelPlan.create_time.desc()).all()
    promotion = get_active_promotion(db)

    result = []
    for p in plans:
        # 如果是按年，自动计算少20%
        # 已经在后台创建套餐时可以配置，也可以在这里动态应用
        # 我们在这里统一做促销优惠活动的计算
        prices = calculate_plan_price(p.current_price, p.original_price, promotion)

        plan_data = {
            "planId": p.plan_id,
            "name": p.name,
            "tier": p.tier,
            "periodType": p.period_type,
            "durationDays": p.duration_days,
            "originalPrice": prices["originalPrice"],
            "currentPrice": p.current_price,
            "finalPrice": prices["finalPrice"],
            "discountAmount": prices["discountAmount"],
            "pointsMonthly": p.points_monthly,
            "pointsConversionRate": p.points_conversion_rate,
            "features": p.features or [],
            "badge": p.badge,
            "isRecommended": p.is_recommended,
            "extraPointsPct": prices["extraPointsPct"],
        }
        result.append(plan_data)

    return ok({"plans": result, "promotion": {
        "promotionId": promotion.promotion_id,
        "name": promotion.name,
        "discountRate": promotion.discount_rate,
        "extraPointsPct": promotion.extra_points_pct,
    } if promotion else None})


@router.post("/subscribe", summary="订阅充值（Mock支付）")
def subscribe_plan(
    payload: AiModelSubscribeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    p = db.query(AiModelPlan).filter(AiModelPlan.plan_id == payload.planId, AiModelPlan.status == "enabled").first()
    if not p:
        raise fail(404, "充值套餐不可用")

    promotion = get_active_promotion(db, p.plan_id)
    prices = calculate_plan_price(p.current_price, p.original_price, promotion)

    now = datetime.now(timezone.utc)
    duration_days = p.duration_days

    # 赠送积分基数：根据周期天数比例来算
    # 如果是按年(365天)，按年计算赠送基数 = p.points_monthly * 12
    # 如果是按天(如1天)，按天赠送 = p.points_monthly * 1 // 30
    months = max(1, duration_days // 30)
    base_points = p.points_monthly * months

    # 应用促销活动的额外赠送比例
    extra_pct = prices["extraPointsPct"]
    total_points_granted = base_points * (100 + extra_pct) // 100

    subscription = AiModelSubscription(
        subscription_id=new_business_id("ams"),
        user_id=current_user.user_id,
        plan_id=p.plan_id,
        plan_name=p.name,
        period_type=p.period_type,
        pay_amount=prices["finalPrice"],
        original_amount=prices["originalPrice"],
        discount_amount=prices["discountAmount"],
        promotion_id=promotion.promotion_id if promotion else None,
        pay_method=payload.payMethod,
        pay_status="paid",  # Mock 支付成功
        points_granted=total_points_granted,
        start_time=now,
        end_time=now + timedelta(days=duration_days),
        auto_renew=False,
    )
    db.add(subscription)

    # 充值积分（直接加到不过期积分 model_points 里）
    current_user.model_points = (current_user.model_points or 0) + total_points_granted

    # VIP 到期时间延长
    current_user.model_vip_level = p.tier
    if current_user.model_vip_expire_time and current_user.model_vip_expire_time > now:
        current_user.model_vip_expire_time += timedelta(days=duration_days)
    else:
        current_user.model_vip_expire_time = now + timedelta(days=duration_days)

    db.commit()
    db.refresh(subscription)

    return ok(_subscription_out(subscription), "购买成功")


@router.get("/subscription", summary="我的当前订阅状态")
def get_my_subscription(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    expire_old_grants(db, current_user)
    db.commit()

    latest_sub = db.query(AiModelSubscription).filter(
        AiModelSubscription.user_id == current_user.user_id,
        AiModelSubscription.pay_status == "paid",
    ).order_by(AiModelSubscription.create_time.desc()).first()

    point_overview = {
        "userId": current_user.user_id,
        "modelPoints": current_user.model_points or 0,
        "dailyModelPoints": current_user.daily_model_points or 0,
        "dailyExpireAt": today_expire_at().isoformat(),
        "vipLevel": current_user.model_vip_level,
        "vipExpireTime": current_user.model_vip_expire_time.isoformat() if current_user.model_vip_expire_time else None,
    }

    return ok({
        "subscription": _subscription_out(latest_sub) if latest_sub else None,
        "pointOverview": point_overview,
    })


# ---------------------------------------------------------------------------
# 积分概览
# ---------------------------------------------------------------------------


@router.get("/points", summary="我的模型积分概览")
def get_points_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
):
    expire_old_grants(db, current_user)
    db.commit()

    return ok({
        "userId": current_user.user_id,
        "modelPoints": current_user.model_points or 0,
        "dailyModelPoints": current_user.daily_model_points or 0,
        "dailyExpireAt": today_expire_at().isoformat(),
        "vipLevel": current_user.model_vip_level,
        "vipExpireTime": current_user.model_vip_expire_time.isoformat() if current_user.model_vip_expire_time else None,
    })
