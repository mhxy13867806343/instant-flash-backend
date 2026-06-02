from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

_memory_tokens: dict[str, tuple[str, float]] = {}
_redis_client: Any | None = None


def _token_key(subject: str, jti: str) -> str:
    return f"{settings.redis_key_prefix}:auth:token:{subject}:{jti}"


def _ttl_seconds(expires_at: datetime) -> int:
    expires_timestamp = expires_at.astimezone(timezone.utc).timestamp()
    return max(1, int(expires_timestamp - time.time()))


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


def store_access_token(subject: str, jti: str, token_type: str, expires_at: datetime) -> None:
    key = _token_key(subject, jti)
    ttl = _ttl_seconds(expires_at)
    value = json.dumps({"subject": subject, "jti": jti, "type": token_type}, ensure_ascii=False)
    if _use_memory_store():
        _memory_tokens[key] = (value, time.time() + ttl)
        return
    _client().setex(key, ttl, value)


def is_access_token_active(subject: str, jti: str) -> bool:
    key = _token_key(subject, jti)
    if _use_memory_store():
        item = _memory_tokens.get(key)
        if item is None:
            return False
        _, expires_at = item
        if expires_at <= time.time():
            _memory_tokens.pop(key, None)
            return False
        return True
    return bool(_client().exists(key))


def revoke_access_token_state(subject: str, jti: str) -> None:
    key = _token_key(subject, jti)
    if _use_memory_store():
        _memory_tokens.pop(key, None)
        return
    _client().delete(key)
