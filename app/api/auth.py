from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import DevTokenRequest, TokenResponse, WxLoginRequest, WxLoginResponse

router = APIRouter(prefix="/api/auth", tags=["鉴权登录"])


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


@router.post(
    "/logout",
    summary="用户端退出登录",
    description="用户端退出登录接口。JWT 为无状态 Token，后端返回成功，前端清理本地 Token 即可。",
)
def user_logout(_: User = Depends(get_current_user_required)) -> dict[str, object]:
    return {"code": 200, "message": "退出成功", "data": {}}


@router.post(
    "/dev-token",
    response_model=TokenResponse,
    summary="开发调试 Token",
    description="开发联调用接口：创建或更新测试用户，并返回 Bearer Token。",
)
def create_dev_token(payload: DevTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user_id = payload.user_id or new_business_id("usr")
    lookup_conditions = [User.user_id == user_id]
    if payload.openid:
        lookup_conditions.append(User.openid == payload.openid)
    if payload.unionid:
        lookup_conditions.append(User.unionid == payload.unionid)
    if payload.phone:
        lookup_conditions.append(User.phone == payload.phone)

    matched_users = db.query(User).filter(or_(*lookup_conditions)).all()
    if len({user.id for user in matched_users}) > 1:
        raise fail(status.HTTP_400_BAD_REQUEST, "调试用户标识冲突，请检查 userId/openid/unionid/phone 是否属于同一用户")

    user = matched_users[0] if matched_users else None
    if user is not None and user.user_id != user_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "该 openid/unionid/phone 已绑定其他 userId")

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
