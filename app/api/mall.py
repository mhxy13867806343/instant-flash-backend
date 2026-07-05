from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.points import POINT_TYPE_MALL, award_points
from app.core.wallet import get_or_create_wallet, change_wallet_balance
from app.db.base import utc_now
from app.db.session import get_db
from app.models.mall import MallOrder, MallPaymentMethod, MallProduct, MallSetting, MallProductComment
from app.models.user import User
from app.schemas.mall import (
    MallOrderCreate,
    MallOrderOut,
    MallOrderListResponse,
    MallPaymentMethodOut,
    MallProductOut,
    MallProductListResponse,
    ORDER_STATUS_LABELS,
    MallProductCommentCreate,
    MallProductCommentOut,
    MallProductCommentListResponse,
)

router = APIRouter(prefix="/api/mall", tags=["用户端商城"])

MALL_SETTING_ID = 1
# 待支付订单超时时间（分钟）
ORDER_EXPIRE_MINUTES = 30


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
        expireAt=o.expire_at,
        userRemark=o.user_remark,
        receiverName=o.receiver_name,
        receiverPhone=o.receiver_phone,
        receiverAddress=o.receiver_address,
        expressCompany=o.express_company,
        expressNo=o.express_no,
        shareToken=o.share_token,
        isCommented=o.is_commented,
        createTime=o.create_time,
        updateTime=o.update_time,
    )


def _auto_cancel_if_expired(db: Session, order: MallOrder) -> MallOrder:
    """
    对 pending_pay 状态的订单检查是否超时，超时则自动取消。
    注意：此函数会在需要时 commit，调用方无需再 commit。
    """
    if (
        order.status == "pending_pay"
        and order.expire_at is not None
        and order.expire_at < utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    ):
        now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
        order.status = "cancelled"
        order.cancelled_at = now_str
        order.cancel_reason = "订单超时自动取消"
        db.commit()
        db.refresh(order)
    return order


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
# 下单（#9 行锁防超卖）
# ---------------------------------------------------------------------------

