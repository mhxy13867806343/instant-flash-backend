from __future__ import annotations

from datetime import datetime, timezone

from app.core.configs import DEACTIVATION_WAIT_DAYS, MOBILE_CLIENT_TYPES
from app.db.base import utc_now
from app.models.user import User

__all__ = [
    "DEACTIVATION_WAIT_DAYS",
    "MOBILE_CLIENT_TYPES",
    "is_mobile_account",
    "deactivation_is_due",
    "mark_deactivated",
    "expire_deactivation_if_due",
]


def is_mobile_account(user: User) -> bool:
    return user.client_type in MOBILE_CLIENT_TYPES


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def deactivation_is_due(user: User, now: datetime | None = None) -> bool:
    if user.deactivation_status != "pending" or user.deactivation_end_time is None:
        return False
    return _as_utc(now or utc_now()) >= _as_utc(user.deactivation_end_time)


def mark_deactivated(user: User) -> None:
    user.deactivation_status = "deactivated"
    user.is_active = False


def expire_deactivation_if_due(user: User, now: datetime | None = None) -> bool:
    if not deactivation_is_due(user, now):
        return False
    mark_deactivated(user)
    return True
