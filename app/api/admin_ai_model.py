from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.admin import fail, get_admin_subject
from app.core.pagination import paginate_with_total
from app.core.response import ok
from app.api.utils import new_business_id
from app.db.session import get_db
from app.models.ai_model import AiModel, AiModelPlan, AiModelPromotion, AiModelUsageRecord, AiModelSubscription
from app.schemas.ai_model import (
    AiModelCreate,
    AiModelUpdate,
    AiModelPlanCreate,
    AiModelPlanUpdate,
    AiModelPromotionCreate,
    AiModelPromotionUpdate,
)

router = APIRouter(prefix="/api/admin/ai-models", tags=["后台管理"])


# Helper function to serialize AiModel
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
        "createTime": m.create_time.isoformat() if m.create_time else None,
        "updateTime": m.update_time.isoformat() if m.update_time else None,
    }


# Helper function to serialize AiModelPlan
def _plan_out(p: AiModelPlan) -> dict:
    return {
        "planId": p.plan_id,
        "name": p.name,
        "tier": p.tier,
        "periodType": p.period_type,
        "durationDays": p.duration_days,
        "originalPrice": p.original_price,
        "currentPrice": p.current_price,
        "pointsMonthly": p.points_monthly,
        "pointsConversionRate": p.points_conversion_rate,
        "features": p.features or [],
        "badge": p.badge,
        "isRecommended": p.is_recommended,
        "sort": p.sort,
        "status": p.status,
        "createTime": p.create_time.isoformat() if p.create_time else None,
        "updateTime": p.update_time.isoformat() if p.update_time else None,
    }


# Helper function to serialize AiModelPromotion
def _promotion_out(pr: AiModelPromotion) -> dict:
    return {
        "promotionId": pr.promotion_id,
        "name": pr.name,
        "description": pr.description,
        "discountRate": pr.discount_rate,
        "extraPointsPct": pr.extra_points_pct,
        "startTime": pr.start_time.isoformat() if pr.start_time else None,
        "endTime": pr.end_time.isoformat() if pr.end_time else None,
        "applicablePlans": pr.applicable_plans or [],
        "status": pr.status,
        "createTime": pr.create_time.isoformat() if pr.create_time else None,
        "updateTime": pr.update_time.isoformat() if pr.update_time else None,
    }


# Helper function to serialize AiModelUsageRecord
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


# Helper function to serialize AiModelSubscription
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
# AI 模型管理
# ---------------------------------------------------------------------------


@router.get("", summary="获取模型列表")
def list_models(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    type: str | None = Query(default=None, description="模型类型筛选"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModel)
    if type:
        query = query.filter(AiModel.type == type)
    query = query.order_by(AiModel.sort.asc(), AiModel.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_model_out(m) for m in items], "total": total})