@router.post(
    "/orders",
    status_code=201,
    summary="下单",
    description=(
        "移动端用户下单。"
        "积分开关开启时 payType 必须为 points；"
        "使用积分支付时会校验用户积分是否足够；"
        "库存使用数据库行锁（SELECT FOR UPDATE）防止超卖；"
        "下单成功后订单状态为 pending_pay（待支付），30分钟内未支付自动取消。"
        "需调用 /orders/{orderId}/pay 完成支付。"
    ),
)
def mobile_create_order(
    payload: MallOrderCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    setting = _get_setting(db)

    # ✅ #9 行锁：防止并发超卖，锁定商品行直到事务结束
    p = (
        db.query(MallProduct)
        .filter(
            MallProduct.product_id == payload.product_id,
            MallProduct.status == "on_sale",
        )
        .with_for_update()
        .first()
    )
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在或已下架")

    # 库存校验（行锁已获取，此时库存值可信）
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
            raise fail(
                status.HTTP_400_BAD_REQUEST,
                f"积分不足，需要 {points_needed} 积分，当前余额 {current_user.points or 0}",
            )
        unit_price = 0  # 纯积分支付，价格为 0
    elif pay_type == "wallet":
        # 钱包支付：校验余额是否足够
        wallet = get_or_create_wallet(db, current_user.user_id)
        total_cost = unit_price * payload.quantity
        if wallet.balance < total_cost:
            raise fail(
                status.HTTP_400_BAD_REQUEST,
                f"余额不足，需要 {total_cost/100:.2f} 元，当前余额 {wallet.balance/100:.2f} 元",
            )

    total = unit_price * payload.quantity

    # 计算超时时间（UTC）
    expire_str = (utc_now() + timedelta(minutes=ORDER_EXPIRE_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")

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
        expire_at=expire_str,
        user_remark=payload.user_remark,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        receiver_address=payload.receiver_address,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return ok(_order_out(order).model_dump(), "下单成功")


# ---------------------------------------------------------------------------
# 支付（#10 幂等 + 行锁）
# ---------------------------------------------------------------------------

@router.post(
    "/orders/{order_id}/pay",
    summary="发起支付",
    description=(
        "移动端对待支付订单发起支付。"
        "使用数据库行锁（SELECT FOR UPDATE）保证支付幂等，防止重复扣积分。"
        "超时订单会先自动取消再返回错误。"
        "积分支付会立即扣除用户积分并扣减库存；"
        "其他支付方式（微信/支付宝等）直接标记为已支付（模拟，未接入真实 SDK）。"
    ),
)
def mobile_pay_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    # ✅ #10 行锁：并发支付只有一个能通过，另一个看到状态非 pending_pay 后直接返回幂等结果
    o = (
        db.query(MallOrder)
        .filter(
            MallOrder.order_id == order_id,
            MallOrder.user_id == current_user.user_id,
        )
        .with_for_update()
        .first()
    )
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")

    # ✅ 幂等：已支付则直接返回成功
    if o.status == "paid":
        return ok(_order_out(o).model_dump(), "支付成功（重复请求）")

    # ✅ #5 超时自动取消
    if o.status == "pending_pay" and o.expire_at and o.expire_at < utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"):
        now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
        o.status = "cancelled"
        o.cancelled_at = now_str
        o.cancel_reason = "订单超时自动取消"
        db.commit()
        raise fail(status.HTTP_400_BAD_REQUEST, "订单已超时，已自动取消")

    if o.status != "pending_pay":
        raise fail(
            status.HTTP_400_BAD_REQUEST,
            f"订单当前状态为「{ORDER_STATUS_LABELS.get(o.status, o.status)}」，无法支付",
        )

    # 积分扣除
    if o.points_used > 0:
        if (current_user.points or 0) < o.points_used:
            raise fail(
                status.HTTP_400_BAD_REQUEST,
                f"积分不足，需要 {o.points_used} 积分，当前余额 {current_user.points or 0}",
            )
        award_points(
            db,
            current_user,
            POINT_TYPE_MALL,  # ✅ #2 专用商城积分类型，明细显示"商城兑换"
            -o.points_used,
            title=f"兑换商品：{o.product_title}",
            source_id=o.order_id,
        )
    elif o.pay_type == "wallet":
        # 钱包余额扣除
        try:
            change_wallet_balance(
                db,
                current_user.user_id,
                "consume",
                -o.total_price,
                title=f"购买商品：{o.product_title}",
                source_id=o.order_id,
            )
        except ValueError as e:
            raise fail(status.HTTP_400_BAD_REQUEST, str(e))

    # 扣减库存 & 增加销量（行锁下操作，安全）
    p = (
        db.query(MallProduct)
        .filter(MallProduct.product_id == o.product_id)
        .with_for_update()
        .first()
    )
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
        "pending_pay 中超时的订单会自动标记为 cancelled 再返回。"
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
    # ✅ #5 批量检查超时，自动取消过期待支付订单
    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    need_commit = False
    for o in orders:
        if o.status == "pending_pay" and o.expire_at and o.expire_at < now_str:
            o.status = "cancelled"
            o.cancelled_at = now_str
            o.cancel_reason = "订单超时自动取消"
            need_commit = True
    if need_commit:
        db.commit()

    return MallOrderListResponse(items=[_order_out(o) for o in orders], total=total)


@router.get(
    "/orders/{order_id}",
    response_model=MallOrderOut,
    summary="订单详情",
    description="移动端查询当前用户的单条订单详情，pending_pay 超时订单自动取消后返回。",
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
    # ✅ #5 超时自动取消
    o = _auto_cancel_if_expired(db, o)
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
    ).with_for_update().first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if o.status != "pending_pay":
        raise fail(
            status.HTTP_400_BAD_REQUEST,
            f"当前状态「{ORDER_STATUS_LABELS.get(o.status, o.status)}」的订单不能取消",
        )

    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    o.status = "cancelled"
    o.cancelled_at = now_str
    o.cancel_reason = "用户主动取消"
    db.commit()
    db.refresh(o)
    return ok(_order_out(o).model_dump(), "订单已取消")


# ---------------------------------------------------------------------------
# 确认收货
# ---------------------------------------------------------------------------

@router.post(
    "/orders/{order_id}/confirm",
    summary="确认收货",
    description="移动端确认已收货，只有已发货（shipped）状态的订单才可以确认收货，操作后状态流转为已完成（completed）。",
)
def mobile_confirm_receipt(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    o = db.query(MallOrder).filter(
        MallOrder.order_id == order_id,
        MallOrder.user_id == current_user.user_id,
    ).with_for_update().first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if o.status != "shipped":
        raise fail(
            status.HTTP_400_BAD_REQUEST,
            f"订单当前状态为「{ORDER_STATUS_LABELS.get(o.status, o.status)}」，无法确认收货",
        )

    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    o.status = "completed"
    o.completed_at = now_str
    db.commit()
    db.refresh(o)
    return ok(_order_out(o).model_dump(), "确认收货成功")


# ---------------------------------------------------------------------------
# 订单分享功能
# ---------------------------------------------------------------------------

def mask_name(name: str | None) -> str | None:
    if not name:
        return name
    if len(name) <= 1:
        return name
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    if len(phone) >= 11:
        return phone[:3] + "****" + phone[-4:]
    return phone[:2] + "***" + phone[-2:]


def mask_address(address: str | None) -> str | None:
    if not address:
        return address
    # 保留省/市/区等前部信息，打码后部具体地址
    if len(address) > 8:
        return address[:8] + "******"
    return address[:3] + "******"


@router.post(
    "/orders/{order_id}/share",
    summary="生成订单分享链接",
    description="生成用于订单公开分享的 Token 令牌。每个订单的分享 Token 全局唯一。",
)
def mobile_share_order(
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

    # 若未生成过 share_token，则在此生成并持久化
    if not o.share_token:
        # 循环确保唯一性
        while True:
            candidate = new_business_id("shr")
            collision = db.query(MallOrder.id).filter(MallOrder.share_token == candidate).first()
            if not collision:
                o.share_token = candidate
                break
        db.commit()
        db.refresh(o)

    # 可在此生成完整的分享跳转链接格式，如：https://h5.instantflash.com/order-share?token=xxx
    share_link = f"/pages/mall/order-share?token={o.share_token}"

    return ok(
        {
            "orderId": o.order_id,
            "shareToken": o.share_token,
            "shareLink": share_link,
            "shareText": f"【即闪积分商城】我购买了「{o.product_title}」，快来帮我看看订单进度吧！链接: {share_link}",
        },
        "分享凭证生成成功",
    )


from app.schemas.mall import MallOrderSharedOut

@router.get(
    "/orders/share/{share_token}",
    response_model=MallOrderSharedOut,
    summary="查看被分享的订单",
    description="无需登录，通过分享 Token 查看订单状态，所有收货人敏感数据（姓名、手机、地址）均已打码脱敏保护隐私。",
)
def mobile_get_shared_order(
    share_token: Annotated[str, Path(description="分享 Token 令牌")],
    db: Annotated[Session, Depends(get_db)],
) -> MallOrderSharedOut:
    o = db.query(MallOrder).filter(MallOrder.share_token == share_token).first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "分享的订单不存在或已被删除")

    # 自动处理待支付超时订单的流转
    o = _auto_cancel_if_expired(db, o)

    return MallOrderSharedOut(
        orderId=o.order_id,
        productId=o.product_id,
        productTitle=o.product_title,
        productImage=o.product_image,
        quantity=o.quantity,
        unitPrice=o.unit_price,
        totalPrice=o.total_price,
        pointsUsed=o.points_used,
        status=o.status,
        statusLabel=ORDER_STATUS_LABELS.get(o.status, o.status),
        createTime=o.create_time,
        
        # 脱敏数据处理
        receiverName=mask_name(o.receiver_name),
        receiverPhone=mask_phone(o.receiver_phone),
        receiverAddress=mask_address(o.receiver_address),
        
        # 物流公开信息
        expressCompany=o.express_company,
        expressNo=o.express_no,
    )


# ---------------------------------------------------------------------------
# 商品评价与订单关联接口 (用户端)
# ---------------------------------------------------------------------------

def _comment_out(c: MallProductComment) -> MallProductCommentOut:
    return MallProductCommentOut(
        commentId=c.comment_id,
        orderId=c.order_id,
        productId=c.product_id,
        userId=c.user_id,
        nickname=c.nickname or "即闪用户",
        avatar=c.avatar or "",
        rating=c.rating,
        content=c.content,
        images=c.images or [],
        status=c.status,
        createTime=c.create_time,
    )


@router.post(
    "/orders/{order_id}/comment",
    status_code=201,
    summary="评价订单/商品",
    description="对已完成的订单发起评价。每个订单只允许评价一次，支持 1-5 星级以及最多 9 张晒图。",
)
def mobile_comment_order(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    payload: MallProductCommentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    # 查找并锁定订单行
    o = db.query(MallOrder).filter(
        MallOrder.order_id == order_id,
        MallOrder.user_id == current_user.user_id,
    ).with_for_update().first()
    if o is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if o.status != "completed":
        raise fail(
            status.HTTP_400_BAD_REQUEST,
            f"订单当前状态为「{ORDER_STATUS_LABELS.get(o.status, o.status)}」，只有已完成订单才能发表评价",
        )
    if o.is_commented:
        raise fail(status.HTTP_400_BAD_REQUEST, "该订单已评价过，不能重复评价")

    comment = MallProductComment(
        comment_id=new_business_id("cmt"),
        order_id=o.order_id,
        product_id=o.product_id,
        user_id=current_user.user_id,
        nickname=current_user.nickname,
        avatar=current_user.avatar,
        rating=payload.rating,
        content=payload.content,
        images=payload.images,
        status="approved",  # 默认通过，后台可隐藏
    )
    db.add(comment)
    
    # 标记订单已评价
    o.is_commented = True
    db.commit()
    db.refresh(comment)
    
    return ok(_comment_out(comment).model_dump(), "发表评价成功")


@router.get(
    "/products/{product_id}/comments",
    response_model=MallProductCommentListResponse,
    summary="查看商品评价列表",
    description="分页获取指定商品的评价列表（仅返回状态为 approved 的公开评论）。",
)
def mobile_list_product_comments(
    product_id: Annotated[str, Path(description="商品业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> MallProductCommentListResponse:
    q = db.query(MallProductComment).filter(
        MallProductComment.product_id == product_id,
        MallProductComment.status == "approved",
    )
    total = q.count()
    comments = (
        q.order_by(MallProductComment.create_time.desc(), MallProductComment.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return MallProductCommentListResponse(
        items=[_comment_out(c) for c in comments],
        total=total,
    )



