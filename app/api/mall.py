from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.points import POINT_TYPE_OTHER, award_points
from app.db.base import utc_now
from app.db.session import get_db
from app.models.mall import MallOrder, MallPaymentMethod, MallProduct, MallSetting
from app.models.user import User
from app.schemas.mall import (
    MallOrderCreate,
    MallOrderOut,
    MallOrderListResponse,
    MallPaymentMethodOut,
    MallProductOut,
    MallProductListResponse,
    ORDER_STATUS_LABELS,
)

router = APIRouter(prefix="/api/mall", tags=["用户端商城"])

MALL_SETTING_ID = 1


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data if data is not None else {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def _get_setting(db: Session) -> MallSetting:
    setting = db.get(MallSetting, MALL_SETTING_ID)
    if setting is None:
        # 设置不存在时用默认值（积分开关关闭）
        return MallSetting(id=MALL_SETTING_ID, points_switch=False)
    return setting


def _product_out(p: MallProduct, points_switch: bool) -> MallProductOut:
    return MallProductOut(
        productId=p.product_id,
        title=p.title,
        description=p.description,
        images=p.images or [],
        coverImage=p.cover_image,
        coverVideo=p.cover_video,
        originalPrice=p.original_price,
        currentPrice=p.current_price,
        pointsCost=p.points_cost,
        # 积分开关开启时，所有商品强制仅积分
        pointsOnly=True if points_switch else p.points_only,
        stock=p.stock,
        soldCount=p.sold_count,
        status=p.status,
        sort=p.sort,
        remark=p.remark,
        createTime=p.create_time,
        updateTime=p.update_time,
    )


def _order_out(o: MallOrder) -> MallOrderOut:
    return MallOrderOut(
        orderId=o.order_id,
        userId=o.user_id,
        productId=o.product_id,
        productTitle=o.product_title,
        productImage=o.product_image,
        quantity=o.quantity,
        unitPrice=o.unit_price,
        totalPrice=o.total_price,
        pointsUsed=o.points_used,
        payType=o.pay_type,
        payTypeValue=o.pay_type_value,
        status=o.status,
        statusLabel=ORDER_STATUS_LABELS.get(o.status, o.status),
        paidAt=o.paid_at,
        shippedAt=o.shipped_at,
        completedAt=o.completed_at,
        cancelledAt=o.cancelled_at,
        cancelReason=o.cancel_reason,
        remark=o.remark,
        createTime=o.create_time,
        updateTime=o.update_time,
    )


# ---------------------------------------------------------------------------
# 商品浏览（移动端）
# ---------------------------------------------------------------------------

@router.get(
    "/products",
    response_model=MallProductListResponse,
    summary="商品列表",
    description=(
        "移动端展示上架中的商品列表，仅返回 status=on_sale 的商品。"
        "响应中的 pointsOnly 字段已根据全局积分开关自动调整。"
    ),
)
def mobile_list_products(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user_required)],
    keyword: Annotated[str | None, Query(description="标题关键词")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MallProductListResponse:
    setting = _get_setting(db)
    q = db.query(MallProduct).filter(MallProduct.status == "on_sale")
    if keyword:
        q = q.filter(MallProduct.title.ilike(f"%{keyword}%"))
    total = q.count()
    products = (
        q.order_by(MallProduct.sort.asc(), MallProduct.create_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return MallProductListResponse(
        items=[_product_out(p, setting.points_switch) for p in products],
        total=total,
    )


@router.get(
    "/products/{product_id}",
    response_model=MallProductOut,
    summary="商品详情",
    description=(
        "移动端查询单个商品详情。"
        "pointsOnly=true 时用户只能用积分购买；"
        "pointsCost=0 时不支持积分；"
        "全局积分开关开启时 pointsOnly 强制为 true。"
    ),
)
def mobile_get_product(
    product_id: Annotated[str, Path(description="商品业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user_required)],
) -> MallProductOut:
    p = db.query(MallProduct).filter(
        MallProduct.product_id == product_id,
        MallProduct.status == "on_sale",
    ).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在或已下架")
    setting = _get_setting(db)
    return _product_out(p, setting.points_switch)


# ---------------------------------------------------------------------------
# 支付方式（移动端展示）
# ---------------------------------------------------------------------------

@router.get(
    "/payment-methods",
    summary="可用支付方式列表",
    description=(
        "移动端展示可用的支付方式列表（仅返回 status=enabled 的方式）。"
        "若全局积分开关开启，列表仅返回 type=points 的积分支付方式（如有），其他支付方式不显示。"
    ),
)
def mobile_list_payment_methods(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    setting = _get_setting(db)
    q = db.query(MallPaymentMethod).filter(MallPaymentMethod.status == "enabled")
    if setting.points_switch:
        # 积分开关开启，只展示 points 类型
        q = q.filter(MallPaymentMethod.type == "points")
    methods = q.order_by(MallPaymentMethod.sort.asc()).all()
    return ok(
        {
            "list": [
                MallPaymentMethodOut(
                    methodId=m.method_id,
                    name=m.name,
                    logo=m.logo,
                    type=m.type,
                    typeValue=m.type_value,
                    status=m.status,
                    sort=m.sort,
                    remark=m.remark,
                    createTime=m.create_time,
                    updateTime=m.update_time,
                ).model_dump()
                for m in methods
            ],
            "total": len(methods),
            "pointsSwitch": setting.points_switch,
        }
    )


# ---------------------------------------------------------------------------
# 下单
# ---------------------------------------------------------------------------

@router.post(
    "/orders",
    status_code=201,
    summary="下单",
    description=(
        "移动端用户下单。"
        "积分开关开启时 payType 必须为 points；"
        "使用积分支付时会校验用户积分是否足够；"
        "下单成功后订单状态为 pending_pay（待支付），需调用 /orders/{orderId}/pay 完成支付。"
    ),
)
def mobile_create_order(
    payload: MallOrderCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    setting = _get_setting(db)

    # 查商品
    p = db.query(MallProduct).filter(
        MallProduct.product_id == payload.product_id,
        MallProduct.status == "on_sale",
    ).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在或已下架")

    # 库存校验
    if p.stock < payload.quantity:
        raise fail(status.HTTP_400_BAD_REQUEST, f"库存不足，当前库存 {p.stock} 件")

    pay_type = payload.pay_type.strip().lower()

    # 积分开关校验：开启后只能积分支付
    if setting.points_switch and pay_type != "points":
        raise fail(status.HTTP_400_BAD_REQUEST, "当前商城仅支持积分支付，请使用积分购买")

    # 商品仅积分限制
    effective_points_only = setting.points_switch or p.points_only
    if effective_points_only and pay_type != "points":
        raise fail(status.HTTP_400_BAD_REQUEST, "该商品仅支持积分购买")

    # 支付方式校验（需在支付方式表中存在且启用）
    method = db.query(MallPaymentMethod).filter(
        MallPaymentMethod.type == pay_type,
        MallPaymentMethod.status == "enabled",
    ).first()
    if method is None:
        raise fail(status.HTTP_400_BAD_REQUEST, f"支付方式 '{pay_type}' 不可用")

    # 积分支付：校验 points_cost > 0 且用户积分足够
    points_needed = 0
    unit_price = p.current_price
    if pay_type == "points":
        if p.points_cost <= 0:
            raise fail(status.HTTP_400_BAD_REQUEST, "该商品不支持积分兑换")
        points_needed = p.points_cost * payload.quantity
        if (current_user.points or 0) < points_needed:
            raise fail(status.HTTP_400_BAD_REQUEST, f"积分不足，需要 {points_needed} 积分，当前余额 {current_user.points or 0}")
        unit_price = 0  # 纯积分支付，价格为 0

    total = unit_price * payload.quantity
    order = MallOrder(
        order_id=new_business_id("ord"),
        user_id=current_user.user_id,
        product_id=p.product_id,
        product_title=p.title,
        product_image=p.cover_image,
        quantity=payload.quantity,
        unit_price=unit_price,
        total_price=total,
        points_used=points_needed,
        pay_type=pay_type,
        pay_type_value=method.type_value,
        status="pending_pay",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return ok(_order_out(order).model_dump(), "下单成功")


# ---------------------------------------------------------------------------
# 支付
# ---------------------------------------------------------------------------

@router.post(
    "/orders/{order_id}/pay",
    summary="发起支付",
    description=(
        "移动端对待支付订单发起支付。"
        "当前为模拟支付：积分支付会立即扣除用户积分并扣减库存，更新订单为已支付；"
        "其他支付方式（微信/支付宝等）同样直接标记为已支付（模拟，未接入真实 SDK）。"
    ),
)
def mobile_pay_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    o = db.query(MallOrder).filter(
        MallOrder.order_id == order_id,
        MallOrder.user_id == current_user.user_id,
    ).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if o.status != "pending_pay":
        raise fail(status.HTTP_400_BAD_REQUEST, f"订单当前状态为「{ORDER_STATUS_LABELS.get(o.status, o.status)}」，无法支付")

    # 积分扣除
    if o.points_used > 0:
        if (current_user.points or 0) < o.points_used:
            raise fail(status.HTTP_400_BAD_REQUEST, f"积分不足，需要 {o.points_used} 积分，当前余额 {current_user.points or 0}")
        award_points(
            db,
            current_user,
            POINT_TYPE_OTHER,
            -o.points_used,
            title=f"兑换商品：{o.product_title}",
            source_id=o.order_id,
        )

    # 扣减库存 & 增加销量
    p = db.query(MallProduct).filter(MallProduct.product_id == o.product_id).first()
    if p is not None:
        p.stock = max(0, p.stock - o.quantity)
        p.sold_count = (p.sold_count or 0) + o.quantity
        if p.stock == 0:
            p.status = "sold_out"

    # 更新订单
    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    o.status = "paid"
    o.paid_at = now_str

    db.commit()
    db.refresh(o)
    return ok(_order_out(o).model_dump(), "支付成功")


# ---------------------------------------------------------------------------
# 我的订单（移动端）
# ---------------------------------------------------------------------------

@router.get(
    "/orders",
    response_model=MallOrderListResponse,
    summary="我的订单列表",
    description=(
        "移动端查询当前用户的订单列表。"
        "status 筛选：all(全部) / pending_pay(待支付) / paid(已支付) / shipped(已发货) / completed(已完成) / cancelled(已取消)。"
    ),
)
def mobile_list_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    order_status: Annotated[str | None, Query(alias="status", description="订单状态")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MallOrderListResponse:
    q = db.query(MallOrder).filter(MallOrder.user_id == current_user.user_id)
    if order_status and order_status != "all":
        q = q.filter(MallOrder.status == order_status)
    total = q.count()
    orders = (
        q.order_by(MallOrder.create_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return MallOrderListResponse(items=[_order_out(o) for o in orders], total=total)


@router.get(
    "/orders/{order_id}",
    response_model=MallOrderOut,
    summary="订单详情",
    description="移动端查询当前用户的单条订单详情。",
)
def mobile_get_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> MallOrderOut:
    o = db.query(MallOrder).filter(
        MallOrder.order_id == order_id,
        MallOrder.user_id == current_user.user_id,
    ).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    return _order_out(o)


@router.post(
    "/orders/{order_id}/cancel",
    summary="取消订单",
    description="移动端取消待支付订单，仅 status=pending_pay 的订单可以取消。",
)
def mobile_cancel_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    o = db.query(MallOrder).filter(
        MallOrder.order_id == order_id,
        MallOrder.user_id == current_user.user_id,
    ).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if o.status != "pending_pay":
        raise fail(status.HTTP_400_BAD_REQUEST, f"当前状态「{ORDER_STATUS_LABELS.get(o.status, o.status)}」的订单不能取消")

    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    o.status = "cancelled"
    o.cancelled_at = now_str
    o.cancel_reason = "用户主动取消"
    db.commit()
    db.refresh(o)
    return ok(_order_out(o).model_dump(), "订单已取消")
