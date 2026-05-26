from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import DevTokenRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/dev-token", response_model=TokenResponse)
def create_dev_token(payload: DevTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user_id = payload.user_id or new_business_id("usr")
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        user = User(user_id=user_id)
        db.add(user)

    for field in ("openid", "unionid", "phone", "nickname", "avatar"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return TokenResponse(accessToken=create_access_token(user.user_id), userId=user.user_id)

