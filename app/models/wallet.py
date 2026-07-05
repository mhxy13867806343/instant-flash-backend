from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserWallet(TimestampMixin, Base):
    """用户钱包表。"""

    __tablename__ = "user_wallets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 账户余额（分），默认 0
    frozen_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 冻结金额（分）
    status: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)  # normal 正常 / frozen 冻结


class WalletRecord(TimestampMixin, Base):
    """钱包变动明细记录表。"""

    __tablename__ = "wallet_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # recharge 充值 / consume 消费 / refund 退款 / withdraw 提现 / adjust 系统调整
    direction: Mapped[str] = mapped_column(
        String(16), default="earn", nullable=False
    )  # earn 收入 / consume 支出
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 变动金额（分，正或负）
    balance_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 变动后余额（分）
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )  # 关联来源业务ID，如订单号、充值订单号
