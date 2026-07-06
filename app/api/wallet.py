from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.db.base import utc_now
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import WalletRecord
from app.schemas.wallet import (
    UserWalletOut,
    WalletRecordOut,
    WalletRecordListResponse,
    WalletRechargeRequest,
    PAY_METHOD_LABELS,
)
from app.core.wallet import get_or_create_wallet, change_wallet_balance, WALLET_TYPE_LABELS

router = APIRouter(prefix="/api/wallet", tags=["用户端钱包"])


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data if data is not None else {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def _record_out(r: WalletRecord) -> WalletRecordOut:
    return WalletRecordOut(
        recordId=r.record_id,
        userId=r.user_id,
        type=r.type,
        typeLabel=WALLET_TYPE_LABELS.get(r.type, r.type),
        direction=r.direction,
        changeAmount=r.change_amount,
        balanceAfter=r.balance_after,
        title=r.title,
        remark=r.remark,
        sourceId=r.source_id,
        payMethod=r.pay_method,
        payMethodLabel=PAY_METHOD_LABELS.get(r.pay_method or "", None),
        createTime=r.create_time,
    )


# ---------------------------------------------------------------------------
# 钱包概览
# ---------------------------------------------------------------------------

@router.get(
    "/overview",
    summary="钱包账户概览",
    description="获取当前登录用户的钱包余额、冻结金额、账户状态及历史收支总计数据。",
)
def wallet_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    w = get_or_create_wallet(db, current_user.user_id)

    total_recharged = db.query(func.coalesce(func.sum(WalletRecord.change_amount), 0)).filter(
        WalletRecord.user_id == current_user.user_id,
        WalletRecord.type == "recharge"
    ).scalar() or 0

    total_spent = db.query(func.coalesce(func.sum(WalletRecord.change_amount), 0)).filter(
        WalletRecord.user_id == current_user.user_id,
        WalletRecord.type == "consume"
    ).scalar() or 0

    return ok(
        {
            "walletId": w.wallet_id,
            "userId": w.user_id,
            "balance": w.balance,
            "frozenBalance": w.frozen_balance,
            "status": w.status,
            "totalRecharged": total_recharged,
            "totalSpent": abs(total_spent),
            "createTime": w.create_time,
            "updateTime": w.update_time,
        }
    )


# ---------------------------------------------------------------------------
# 充值明细列表
# ---------------------------------------------------------------------------

@router.get(
    "/records",
    response_model=WalletRecordListResponse,
    summary="账单变动明细",
    description="分页查询当前登录用户的钱包收支记录账单明细。支持筛选类型 type 和方向 direction。最新的排在最前面。",
)
def wallet_records(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    type_filter: Annotated[str | None, Query(alias="type", description="变动类型：recharge/consume/refund/withdraw/adjust")] = None,
    direction: Annotated[str | None, Query(pattern="^(earn|consume)$", description="方向：earn 收入，consume 支出")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WalletRecordListResponse:
    q = db.query(WalletRecord).filter(WalletRecord.user_id == current_user.user_id)
    if type_filter:
        q = q.filter(WalletRecord.type == type_filter)
    if direction:
        q = q.filter(WalletRecord.direction == direction)

    total = q.count()
    records = (
        q.order_by(WalletRecord.create_time.desc(), WalletRecord.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return WalletRecordListResponse(
        items=[_record_out(r) for r in records],
        total=total,
    )


# ---------------------------------------------------------------------------
# 充值
# ---------------------------------------------------------------------------

@router.post(
    "/recharge",
    summary="钱包余额充值",
    description=(
        "用户为自己钱包进行余额充值。\n"
        "- 充值金额范围：最低 0.01 元（1 分）至最高 999999.00 元（99999900 分）\n"
        "- 默认支持支付宝 (alipay) 和微信 (wechat) 支付方式，也支持 bank_card、apple_pay 或 other\n"
    ),
)
def wallet_recharge(
    payload: WalletRechargeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    try:
        pay_label = PAY_METHOD_LABELS.get(payload.payMethod, payload.payMethod)
        record = change_wallet_balance(
            db,
            current_user.user_id,
            "recharge",
            payload.amount,
            title=f"余额充值（{pay_label}）",
            remark=payload.remark,
            pay_method=payload.payMethod,
        )
        db.commit()
    except ValueError as e:
        raise fail(status.HTTP_400_BAD_REQUEST, str(e))

    return ok(_record_out(record).model_dump(), "充值成功")


# ---------------------------------------------------------------------------
# 删除单条记录
# ---------------------------------------------------------------------------

@router.delete(
    "/records/{record_id}",
    summary="删除单条账单记录",
    description="删除当前登录用户的一条钱包变动记录。仅删除记录，不影响钱包余额。",
)
def delete_wallet_record(
    record_id: Annotated[str, Path(description="账单记录业务 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    record = db.query(WalletRecord).filter(
        WalletRecord.record_id == record_id,
        WalletRecord.user_id == current_user.user_id,
    ).first()
    if record is None:
        raise fail(status.HTTP_404_NOT_FOUND, "账单记录不存在")

    db.delete(record)
    db.commit()
    return ok(message="账单记录已删除")


# ---------------------------------------------------------------------------
# 清空全部记录
# ---------------------------------------------------------------------------

@router.delete(
    "/records",
    summary="清空全部账单记录",
    description="清空当前登录用户的所有钱包变动记录。仅删除记录数据，不影响钱包余额。",
)
def clear_all_wallet_records(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    deleted = db.query(WalletRecord).filter(
        WalletRecord.user_id == current_user.user_id
    ).delete(synchronize_session=False)
    db.commit()
    return ok({"deletedCount": deleted}, f"已清空全部 {deleted} 条账单记录")