@router.post("", summary="创建模型")
def create_model(
    payload: AiModelCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    m = AiModel(
        model_id=new_business_id("aim"),
        name=payload.name,
        type=payload.type,
        icon=payload.icon,
        cover=payload.cover,
        description=payload.description,
        points_per_use=payload.pointsPerUse,
        channel=payload.channel,
        features=payload.features,
        sort=payload.sort,
        status=payload.status,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ok(_model_out(m), "创建模型成功")


@router.put("/{modelId}", summary="更新模型")
def update_model(
    modelId: str,
    payload: AiModelUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    m = db.query(AiModel).filter(AiModel.model_id == modelId).first()
    if not m:
        raise fail(404, "未找到该模型")

    field_map = {"pointsPerUse": "points_per_use"}
    for k, v in payload.model_dump(exclude_unset=True).items():
        col = field_map.get(k, k)
        setattr(m, col, v)

    db.commit()
    db.refresh(m)
    return ok(_model_out(m), "更新模型成功")


@router.delete("/{modelId}", summary="删除模型")
def delete_model(
    modelId: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    m = db.query(AiModel).filter(AiModel.model_id == modelId).first()
    if not m:
        raise fail(404, "未找到该模型")

    db.delete(m)
    db.commit()
    return ok(message="删除模型成功")


# ---------------------------------------------------------------------------
# 充值套餐管理
# ---------------------------------------------------------------------------


@router.get("/plans", summary="获取套餐列表")
def list_plans(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    tier: str | None = Query(default=None),
    periodType: str | None = Query(default=None, alias="periodType"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModelPlan)
    if tier:
        query = query.filter(AiModelPlan.tier == tier)
    if periodType:
        query = query.filter(AiModelPlan.period_type == periodType)
    query = query.order_by(AiModelPlan.sort.asc(), AiModelPlan.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_plan_out(p) for p in items], "total": total})


@router.post("/plans", summary="创建充值套餐")
def create_plan(
    payload: AiModelPlanCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    p = AiModelPlan(
        plan_id=new_business_id("aip"),
        name=payload.name,
        tier=payload.tier,
        period_type=payload.periodType,
        duration_days=payload.durationDays,
        original_price=payload.originalPrice,
        current_price=payload.currentPrice,
        points_monthly=payload.pointsMonthly,
        points_conversion_rate=payload.pointsConversionRate,
        features=payload.features,
        badge=payload.badge,
        is_recommended=payload.isRecommended,
        sort=payload.sort,
        status=payload.status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok(_plan_out(p), "创建套餐成功")


@router.put("/plans/{planId}", summary="更新充值套餐")
def update_plan(
    planId: str,
    payload: AiModelPlanUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    p = db.query(AiModelPlan).filter(AiModelPlan.plan_id == planId).first()
    if not p:
        raise fail(404, "未找到该套餐")

    field_map = {
        "periodType": "period_type",
        "durationDays": "duration_days",
        "originalPrice": "original_price",
        "currentPrice": "current_price",
        "pointsMonthly": "points_monthly",
        "pointsConversionRate": "points_conversion_rate",
        "isRecommended": "is_recommended",
    }
    for k, v in payload.model_dump(exclude_unset=True).items():
        col = field_map.get(k, k)
        setattr(p, col, v)

    db.commit()
    db.refresh(p)
    return ok(_plan_out(p), "更新套餐成功")


@router.delete("/plans/{planId}", summary="删除充值套餐")
def delete_plan(
    planId: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    p = db.query(AiModelPlan).filter(AiModelPlan.plan_id == planId).first()
    if not p:
        raise fail(404, "未找到该套餐")

    db.delete(p)
    db.commit()
    return ok(message="删除套餐成功")


# ---------------------------------------------------------------------------
# 促销活动管理
# ---------------------------------------------------------------------------


@router.get("/promotions", summary="获取促销活动列表")
def list_promotions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModelPromotion).order_by(AiModelPromotion.create_time.desc())
    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_promotion_out(pr) for pr in items], "total": total})


@router.post("/promotions", summary="创建促销活动")
def create_promotion(
    payload: AiModelPromotionCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    pr = AiModelPromotion(
        promotion_id=new_business_id("prm"),
        name=payload.name,
        description=payload.description,
        discount_rate=payload.discountRate,
        extra_points_pct=payload.extraPointsPct,
        start_time=payload.startTime,
        end_time=payload.endTime,
        applicable_plans=payload.applicablePlans,
        status=payload.status,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return ok(_promotion_out(pr), "创建促销活动成功")


@router.put("/promotions/{promotionId}", summary="更新促销活动")
def update_promotion(
    promotionId: str,
    payload: AiModelPromotionUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    pr = db.query(AiModelPromotion).filter(AiModelPromotion.promotion_id == promotionId).first()
    if not pr:
        raise fail(404, "未找到该促销活动")

    field_map = {
        "discountRate": "discount_rate",
        "extraPointsPct": "extra_points_pct",
        "startTime": "start_time",
        "endTime": "end_time",
        "applicablePlans": "applicable_plans",
    }
    for k, v in payload.model_dump(exclude_unset=True).items():
        col = field_map.get(k, k)
        setattr(pr, col, v)

    db.commit()
    db.refresh(pr)
    return ok(_promotion_out(pr), "更新促销活动成功")


@router.delete("/promotions/{promotionId}", summary="删除促销活动")
def delete_promotion(
    promotionId: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    pr = db.query(AiModelPromotion).filter(AiModelPromotion.promotion_id == promotionId).first()
    if not pr:
        raise fail(404, "未找到该促销活动")

    db.delete(pr)
    db.commit()
    return ok(message="删除促销活动成功")


# ---------------------------------------------------------------------------
# 使用统计与使用记录
# ---------------------------------------------------------------------------


@router.get("/stats", summary="获取AI模型服务统计数据")
def get_stats(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
):
    total_uses = db.query(func.count(AiModelUsageRecord.id)).filter(AiModelUsageRecord.is_deleted == False).scalar() or 0
    total_points_consumed = db.query(func.coalesce(func.sum(AiModelUsageRecord.points_consumed), 0)).scalar() or 0
    total_subscriptions = db.query(func.count(AiModelSubscription.id)).filter(AiModelSubscription.pay_status == "paid").scalar() or 0
    total_revenue = db.query(func.coalesce(func.sum(AiModelSubscription.pay_amount), 0)).filter(AiModelSubscription.pay_status == "paid").scalar() or 0

    return ok({
        "totalUses": total_uses,
        "totalPointsConsumed": total_points_consumed,
        "totalSubscriptions": total_subscriptions,
        "totalRevenue": total_revenue,
    })


@router.get("/usage-records", summary="获取全部使用记录（管理员）")
def list_usage_records(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: str | None = Query(default=None, alias="userId"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModelUsageRecord).filter(AiModelUsageRecord.is_deleted == False)
    if userId:
        query = query.filter(AiModelUsageRecord.user_id == userId)
    query = query.order_by(AiModelUsageRecord.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_usage_record_out(r) for r in items], "total": total})


@router.get("/subscriptions", summary="获取全部订阅订单（管理员）")
def list_subscriptions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: str | None = Query(default=None, alias="userId"),
    payStatus: str | None = Query(default=None, alias="payStatus"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(AiModelSubscription)
    if userId:
        query = query.filter(AiModelSubscription.user_id == userId)
    if payStatus:
        query = query.filter(AiModelSubscription.pay_status == payStatus)
    query = query.order_by(AiModelSubscription.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({"list": [_subscription_out(s) for s in items], "total": total})
