from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.models.wallet import UserWallet, WalletRecord

WALLET_TYPE_LABELS = {
    "recharge": "充值",
    "consume": "消费",
    "refund": "退款",
    "withdraw": "提现",
    "adjust": "系统调整",
}


def get_or_create_wallet(db: Session, user_id: str) -> UserWallet:
    """获取或延迟初始化用户钱包。"""
    wallet = db.query(UserWallet).filter(UserWallet.user_id == user_id).first()
    if not wallet:
        wallet = UserWallet(
            wallet_id=new_business_id("wlt"),
            user_id=user_id,
            balance=0,
            frozen_balance=0,
            status="normal",
        )
        db.add(wallet)
        db.flush()
    return wallet


def change_wallet_balance(
    db: Session,
    user_id: str,
    type_str: str,
    amount: int,
    title: str,
    remark: str | None = None,
    source_id: str | None = None,
) -> WalletRecord:
    """
    修改用户钱包余额并记录变动明细。
    amount 可以是正数（加款）或负数（扣款）。
    """
    wallet = get_or_create_wallet(db, user_id)
    if wallet.status == "frozen":
        raise ValueError("钱包账户已被冻结")

    if amount < 0 and wallet.balance + amount < 0:
        raise ValueError("钱包余额不足")

    wallet.balance += amount
    direction = "consume" if amount < 0 else "earn"

    record = WalletRecord(
        record_id=new_business_id("wtr"),
        user_id=user_id,
        type=type_str,
        direction=direction,
        change_amount=amount,
        balance_after=wallet.balance,
        title=title,
        remark=remark,
        source_id=source_id,
    )
    db.add(record)
    db.flush()
    return record
