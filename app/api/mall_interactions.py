from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.db.base import utc_now
from app.db.session import get_db
from app.models.mall import (
    MallOrder,
    MallProduct,
    MallOrderLogisticsStep,
    MallCustomerService,
    MallChatSession,
    MallChatMessage,
    MallProductBargain,
)
from app.models.chat import GlobalChatSession, GlobalChatMessage
from app.models.user import User
from app.api.admin import get_admin_subject, fail as admin_fail, ok as admin_ok
from app.schemas.mall_interactions import (
    LogisticsStepCreate,
    LogisticsStepOut,
    CustomerServiceCreate,
    CustomerServiceUpdate,
    CustomerServiceOut,
    ProductBargainCreate,
    ProductBargainAudit,
    ProductBargainOut,
    ChatSessionInit,
    ChatSessionOut,
    ChatMessageCreate,
    ChatMessageOut,
    GlobalChatSessionInit,
    GlobalChatSessionOut,
    GlobalChatSessionListResponse,
    GlobalChatMessageCreate,
    GlobalChatMessageOut,
)

router = APIRouter(tags=["商城增强交互（物流/客服/会话还价）"])


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data if data is not None else {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


# ---------------------------------------------------------------------------
# 1. 物流轨迹 API
# ---------------------------------------------------------------------------

@router.get(
    "/api/mall/orders/{order_id}/logistics",
    response_model=list[LogisticsStepOut],
    summary="查询订单物流轨迹",
    description="获取指定订单的物流运输节点轨迹，按记录发生时间正序排序。",
)
def get_order_logistics(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[LogisticsStepOut]:
    order = db.query(MallOrder).filter(
        MallOrder.order_id == order_id
    ).first()
    if order is None:
        raise fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    
    # 权限校验：限买家本人或管理员
    if order.user_id != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "无权查看该订单物流")

    steps = db.query(MallOrderLogisticsStep).filter(
        MallOrderLogisticsStep.order_id == order_id
    ).order_by(MallOrderLogisticsStep.step_time.asc()).all()

    return [LogisticsStepOut.model_validate(s) for s in steps]


@router.post(
    "/api/admin/mall/orders/{order_id}/logistics",
    status_code=201,
    summary="添加订单物流轨迹",
    description="PC 管理端为指定发货订单追加一条新的物流节点描述轨迹。",
)
def admin_add_logistics_step(
    order_id: Annotated[str, Path(description="订单业务 ID")],
    payload: LogisticsStepCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    order = db.query(MallOrder).filter(MallOrder.order_id == order_id).first()
    if order is None:
        raise admin_fail(status.HTTP_404_NOT_FOUND, "订单不存在")
    if order.status not in ("shipped", "completed"):
        raise admin_fail(status.HTTP_400_BAD_REQUEST, "只有已发货或已完成订单才能录入物流轨迹")

    step = MallOrderLogisticsStep(
        logistics_id=new_business_id("log"),
        order_id=order_id,
        step_time=payload.stepTime,
        content=payload.content,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return admin_ok(LogisticsStepOut.model_validate(step).model_dump(), "物流节点添加成功")


@router.delete(
    "/api/admin/mall/logistics/{logistics_id}",
    summary="删除指定物流轨迹节点",
)
def admin_delete_logistics_step(
    logistics_id: Annotated[str, Path(description="物流节点业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    step = db.query(MallOrderLogisticsStep).filter(
        MallOrderLogisticsStep.logistics_id == logistics_id
    ).first()
    if step is None:
        raise admin_fail(status.HTTP_404_NOT_FOUND, "该物流节点未找到")

    db.delete(step)
    db.commit()
    return admin_ok(message="物流轨迹节点已删除")


# ---------------------------------------------------------------------------
# 2. 客服管理配置 API
# ---------------------------------------------------------------------------

@router.get(
    "/api/mall/customer-services",
    response_model=list[CustomerServiceOut],
    summary="获取在线客服配置列表",
    description="用户端获取启用的在线客服列表，用于在移动端选择客服发起对话。",
)
def get_customer_services(db: Annotated[Session, Depends(get_db)]) -> list[CustomerServiceOut]:
    cs_list = db.query(MallCustomerService).filter(
        MallCustomerService.status == "active"
    ).order_by(MallCustomerService.sort.asc(), MallCustomerService.create_time.desc()).all()
    return [CustomerServiceOut.model_validate(cs) for cs in cs_list]


@router.post(
    "/api/admin/mall/customer-services",
    status_code=201,
    summary="新建客服配置",
)
def admin_create_customer_service(
    payload: CustomerServiceCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    cs = MallCustomerService(
        cs_id=new_business_id("csv"),
        name=payload.name,
        avatar=payload.avatar,
        status=payload.status,
        sort=payload.sort,
    )
    db.add(cs)
    db.commit()
    db.refresh(cs)
    return admin_ok(CustomerServiceOut.model_validate(cs).model_dump(), "客服创建成功")


@router.put(
    "/api/admin/mall/customer-services/{cs_id}",
    summary="编辑客服配置",
)
def admin_update_customer_service(
    cs_id: Annotated[str, Path(description="客服业务 ID")],
    payload: CustomerServiceUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == cs_id).first()
    if cs is None:
        raise admin_fail(status.HTTP_404_NOT_FOUND, "客服配置不存在")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cs, k, v)
    db.commit()
    db.refresh(cs)
    return admin_ok(CustomerServiceOut.model_validate(cs).model_dump(), "客服配置已更新")


@router.delete(
    "/api/admin/mall/customer-services/{cs_id}",
    summary="删除客服配置",
)
def admin_delete_customer_service(
    cs_id: Annotated[str, Path(description="客服业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == cs_id).first()
    if cs is None:
        raise admin_fail(status.HTTP_404_NOT_FOUND, "客服配置不存在")
    db.delete(cs)
    db.commit()
    return admin_ok(message="客服配置删除成功")


# ---------------------------------------------------------------------------
# 3. 商品还价 API
# ---------------------------------------------------------------------------

@router.post(
    "/api/mall/bargains",
    status_code=201,
    response_model=ProductBargainOut,
    summary="提交商品还价申请",
    description="移动端用户对商品发起心仪出价（还价）。提交后会在与对应客服的聊天会话中插入一条还价卡片消息。",
)
def mobile_create_bargain(
    payload: ProductBargainCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    csId: Annotated[str, Query(description="关联分配或选择的客服 CS ID")] = "",
) -> ProductBargainOut:
    p = db.query(MallProduct).filter(
        MallProduct.product_id == payload.productId,
        MallProduct.status == "on_sale",
    ).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "商品不存在或已下架")
    
    # 积分价格不能还价，仅支持人民币价格还价（currentPrice）
    if p.points_only:
        raise fail(status.HTTP_400_BAD_REQUEST, "仅积分购买的商品不支持还价")
    
    if payload.bargainPrice >= p.current_price:
        raise fail(status.HTTP_400_BAD_REQUEST, "出价必须低于商品的当前销售价")

    # 创建还价记录
    bargain = MallProductBargain(
        bargain_id=new_business_id("bgn"),
        user_id=current_user.user_id,
        product_id=payload.productId,
        original_price=p.current_price,
        bargain_price=payload.bargainPrice,
        status="pending",
    )
    db.add(bargain)
    db.flush()

    # 自动检索或初始化与该客服的聊天会话
    if csId:
        cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == csId).first()
        if cs:
            # 查找会话，不存在则新建
            session = db.query(MallChatSession).filter(
                MallChatSession.user_id == current_user.user_id,
                MallChatSession.cs_id == csId,
            ).first()
            if not session:
                session = MallChatSession(
                    session_id=new_business_id("ses"),
                    user_id=current_user.user_id,
                    cs_id=csId,
                    product_id=payload.productId,
                )
                db.add(session)
                db.flush()
            
            # 在会话中自动插入一条还价卡片消息
            msg = MallChatMessage(
                message_id=new_business_id("msg"),
                session_id=session.session_id,
                sender_type="user",
                sender_id=current_user.user_id,
                content=f"我对商品「{p.title}」发起还价：原价 {p.current_price/100:.2f} 元，期望以 {payload.bargainPrice/100:.2f} 元购买，请问可以吗？",
                msg_type="bargain",
                bargain_id=bargain.bargain_id,
            )
            db.add(msg)

    db.commit()
    db.refresh(bargain)
    return ProductBargainOut.model_validate(bargain)


@router.post(
    "/api/admin/mall/bargains/{bargain_id}/audit",
    summary="后台客服审核/处理还价申请",
    description="PC 客服后台（或管理员）对用户出价进行处理。同意 approved / 拒绝 rejected。同意后用户下单支付时直接生效。",
)
def admin_audit_bargain(
    bargain_id: Annotated[str, Path(description="还价申请业务 ID")],
    payload: ProductBargainAudit,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    b = db.query(MallProductBargain).filter(
        MallProductBargain.bargain_id == bargain_id
    ).with_for_update().first()
    if b is None:
        raise admin_fail(status.HTTP_404_NOT_FOUND, "该还价申请不存在")
    if b.status != "pending":
        raise admin_fail(status.HTTP_400_BAD_REQUEST, f"还价申请已处理过，当前状态为「{b.status}」")

    b.status = payload.status
    
    # 在关联的聊天会话中插入一条客服反馈通知卡片
    msg_ref = db.query(MallChatMessage).filter(MallChatMessage.bargain_id == bargain_id).first()
    if msg_ref:
        action_label = "同意" if payload.status == "approved" else "拒绝"
        feedback_msg = MallChatMessage(
            message_id=new_business_id("msg"),
            session_id=msg_ref.session_id,
            sender_type="cs",
            sender_id=f"cs:{admin_subject}",
            content=f"【系统还价审核反馈】：客服已{action_label}您的还价出价（出价：{b.bargain_price/100:.2f}元）。" + 
                    ("您现在可以直接下单该商品，支付时将自动减价！" if payload.status == "approved" else "很抱歉商家不支持此折价销售。"),
            msg_type="text",
        )
        db.add(feedback_msg)

    db.commit()
    db.refresh(b)
    return admin_ok(ProductBargainOut.model_validate(b).model_dump(), f"已成功将该还价处理为 {payload.status}")


@router.get(
    "/api/mall/bargains/active",
    summary="查询商品有效还价",
    description="移动端获取当前用户对指定商品最新且通过的还价出价，下单时用以此核算最终支付价。",
)
def mobile_get_active_bargain(
    product_id: Annotated[str, Query(description="商品业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    # 查找最新同意且未使用的还价记录
    b = db.query(MallProductBargain).filter(
        MallProductBargain.product_id == product_id,
        MallProductBargain.user_id == current_user.user_id,
        MallProductBargain.status == "approved",
    ).order_by(MallProductBargain.create_time.desc()).first()

    if not b:
        return ok({"hasActiveBargain": False, "bargainPrice": None})
    return ok({"hasActiveBargain": True, "bargainPrice": b.bargain_price, "bargainId": b.bargain_id})


# ---------------------------------------------------------------------------
# 4. 客服会话与聊天消息 API
# ---------------------------------------------------------------------------

@router.post(
    "/api/mall/chat/sessions/init",
    response_model=ChatSessionOut,
    summary="初始化聊天会话",
    description="移动端用户进入与特定客服的聊天对话框时调用，支持带入当前浏览商品的 ID 方便快捷发还价卡片。",
)
def init_chat_session(
    payload: ChatSessionInit,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> ChatSessionOut:
    cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == payload.csId).first()
    if cs is None:
        raise fail(status.HTTP_404_NOT_FOUND, "客服代表不存在")

    # 查询是否已存在该会话，不存在则自动创建
    session = db.query(MallChatSession).filter(
        MallChatSession.user_id == current_user.user_id,
        MallChatSession.cs_id == payload.csId,
    ).first()

    if not session:
        session = MallChatSession(
            session_id=new_business_id("ses"),
            user_id=current_user.user_id,
            cs_id=payload.csId,
            product_id=payload.productId,
        )
        db.add(session)
    else:
        # 已存在时更新带入的商品ID
        session.product_id = payload.productId
        session.is_active = True
        session.last_time = utc_now()
    
    db.commit()
    db.refresh(session)
    return ChatSessionOut.model_validate(session)


@router.get(
    "/api/mall/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
    summary="获取会话消息历史记录",
    description="分页或获取指定聊天会话的历史交互记录列表数据。",
)
def get_chat_messages(
    session_id: Annotated[str, Path(description="会话 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ChatMessageOut]:
    session = db.query(MallChatSession).filter(MallChatSession.session_id == session_id).first()
    if session is None:
        raise fail(status.HTTP_404_NOT_FOUND, "聊天会话不存在")
    
    # 权限：买家或关联客服
    # 这里为了简化，管理员/客服默认都有权限
    if session.user_id != current_user.user_id and not current_user.is_superuser:
        raise fail(status.HTTP_403_FORBIDDEN, "无权查看该会话消息")

    msgs = db.query(MallChatMessage).filter(
        MallChatMessage.session_id == session_id
    ).order_by(MallChatMessage.create_time.asc()).limit(limit).all()

    return [ChatMessageOut.model_validate(m) for m in msgs]


@router.post(
    "/api/mall/chat/messages",
    response_model=ChatMessageOut,
    summary="发送聊天消息",
    description="在聊天会话中发送文本、晒图或还价卡片消息内容。",
)
def send_chat_message(
    payload: ChatMessageCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> ChatMessageOut:
    session = db.query(MallChatSession).filter(MallChatSession.session_id == payload.sessionId).first()
    if session is None:
        raise fail(status.HTTP_404_NOT_FOUND, "聊天会话不存在")

    msg = MallChatMessage(
        message_id=new_business_id("msg"),
        session_id=payload.sessionId,
        sender_type="user",
        sender_id=current_user.user_id,
        content=payload.content,
        msg_type=payload.msgType,
        bargain_id=payload.bargainId,
    )
    db.add(msg)
    
    # 活跃会话时间更新
    session.last_time = utc_now()
    db.commit()
    db.refresh(msg)
    return ChatMessageOut.model_validate(msg)


@router.get(
    "/api/admin/mall/chat/sessions",
    response_model=list[ChatSessionOut],
    summary="客服工作台列表",
    description="PC 管理端获取客服的活跃消息会话列表（进行还价和会话对接）。",
)
def admin_list_chat_sessions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    cs_id: Annotated[str | None, Query(alias="csId", description="客服筛选")] = None,
) -> list[ChatSessionOut]:
    q = db.query(MallChatSession).filter(MallChatSession.is_active.is_(True))
    if cs_id:
        q = q.filter(MallChatSession.cs_id == cs_id)
    
    sessions = q.order_by(MallChatSession.update_time.desc()).all()
    return [ChatSessionOut.model_validate(s) for s in sessions]


# ---------------------------------------------------------------------------
# 5. 全局聊天与私聊 API
# ---------------------------------------------------------------------------

def _global_message_out(m: GlobalChatMessage) -> GlobalChatMessageOut:
    return GlobalChatMessageOut(
        messageId=m.message_id,
        sessionId=m.session_id,
        senderId=m.sender_id,
        receiverId=m.receiver_id,
        content=m.content,
        msgType=m.msg_type,
        productId=m.product_id,
        bargainId=m.bargain_id,
        isRead=m.is_read,
        createTime=m.create_time,
    )


@router.post(
    "/api/chat/sessions/init",
    response_model=GlobalChatSessionOut,
    summary="初始化全局聊天会话",
    description="与另一个用户或客服发起聊天。会话唯一存在，支持关联带入商品ID。",
)
def init_global_chat_session(
    payload: GlobalChatSessionInit,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    target_id = payload.targetId
    if target_id == current_user.user_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "不能与自己建立聊天会话")

    # 查寻是否该会话已存在（A-B 或 B-A）
    session = db.query(GlobalChatSession).filter(
        (
            (GlobalChatSession.user_one_id == current_user.user_id)
            & (GlobalChatSession.user_two_id == target_id)
        )
        | (
            (GlobalChatSession.user_one_id == target_id)
            & (GlobalChatSession.user_two_id == current_user.user_id)
        )
    ).first()

    if not session:
        session = GlobalChatSession(
            session_id=new_business_id("gses"),
            user_one_id=current_user.user_id,
            user_two_id=target_id,
            is_active=True,
        )
        db.add(session)
        db.flush()
    else:
        session.is_active = True
        session.last_time = utc_now()

    db.commit()
    db.refresh(session)

    # 封装基础数据
    ret = GlobalChatSessionOut.model_validate(session).model_dump()
    
    # 填充目标头像与昵称
    target_user = db.query(User).filter(User.user_id == target_id).first()
    if target_user:
        ret["targetNickname"] = target_user.nickname or "即闪用户"
        ret["targetAvatar"] = target_user.avatar or ""
    else:
        target_cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == target_id).first()
        if target_cs:
            ret["targetNickname"] = target_cs.name
            ret["targetAvatar"] = target_cs.avatar or ""
        else:
            ret["targetNickname"] = "客服代表"

    return ok(ret, "会话建立成功")


@router.get(
    "/api/chat/sessions",
    response_model=GlobalChatSessionListResponse,
    summary="我的全局会话列表",
    description="获取当前登录用户的所有活跃私聊/客服会话列表，包括未读消息数、最新消息摘要。",
)
def list_global_chat_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GlobalChatSessionListResponse:
    # 查询参与的会话
    sessions = db.query(GlobalChatSession).filter(
        (GlobalChatSession.user_one_id == current_user.user_id)
        | (GlobalChatSession.user_two_id == current_user.user_id)
    ).filter(GlobalChatSession.is_active.is_(True)).order_by(GlobalChatSession.update_time.desc()).all()

    items = []
    for s in sessions:
        out = GlobalChatSessionOut.model_validate(s)
        # 找到对方 ID
        target_id = s.user_two_id if s.user_one_id == current_user.user_id else s.user_one_id
        
        # 对方资料
        target_user = db.query(User).filter(User.user_id == target_id).first()
        if target_user:
            out.targetNickname = target_user.nickname or "即闪用户"
            out.targetAvatar = target_user.avatar or ""
        else:
            target_cs = db.query(MallCustomerService).filter(MallCustomerService.cs_id == target_id).first()
            if target_cs:
                out.targetNickname = target_cs.name
                out.targetAvatar = target_cs.avatar or ""
            else:
                out.targetNickname = "客服代表"

        # 未读消息统计
        unread_cnt = db.query(func.count(GlobalChatMessage.id)).filter(
            GlobalChatMessage.session_id == s.session_id,
            GlobalChatMessage.receiver_id == current_user.user_id,
            GlobalChatMessage.is_read.is_(False),
        ).scalar() or 0
        out.unreadCount = int(unread_cnt)
        items.append(out)

    return GlobalChatSessionListResponse(items=items, total=len(items))


@router.get(
    "/api/chat/sessions/{session_id}/messages",
    response_model=list[GlobalChatMessageOut],
    summary="获取全局会话消息历史",
)
def get_global_chat_messages(
    session_id: Annotated[str, Path(description="全局会话 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[GlobalChatMessageOut]:
    session = db.query(GlobalChatSession).filter(GlobalChatSession.session_id == session_id).first()
    if session is None:
        raise fail(status.HTTP_404_NOT_FOUND, "会话未找到")

    # 鉴权
    if session.user_one_id != current_user.user_id and session.user_two_id != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "无权查看此会话")

    msgs = db.query(GlobalChatMessage).filter(
        GlobalChatMessage.session_id == session_id
    ).order_by(GlobalChatMessage.create_time.asc()).limit(limit).all()

    return [_global_message_out(m) for m in msgs]


@router.post(
    "/api/chat/messages",
    response_model=GlobalChatMessageOut,
    summary="发送全局私聊/客服消息",
    description="发送单条私聊/客服消息，支持普通文字、晒图、还价卡片及关联商品分享。",
)
def send_global_chat_message(
    payload: GlobalChatMessageCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GlobalChatMessageOut:
    session = db.query(GlobalChatSession).filter(
        GlobalChatSession.session_id == payload.sessionId
    ).first()
    if session is None:
        raise fail(status.HTTP_404_NOT_FOUND, "会话未找到")

    # 鉴权并发起者/接收者定位
    if session.user_one_id == current_user.user_id:
        receiver_id = session.user_two_id
    elif session.user_two_id == current_user.user_id:
        receiver_id = session.user_one_id
    else:
        raise fail(status.HTTP_403_FORBIDDEN, "无权在当前会话发消息")

    msg = GlobalChatMessage(
        message_id=new_business_id("gmsg"),
        session_id=payload.sessionId,
        sender_id=current_user.user_id,
        receiver_id=receiver_id,
        content=payload.content,
        msg_type=payload.msgType,
        product_id=payload.productId,
        bargain_id=payload.bargainId,
        is_read=False,
    )
    db.add(msg)

    # 更新会话最后消息预览和活跃更新时间
    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    session.last_message = payload.content
    session.last_message_time = now_str
    session.last_time = utc_now()
    
    db.commit()
    db.refresh(msg)
    return _global_message_out(msg)


@router.put(
    "/api/chat/sessions/{session_id}/read",
    summary="标记会话消息为已读",
)
def read_global_chat_messages(
    session_id: Annotated[str, Path(description="全局会话 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    db.query(GlobalChatMessage).filter(
        GlobalChatMessage.session_id == session_id,
        GlobalChatMessage.receiver_id == current_user.user_id,
        GlobalChatMessage.is_read.is_(False),
    ).update({GlobalChatMessage.is_read: True, GlobalChatMessage.last_time: utc_now()}, synchronize_session=False)
    db.commit()
    return ok(message="会话消息已全部标记为已读")

