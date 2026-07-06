"""分页通用工具。

集中封装重复的分页逻辑，避免各接口反复书写 offset/limit 计算。
- page_offset：计算偏移量 (page - 1) * limit，适用于需自定义收尾（如 .subquery()）的场景
- paginate：对已排序的 query 应用分页并返回列表
- paginate_with_total：返回 (当前页列表, 总条数)
- resolve_limit_offset：兼容 page/pageSize 与 limit/offset 两套分页参数
"""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


def page_offset(page: int, limit: int) -> int:
    """根据页码与每页数量计算偏移量。"""
    return (page - 1) * limit


def paginate(query: Any, page: int, limit: int) -> list[Any]:
    """对已排序的 query 应用页码分页，返回当前页列表。"""
    return query.offset(page_offset(page, limit)).limit(limit).all()


def paginate_with_total(query: Any, page: int, limit: int) -> tuple[list[Any], int]:
    """对 query 统计总数并返回当前页列表，返回 (items, total)。"""
    total = query.count()
    items = query.offset(page_offset(page, limit)).limit(limit).all()
    return items, total


def resolve_limit_offset(
    page: int | None,
    page_size: int | None,
    limit: int,
    offset: int,
) -> tuple[int, int]:
    """兼容两套分页参数：

    - 传了 page 时，按 page/pageSize 计算，pageSize 缺省时沿用 limit；
    - 未传 page 时，沿用传入的 limit/offset。

    返回最终生效的 (limit, offset)。
    """
    if page is not None:
        limit = page_size or limit
        offset = page_offset(page, limit)
    return limit, offset
