from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import DevTokenRequest, TokenResponse, WxLoginRequest, WxLoginResponse

router = APIRouter(prefix="/api/auth", tags=["鉴权登录"])


@router.post(
    "/dev-token",
    response_model=TokenResponse,
    summary="开发调试 Token",
    description="开发联调用接口：创建或更新测试用户，并返回 Bearer Token。",
)
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


@router.post(
    "/wx-login",
    response_model=WxLoginResponse,
    summary="微信登录",
    description="用户端微信登录接口。当前实现为本地联调逻辑，会根据 code 生成模拟 openid 并返回 token。",
)
def wx_login(payload: WxLoginRequest, db: Session = Depends(get_db)) -> WxLoginResponse:
    openid = f"mock_openid_{payload.code}"
    user = db.query(User).filter(User.openid == openid).one_or_none()
    if user is None:
        user = User(user_id=new_business_id("usr"), openid=openid)
        db.add(user)

    for field in ("nickname", "avatar", "phone", "gender", "province", "city", "district"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)

    db.commit()
    db.refresh(user)

    token = create_access_token(user.user_id)
    return WxLoginResponse(
        accessToken=token,
        token=token,
        user={
            "userId": user.user_id,
            "openid": user.openid,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "phone": user.phone,
            "gender": user.gender,
        },
    )
