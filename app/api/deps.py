from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.account_deactivation import expire_deactivation_if_due
from app.db.session import get_db
from app.models.user import User

bearer_required = HTTPBearer(auto_error=False)
bearer_optional = HTTPBearer(auto_error=False)


def _user_from_credentials(
    db: Session, credentials: HTTPAuthorizationCredentials | None
) -> User | None:
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        return None

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None

    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        return None
    if user.deactivation_status == "deactivated" or not user.is_active:
        return None

    if expire_deactivation_if_due(user):
        db.commit()
        return None

    return user


def get_current_user_required(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_required)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "未登录，请先登录", "data": {}},
        )
    user = _user_from_credentials(db, credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "登录已过期或无效", "data": {}},
        )
    return user


def get_current_user_optional(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_optional)],
) -> User | None:
    return _user_from_credentials(db, credentials)
