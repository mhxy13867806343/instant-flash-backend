from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import settings

# 二维码有效期（秒）
QR_TTL_SECONDS = 120

# 状态常量
STATUS_PENDING = "pending"      # 已生成，等待扫码
STATUS_SCANNED = "scanned"      # 已被 App 扫码，等待确认
STATUS_CONFIRMED = "confirmed"  # 已确认登录
STATUS_CANCELLED = "cancelled"  # 已取消
STATUS_EXPIRED = "expired"      # 已过期（Redis key 消失时的兜底返回值）

_memory_store: dict[str, tuple[str, float]] = {}
_redis_client: Any | None = None


def _qr_key(qr_id: str) -> str:
    return f"{settings.redis_key_prefix}:auth:qrlogin:{qr_id}"


def _use_memory_store() -> bool:
    return settings.redis_url == "memory://"


def _client() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_client


def _memory_get(key: str) -> str | None:
    item = _memory_store.get(key)
    if item is None:
        return None
    value, expires_at = item
    if expires_at <= time.time():
        _memory_store.pop(key, None)
        return None
    return value


def create_qr_session(qr_id: str, ticket: str) -> dict[str, Any]:
    """创建一条扫码登录会话，TTL 固定 120s。"""
    data: dict[str, Any] = {
        "qr_id": qr_id,
        "ticket": ticket,
        "status": STATUS_PENDING,
        "user_id": None,
        "access_token": None,
        "created_at": int(time.time()),
    }
    _save(qr_id, data, ttl=QR_TTL_SECONDS)
    return data


def get_qr_session(qr_id: str) -> dict[str, Any] | None:
    key = _qr_key(qr_id)
    if _use_memory_store():
        raw = _memory_get(key)
    else:
        raw = _client().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _remaining_ttl(qr_id: str) -> int:
    key = _qr_key(qr_id)
    if _use_memory_store():
        item = _memory_store.get(key)
        if item is None:
            return QR_TTL_SECONDS
        _, expires_at = item
        return max(1, int(expires_at - time.time()))
    ttl = _client().ttl(key)
    return ttl if isinstance(ttl, int) and ttl > 0 else QR_TTL_SECONDS


def _save(qr_id: str, data: dict[str, Any], ttl: int | None = None) -> None:
    key = _qr_key(qr_id)
    value = json.dumps(data, ensure_ascii=False)
    if ttl is None:
        ttl = _remaining_ttl(qr_id)
    ttl = max(1, ttl)
    if _use_memory_store():
        _memory_store[key] = (value, time.time() + ttl)
        return
    _client().setex(key, ttl, value)


def update_qr_session(qr_id: str, **fields: Any) -> dict[str, Any] | None:
    """在保留剩余 TTL 的前提下更新会话字段。"""
    data = get_qr_session(qr_id)
    if data is None:
        return None
    data.update(fields)
    _save(qr_id, data)
    return data


def delete_qr_session(qr_id: str) -> None:
    key = _qr_key(qr_id)
    if _use_memory_store():
        _memory_store.pop(key, None)
        return
    _client().delete(key)
