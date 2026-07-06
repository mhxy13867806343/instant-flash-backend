"""数据库查询通用工具。

集中封装重复的聚合查询写法，避免各处反复书写 func.coalesce(func.sum(...))。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session


def sum_column(db: Session, column: Any, *filters: Any) -> int:
    """对某列求和，NULL 视为 0，返回 int。

    用法：sum_column(db, WalletRecord.change_amount, WalletRecord.user_id == uid)
    可传入任意数量的过滤条件，等价于 .filter(*filters)。
    """
    query = db.query(func.coalesce(func.sum(column), 0))
    if filters:
        query = query.filter(*filters)
    return int(query.scalar() or 0)
