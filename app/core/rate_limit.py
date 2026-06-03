from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.system_config import AdminAccessRule

_redis_client: Any | None = None
_memory_counters: dict[str, tuple[int, float]] = {}

SKIP_RATE_LIMIT_PREFIXES = (
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
    "/health",
)


@dataclass
class RateLimitResult:
    allowed: bool
    message: str
    current: int = 0
    limit: int = 0
    retry_after: int = 0
    rule_id: str | None = None


def request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client is None:
        return "127.0.0.1"
    return request.client.host or "127.0.0.1"


def should_skip_rate_limit(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in SKIP_RATE_LIMIT_PREFIXES)


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


def _counter_key(ip: str, method: str, path: str) -> str:
    return f"{settings.redis_key_prefix}:rate_limit:{ip}:{method.upper()}:{path}"


def _increment_counter(key: str, window_seconds: int) -> tuple[int, int]:
    now = time.time()
    if _use_memory_store():
        current, expires_at = _memory_counters.get(key, (0, now + window_seconds))
        if expires_at <= now:
            current = 0
            expires_at = now + window_seconds
        current += 1
        _memory_counters[key] = (current, expires_at)
        return current, max(1, int(expires_at - now))
    client = _client()
    current = int(client.incr(key))
    if current == 1:
        client.expire(key, window_seconds)
    ttl = int(client.ttl(key))
    return current, ttl if ttl > 0 else window_seconds


def _matches_value(pattern: str | None, value: str) -> bool:
    if not pattern or pattern == "*":
        return True
    if "*" in pattern:
        return fnmatch.fnmatch(value, pattern)
    return pattern == value


def _matches_path(pattern: str | None, value: str) -> bool:
    if not pattern or pattern == "*":
        return True
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    if "*" in pattern:
        return fnmatch.fnmatch(value, pattern)
    return pattern == value


def _matching_rules(ip: str, method: str, path: str) -> list[AdminAccessRule]:
    db = SessionLocal()
    try:
        rules = db.query(AdminAccessRule).filter(AdminAccessRule.status == "enabled").all()
        return [
            rule
            for rule in rules
            if _matches_value(rule.ip, ip)
            and _matches_value((rule.method or "ALL").upper(), method.upper())
            and _matches_path(rule.path, path)
        ]
    except (OperationalError, ProgrammingError):
        return []
    finally:
        db.close()


def check_rate_limit(request: Request) -> RateLimitResult:
    if not settings.rate_limit_enabled:
        return RateLimitResult(True, "success")
    path = request.url.path
    if should_skip_rate_limit(path):
        return RateLimitResult(True, "success")

    ip = request_ip(request)
    method = request.method.upper()
    rules = _matching_rules(ip, method, path)
    whitelist_rule = next((rule for rule in rules if rule.rule_type == "whitelist"), None)
    if whitelist_rule is not None:
        return RateLimitResult(True, "白名单放行", rule_id=whitelist_rule.rule_id)
    blacklist_rule = next((rule for rule in rules if rule.rule_type == "blacklist"), None)
    if blacklist_rule is not None:
        return RateLimitResult(False, "当前 IP 或接口已被黑名单拦截", rule_id=blacklist_rule.rule_id)

    limit = settings.rate_limit_max_requests
    window_seconds = settings.rate_limit_window_seconds
    key = _counter_key(ip, method, path)
    try:
        current, retry_after = _increment_counter(key, window_seconds)
    except Exception:
        return RateLimitResult(True, "限流存储不可用，临时放行")
    if current > limit:
        return RateLimitResult(False, f"访问过于频繁，请 {retry_after} 秒后再试", current=current, limit=limit, retry_after=retry_after)
    return RateLimitResult(True, "success", current=current, limit=limit, retry_after=retry_after)
