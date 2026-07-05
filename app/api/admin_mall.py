from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.admin import fail, format_time, get_admin_subject, ok
from app.api.utils import new_business_id
from app.core.points import POINT_TYPE_MALL, award_points, cst_day_bounds
from app.db.base import utc_now
from app.db.session import get_db
from app.models.mall import MallOrder, MallPaymentMethod, MallProduct, MallSetting
from app.models.user import User
from app.schemas.mall import (
    MallOrderListResponse,
    MallOrderOut,
    MallOrderStatusUpdate,
    MallPaymentMethodCreate,
    MallPaymentMethodOut,
    MallPaymentMethodUpdate,
    MallProductCreate,
    MallProductListResponse,
    MallProductOut,
    MallProductUpdate,
    MallSettingOut,
    MallSettingUpdate,
    ORDER_STATUS_LABELS,
)

router = APIRouter(prefix="/api/admin/mall", tags=["后台管理"])

MALL_SETTING_ID = 1


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _ensure_mall_setting(db: Session) -> MallSetting:
    """确保商城全局设置记录存在（单行，id=1）。"""
    setting = db.get(MallSetting, MALL_SETTING_ID)
    if setting is None:
        setting = MallSetting(id=MALL_SETTING_ID, points_switch=False)
        db.add(setting)
        db.flush()
    return setting


def _product_out(p: MallProduct) -> MallProductOut:
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
        pointsOnly=p.points_only,
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
        expireAt=o.expire_at,
        userRemark=o.user_remark,
        receiverName=o.receiver_name,
        receiverPhone=o.receiver_phone,
        receiverAddress=o.receiver_address,
        expressCompany=o.express_company,
        expressNo=o.express_no,
        shareToken=o.share_token,
        createTime=o.create_time,
        updateTime=o.update_time,
    )


def _method_out(m: MallPaymentMethod) -> MallPaymentMethodOut:
    return MallPaymentMethodOut(
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
    )


# ---------------------------------------------------------------------------
# 商城全局设置
# ---------------------------------------------------------------------------

