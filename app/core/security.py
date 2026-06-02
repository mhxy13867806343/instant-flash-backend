from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings
from app.core.token_store import is_access_token_active, revoke_access_token_state, store_access_token


def create_access_token(subject: str, expires_delta: timedelta | None = None, token_type: str = "user") -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    jti = uuid4().hex
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "jti": jti, "typ": token_type}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    store_access_token(subject, jti, token_type, expire)
    return token


def decode_access_token_payload(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    subject = payload.get("sub")
    jti = payload.get("jti")
    if not isinstance(subject, str) or not subject:
        return None
    if not isinstance(jti, str) or not jti:
        return None
    if not is_access_token_active(subject, jti):
        return None
    return payload


def decode_access_token(token: str) -> str | None:
    payload = decode_access_token_payload(token)
    if payload is None:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def revoke_access_token(token: str) -> bool:
    payload = decode_access_token_payload(token)
    if payload is None:
        return False
    subject = payload.get("sub")
    jti = payload.get("jti")
    if not isinstance(subject, str) or not isinstance(jti, str):
        return False
    revoke_access_token_state(subject, jti)
    return True
