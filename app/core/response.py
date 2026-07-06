"""统一响应工具。

集中管理成功 / 失败响应的构造，替代各 API 模块内重复定义的 ok() / fail()。
- ok：构造统一成功响应体 {"code": 200, "message": ..., "data": ...}
- fail：构造统一失败 HTTPException，抛出后由全局异常处理器序列化
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.configs import CODE_SUCCESS, MESSAGE_SUCCESS


def ok(data: Any = None, message: str = MESSAGE_SUCCESS) -> dict[str, Any]:
    """构造统一成功响应。data 为 None 时统一返回空对象 {}。"""
    return {"code": CODE_SUCCESS, "message": message, "data": {} if data is None else data}


def fail(status_code: int, message: str) -> HTTPException:
    """构造统一失败响应（抛出用）。"""
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )
