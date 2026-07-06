from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.admin import fail, get_admin_subject, ok
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import WalletRecord, UserWallet
from app.schemas.wallet import WalletAdjustRequest, WalletRecordOut, WalletRecordListResponse, PAY_METHOD_LABELS
from app.core.wallet import get_or_create_wallet, change_wallet_balance, WALLET_TYPE_LABELS

router = APIRouter(prefix="/api/admin/wallet", tags=["后台管理"])


class WalletStatusPayload(BaseModel):
    status: str = Field(pattern="^(normal|frozen)$", description="normal 正常，frozen 冻结")


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


@router.post(
    "/users/{user_id}/adjust",
    summary="手动调整用户钱包余额",
    description="管理员手动增加（正数）或扣减（负数）用户的钱包可用余额。扣减余额时用户钱包必须有足够的可用资金。",
)
def admin_adjust_wallet(
    user_id: Annotated[str, Path(description="目标用户 ID")],
    payload: WalletAdjustRequest,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")

    action = "增加" if payload.amount > 0 else "扣减"
    try:
        record = change_wallet_balance(
            db,
            user_id,
            "adjust",
            payload.amount,
            title=f"管理员手动{action}余额",
            remark=payload.remark,
            source_id=f"admin:{admin_subject}",
        )
        db.commit()
    except ValueError as e:
        raise fail(status.HTTP_400_BAD_REQUEST, str(e))

    return ok(
        {
            "userId": user_id,
            "adjustAmount": payload.amount,
            "balanceBefore": record.balance_after - payload.amount,
            "balanceAfter": record.balance_after,
            "recordId": record.record_id,
            "remark": payload.remark,
        },
        f"钱包余额{action}成功",
    )


@router.get(
    "/users/{user_id}/records",
    response_model=WalletRecordListResponse,
    summary="查看用户账单流水",
    description="管理员查看指定用户的钱包变动明细记录流水。",
)
def admin_list_wallet_records(
    user_id: Annotated[str, Path(description="目标用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WalletRecordListResponse:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")

    # 懒加载初始化
    get_or_create_wallet(db, user_id)
    db.commit()

    q = db.query(WalletRecord).filter(WalletRecord.user_id == user_id)
    if type_filter:
        q = q.filter(WalletRecord.type == type_filter)

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


@router.put(
    "/users/{user_id}/status",
    summary="冻结或解冻用户钱包",
    description="管理员将指定用户钱包状态设置为冻结（frozen，禁止所有交易）或恢复正常（normal）。",
)
def admin_update_wallet_status(
    user_id: Annotated[str, Path(description="目标用户 ID")],
    payload: WalletStatusPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    w = get_or_create_wallet(db, user_id)
    w.status = payload.status
    db.commit()
    db.refresh(w)
    return ok(
        {
            "userId": user_id,
            "status": w.status,
            "balance": w.balance,
        },
        f"钱包状态已成功设为 {payload.status}",
    )