@router.get(
    "/settings",
    summary="查询商城全局设置",
    description="查询商城全局设置，包括积分开关。积分开关开启后用户端只能使用积分购买，不能使用价格支付。",
)
def get_mall_settings(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    setting = _ensure_mall_setting(db)
    db.commit()
    return ok(
        MallSettingOut(
            pointsSwitch=setting.points_switch,
            remark=setting.remark,
            updateTime=setting.update_time,
        ).model_dump()
    )


@router.put(
    "/settings",
    summary="修改商城全局设置",
    description="修改商城全局设置。pointsSwitch=true 时全局仅允许积分支付，所有价格支付方式对用户端不可用。",
)
def update_mall_settings(
    payload: MallSettingUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    setting = _ensure_mall_setting(db)
    setting.points_switch = payload.pointsSwitch
    if payload.remark is not None:
        setting.remark = payload.remark
    db.commit()
    db.refresh(setting)
    return ok(
        MallSettingOut(
            pointsSwitch=setting.points_switch,
            remark=setting.remark,
            updateTime=setting.update_time,
        ).model_dump(),
        "设置已更新",
    )


# ---------------------------------------------------------------------------
# 商品管理
# ---------------------------------------------------------------------------

@router.post(
    "/products",
    status_code=201,
    summary="新增商品",
    description="PC 端新增商品。originalPrice 必须 > 0；currentPrice 不传时自动设为 originalPrice / 2。图片最多 9 张，封面图与封面视频二选一。",
)
def create_product(
    payload: MallProductCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    p = MallProduct(
        product_id=new_business_id("prod"),
        title=payload.title,
        description=payload.description,
        images=payload.images,
        cover_image=payload.cover_image,
        cover_video=payload.cover_video,
        original_price=payload.original_price,
        current_price=payload.current_price,  # model_validator 已自动处理默认值
        points_cost=payload.points_cost,
        points_only=payload.points_only,
        stock=payload.stock,
        sold_count=0,
        status=payload.status,
        sort=payload.sort,
        remark=payload.remark,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok(_product_out(p).model_dump(), "商品创建成功")


@router.get(
    "/products",
    summary="商品列表",
    description="PC 端商品列表，支持按标题搜索、状态筛选、分页。",
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="标题关键词，模糊匹配")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态筛选：on_sale/off_shelf/sold_out")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
) -> dict[str, Any]:
    q = db.query(MallProduct)
    if keyword:
        q = q.filter(MallProduct.title.ilike(f"%{keyword}%"))
    if status_filter:
        q = q.filter(MallProduct.status == status_filter)
    total = q.count()
    products = (
        q.order_by(MallProduct.sort.asc(), MallProduct.create_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ok({"list": [_product_out(p).model_dump() for p in products], "total": total})


@router.get(
    "/products/{product_id}",
    summary="商品详情",
    description="PC 端查询单个商品详情。",
)
def get_product(
    product_id: Annotated[str, Path(description="商品业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    p = db.query(MallProduct).filter(MallProduct.product_id == product_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在")
    return ok(_product_out(p).model_dump())


@router.put(
    "/products/{product_id}",
    summary="修改商品",
    description="PC 端修改商品信息，所有字段均为可选（部分更新）。",
)
def update_product(
    product_id: Annotated[str, Path(description="商品业务 ID")],
    payload: MallProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    p = db.query(MallProduct).filter(MallProduct.product_id == product_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在")

    data = payload.model_dump(exclude_unset=True)
    field_map = {
        "cover_image": "cover_image",
        "cover_video": "cover_video",
        "original_price": "original_price",
        "current_price": "current_price",
        "points_cost": "points_cost",
        "points_only": "points_only",
    }
    for key, value in data.items():
        db_key = field_map.get(key, key)
        setattr(p, db_key, value)

    db.commit()
    db.refresh(p)
    return ok(_product_out(p).model_dump(), "商品已更新")


@router.delete(
    "/products/{product_id}",
    summary="删除商品",
    description="PC 端删除商品。已有订单关联的商品仍可删除，历史订单快照不受影响。",
)
def delete_product(
    product_id: Annotated[str, Path(description="商品业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    p = db.query(MallProduct).filter(MallProduct.product_id == product_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在")
    db.delete(p)
    db.commit()
    return ok(message="商品已删除")


# ---------------------------------------------------------------------------
# 订单管理（PC）
# ---------------------------------------------------------------------------

@router.get(
    "/orders",
    summary="订单列表",
    description=(
        "PC 端订单列表，支持按状态、用户ID、商品ID、关键词筛选。"
        "status 可选值：all(全部) / pending_pay(待支付) / paid(已支付) / shipped(已发货) / completed(已完成) / cancelled(已取消)。"
    ),
)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    order_status: Annotated[str | None, Query(alias="status", description="订单状态")] = None,
    user_id: Annotated[str | None, Query(alias="userId", description="用户ID，精确匹配")] = None,
    product_id: Annotated[str | None, Query(alias="productId", description="商品ID，精确匹配")] = None,
    keyword: Annotated[str | None, Query(description="关键词（商品标题模糊匹配）")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    q = db.query(MallOrder)
    if order_status and order_status != "all":
        q = q.filter(MallOrder.status == order_status)
    if user_id:
        q = q.filter(MallOrder.user_id == user_id)
    if product_id:
        q = q.filter(MallOrder.product_id == product_id)
    if keyword:
        q = q.filter(MallOrder.product_title.ilike(f"%{keyword}%"))
    total = q.count()
    orders = (
        q.order_by(MallOrder.create_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ok({"list": [_order_out(o).model_dump() for o in orders], "total": total})


@router.get(
    "/orders/{order_id}",
    summary="订单详情",
    description="PC 端查询单条订单详情。",
)
def get_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    o = db.query(MallOrder).filter(MallOrder.order_id == order_id).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    return ok(_order_out(o).model_dump())


@router.put(
    "/orders/{order_id}/status",
    summary="修改订单状态",
    description=(
        "PC 端手动修改订单状态。"
        "允许的流转：paid→shipped→completed；任意状态→cancelled。"
        "取消时可传 cancelReason。"
    ),
)
def update_order_status(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    payload: MallOrderStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    o = db.query(MallOrder).filter(MallOrder.order_id == order_id).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")

    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    target = payload.status

    # 状态流转校验
    if target == "shipped" and o.status != "paid":
        raise fail(status.HTTP_400_BAD_REQUEST, "只有已支付订单才能发货")
    if target == "completed" and o.status != "shipped":
        raise fail(status.HTTP_400_BAD_REQUEST, "只有已发货订单才能标记完成")
    if target == "cancelled" and o.status in ("completed",):
        raise fail(status.HTTP_400_BAD_REQUEST, "已完成订单不能取消")

    # 取消时的退款逻辑
    if target == "cancelled":
        # 已支付/已发货订单取消：退还积分 + 恢复库存
        if o.status in ("paid", "shipped") and o.points_used > 0:
            user = db.query(User).filter(User.user_id == o.user_id).first()
            if user is not None:
                award_points(
                    db,
                    user,
                    POINT_TYPE_MALL,
                    o.points_used,  # 正数 = 退还
                    title=f"订单取消退还积分",
                    remark=f"订单号：{o.order_id}，{payload.cancel_reason or '平台取消'}",
                    source_id=o.order_id,
                )
        # 已支付/已发货订单取消：恢复库存
        if o.status in ("paid", "shipped"):
            p = db.query(MallProduct).filter(MallProduct.product_id == o.product_id).first()
            if p is not None:
                p.stock = min(999, p.stock + o.quantity)
                p.sold_count = max(0, (p.sold_count or 0) - o.quantity)
                if p.status == "sold_out" and p.stock > 0:
                    p.status = "on_sale"

    o.status = target
    if target == "paid":
        o.paid_at = now_str
    elif target == "shipped":
        o.shipped_at = now_str
        if payload.express_company:
            o.express_company = payload.express_company
        if payload.express_no:
            o.express_no = payload.express_no
    elif target == "completed":
        o.completed_at = now_str
    elif target == "cancelled":
        o.cancelled_at = now_str
        if payload.cancel_reason:
            o.cancel_reason = payload.cancel_reason

    if payload.remark:
        o.remark = payload.remark

    db.commit()
    db.refresh(o)
    return ok(_order_out(o).model_dump(), f"订单状态已更新为 {ORDER_STATUS_LABELS.get(target, target)}")


# ---------------------------------------------------------------------------
# 支付方式管理
# ---------------------------------------------------------------------------

@router.post(
    "/payment-methods",
    status_code=201,
    summary="新增支付方式",
    description="PC 端新增支付方式，type 字段须全局唯一（如 wechat/alipay/自定义）。",
)
def create_payment_method(
    payload: MallPaymentMethodCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    existing = db.query(MallPaymentMethod).filter(MallPaymentMethod.type == payload.type).first()
    if existing:
        raise fail(status.HTTP_400_BAD_REQUEST, f"支付类型 '{payload.type}' 已存在")

    m = MallPaymentMethod(
        method_id=new_business_id("pay"),
        name=payload.name,
        logo=payload.logo,
        type=payload.type,
        type_value=payload.type_value,
        status=payload.status,
        sort=payload.sort,
        remark=payload.remark,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ok(_method_out(m).model_dump(), "支付方式创建成功")


@router.get(
    "/payment-methods",
    summary="支付方式列表",
    description="PC 端查询所有支付方式，含禁用状态。",
)
def list_payment_methods(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    status_filter: Annotated[str | None, Query(alias="status", description="enabled/disabled")] = None,
) -> dict[str, Any]:
    q = db.query(MallPaymentMethod)
    if status_filter:
        q = q.filter(MallPaymentMethod.status == status_filter)
    methods = q.order_by(MallPaymentMethod.sort.asc(), MallPaymentMethod.create_time.asc()).all()
    return ok({"list": [_method_out(m).model_dump() for m in methods], "total": len(methods)})


@router.put(
    "/payment-methods/{method_id}",
    summary="修改支付方式",
    description="PC 端修改支付方式信息（名称、logo、typeValue、状态、排序等），type 不可修改。",
)
def update_payment_method(
    method_id: Annotated[str, Path(description="支付方式业务 ID")],
    payload: MallPaymentMethodUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    m = db.query(MallPaymentMethod).filter(MallPaymentMethod.method_id == method_id).first()
    if m is None:
        raise fail(status.HTTP_404_NOT_FOUND, "支付方式不存在")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        db_key = "type_value" if key == "type_value" else key
        setattr(m, db_key, value)

    db.commit()
    db.refresh(m)
    return ok(_method_out(m).model_dump(), "支付方式已更新")


@router.delete(
    "/payment-methods/{method_id}",
    summary="删除支付方式",
    description="PC 端删除支付方式。",
)
def delete_payment_method(
    method_id: Annotated[str, Path(description="支付方式业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    m = db.query(MallPaymentMethod).filter(MallPaymentMethod.method_id == method_id).first()
    if m is None:
        raise fail(status.HTTP_404_NOT_FOUND, "支付方式不存在")
    db.delete(m)
    db.commit()
    return ok(message="支付方式已删除")


# ---------------------------------------------------------------------------
# 商城统计看板
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    summary="商城数据统计",
    description=(
        "PC 端商城看板数据。包含各状态订单数量、总销售额（分）、"
        "积分消耗总量、今日新增订单数、商品总数及上架数量。"
    ),
)
def mall_stats(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    # 各状态订单数
    status_counts: dict[str, int] = {}
    for s in ["pending_pay", "paid", "shipped", "completed", "cancelled"]:
        cnt = db.query(func.count(MallOrder.id)).filter(MallOrder.status == s).scalar() or 0
        status_counts[s] = int(cnt)
    total_orders = sum(status_counts.values())

    # 有效订单（已支付/已发货/已完成）的销售额和积分消耗
    valid_statuses = ["paid", "shipped", "completed"]
    revenue: int = int(
        db.query(func.coalesce(func.sum(MallOrder.total_price), 0))
        .filter(MallOrder.status.in_(valid_statuses))
        .scalar() or 0
    )
    points_consumed: int = int(
        db.query(func.coalesce(func.sum(MallOrder.points_used), 0))
        .filter(MallOrder.status.in_(valid_statuses))
        .scalar() or 0
    )

    # 今日新增订单（CST 时区）
    day_start, day_end = cst_day_bounds()
    today_orders: int = int(
        db.query(func.count(MallOrder.id))
        .filter(MallOrder.create_time >= day_start, MallOrder.create_time < day_end)
        .scalar() or 0
    )

    # 商品统计
    total_products: int = int(db.query(func.count(MallProduct.id)).scalar() or 0)
    on_sale_products: int = int(
        db.query(func.count(MallProduct.id))
        .filter(MallProduct.status == "on_sale")
        .scalar() or 0
    )

    return ok(
        {
            "orderStatusCounts": {
                **{ORDER_STATUS_LABELS[k]: v for k, v in status_counts.items()},
                "rawKeys": status_counts,
            },
            "totalOrders": total_orders,
            "todayNewOrders": today_orders,
            "totalRevenue": revenue,          # 单位：分，前端展示时 ÷100 换算成元
            "totalPointsConsumed": points_consumed,
            "totalProducts": total_products,
            "onSaleProducts": on_sale_products,
        }
    )
