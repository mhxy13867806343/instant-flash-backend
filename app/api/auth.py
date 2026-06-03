from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import bearer_required, get_current_user_required
from app.api.user_identity import (
    mobile_user_id,
    normalize_client_subtype,
    normalize_client_type,
    normalize_phone,
    phone_from_user_id,
    should_use_mobile_user_id,
)
from app.api.utils import new_business_id
from app.core.security import create_access_token, revoke_access_token
from app.db.session import get_db
from app.models.comment import Comment
from app.models.message import Message
from app.models.user import User
from app.schemas.auth import DevTokenRequest, TokenResponse, WxLoginRequest, WxLoginResponse

router = APIRouter(prefix="/api/auth", tags=["鉴权登录"])


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def migrate_mobile_user_id(db: Session, user: User, target_user_id: str) -> User:
    if user.user_id == target_user_id:
        return user

    existing = db.query(User).filter(User.user_id == target_user_id, User.id != user.id).one_or_none()
    if existing is not None:
        return existing

    old_user_id = user.user_id
    user.user_id = target_user_id
    db.flush()
    db.query(Comment).filter(Comment.reply_to_user_id == old_user_id).update({Comment.reply_to_user_id: target_user_id})
    db.query(Message).filter(Message.user_id == old_user_id).update({Message.user_id: target_user_id})
    db.query(Message).filter(Message.sender_id == old_user_id).update({Message.sender_id: target_user_id})
    return user


def infer_mobile_identity(user_id: str | None, phone: str | None, client_type: str | None) -> tuple[str | None, str | None]:
    normalized_phone = normalize_phone(phone) or phone_from_user_id(user_id)
    if should_use_mobile_user_id(user_id, normalized_phone, client_type):
        return mobile_user_id(normalized_phone), normalized_phone
    return user_id, normalized_phone


def phone_login_conditions(phone: str) -> list[object]:
    return [
        User.new_phone == phone,
        User.phone == phone,
        User.user_id == mobile_user_id(phone),
        User.user_id == f"h5-{phone}",
    ]


def resolve_phone_login_user(matches: list[User], phone: str) -> User | None:
    if not matches:
        return None
    new_phone_matches = [user for user in matches if user.new_phone == phone]
    if new_phone_matches:
        return new_phone_matches[0]
    active_matches = [user for user in matches if not user.new_phone]
    if active_matches:
        return active_matches[0]
    return None


@router.post(
    "/logout",
    summary="用户端退出登录",
    description="用户端退出登录接口。后端会删除 Redis 中的 Token 登录状态，前端同时清理本地 Token。",
)
def user_logout(
    _: Annotated[User, Depends(get_current_user_required)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_required)],
) -> dict[str, object]:
    if credentials is not None:
        revoke_access_token(credentials.credentials)
    return {"code": 200, "message": "退出成功", "data": {}}


@router.post(
    "/dev-token",
    response_model=TokenResponse,
    summary="开发调试 Token",
    description="开发联调用接口：创建或更新测试用户，并返回 Bearer Token。",
)
def create_dev_token(payload: DevTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    client_type = normalize_client_type(payload.client_type)
    client_subtype = normalize_client_subtype(payload.client_subtype)
    inferred_user_id, phone = infer_mobile_identity(payload.user_id, payload.phone, client_type)
    user_id = inferred_user_id or new_business_id("usr")
    lookup_conditions = [User.user_id == user_id]
    legacy_phone = phone_from_user_id(payload.user_id)
    if legacy_phone:
        lookup_conditions.append(User.user_id == f"h5-{legacy_phone}")
    if payload.openid:
        lookup_conditions.append(User.openid == payload.openid)
    if payload.unionid:
        lookup_conditions.append(User.unionid == payload.unionid)
    if phone:
        lookup_conditions.extend(phone_login_conditions(phone))

    matched_users = db.query(User).filter(or_(*lookup_conditions)).all()
    if phone:
        resolved_phone_user = resolve_phone_login_user(matched_users, phone)
        if resolved_phone_user is None and not any([payload.user_id, payload.openid, payload.unionid]):
            raise fail(status.HTTP_400_BAD_REQUEST, "该手机号已换绑，请使用新手机号登录")
        if resolved_phone_user is not None:
            matched_users = [resolved_phone_user]
    if len({user.id for user in matched_users}) > 1:
        raise fail(status.HTTP_400_BAD_REQUEST, "调试用户标识冲突，请检查 userId/openid/unionid/phone 是否属于同一用户")

    user = matched_users[0] if matched_users else None
    if user is not None and user.user_id != user_id:
        if phone and phone_from_user_id(user.user_id) == phone:
            user = migrate_mobile_user_id(db, user, user_id)
        elif phone and user.new_phone == phone:
            pass
        else:
            raise fail(status.HTTP_400_BAD_REQUEST, "该 openid/unionid/phone 已绑定其他 userId")

    if user is None:
        user = User(user_id=user_id)
        db.add(user)

    if phone and user.new_phone != phone:
        user.phone = phone
    if client_type:
        user.client_type = client_type
    if client_subtype:
        user.client_subtype = client_subtype

    for field in ("openid", "unionid", "nickname", "avatar", "bio"):
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
    client_type = normalize_client_type(payload.client_type) or "miniprogram"
    client_subtype = normalize_client_subtype(payload.client_subtype) or ("wechat" if client_type == "miniprogram" else None)
    phone = normalize_phone(payload.phone)
    target_user_id = mobile_user_id(phone) if phone else None
    lookup_conditions = [User.openid == openid]
    if phone:
        lookup_conditions.extend(phone_login_conditions(phone))
    matched_users = db.query(User).filter(or_(*lookup_conditions)).all()
    if phone:
        resolved_phone_user = resolve_phone_login_user(matched_users, phone)
        if resolved_phone_user is None and len(matched_users) > 0:
            raise fail(status.HTTP_400_BAD_REQUEST, "该手机号已换绑，请使用新手机号登录")
        if resolved_phone_user is not None:
            matched_users = [resolved_phone_user]
    if len({user.id for user in matched_users}) > 1:
        target_matches = [item for item in matched_users if target_user_id and item.user_id == target_user_id]
        if target_matches:
            user = target_matches[0]
        else:
            raise fail(status.HTTP_400_BAD_REQUEST, "手机号/openid 命中多个用户，请检查登录绑定关系")
    else:
        user = matched_users[0] if matched_users else None
    if user is None:
        user = User(user_id=target_user_id or new_business_id("usr"), openid=openid)
        db.add(user)
    elif target_user_id and user.user_id != target_user_id and user.new_phone != phone:
        user = migrate_mobile_user_id(db, user, target_user_id)

    user.openid = user.openid or openid
    if phone and user.new_phone != phone:
        user.phone = phone
    user.client_type = client_type
    user.client_subtype = client_subtype

    for field in ("nickname", "avatar", "gender", "bio", "province", "city", "district"):
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
            "newPhone": user.new_phone,
            "clientType": user.client_type,
            "clientSubtype": user.client_subtype,
            "gender": user.gender,
            "bio": user.bio,
            "signature": user.bio,
        },
    )
