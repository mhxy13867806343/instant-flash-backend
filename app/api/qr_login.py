from __future__ import annotations

import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.core.configs import (
    CLIENT_TYPE_PC,
    QR_CONTENT_SCHEME,
    QR_TTL_SECONDS,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_SCANNED,
)
from app.core.points import grant_daily_login
from app.core.qr_login_store import (
    create_qr_session,
    delete_qr_session,
    get_qr_session,
    update_qr_session,
)
from app.core.response import fail
from app.core.security import create_access_token
from app.db.base import utc_now
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    QrCodeConfirmRequest,
    QrCodeConfirmResponse,
    QrCodeCreateResponse,
    QrCodeScanRequest,
    QrCodeScanResponse,
    QrCodeStatusResponse,
)

router = APIRouter(prefix="/api/auth/qrcode", tags=["扫码登录(PC)"])


def user_payload(user: User) -> dict[str, object | None]:
    return {
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
    }


def _session_by_ticket(qr_id: str, ticket: str) -> dict[str, object]:
    session = get_qr_session(qr_id)
    if session is None:
        raise fail(status.HTTP_400_BAD_REQUEST, "二维码已过期，请刷新后重新扫码")
    if session.get("ticket") != ticket:
        raise fail(status.HTTP_400_BAD_REQUEST, "二维码票据无效")
    return session


@router.post(
    "/create",
    response_model=QrCodeCreateResponse,
    summary="PC 生成登录二维码",
    description=(
        "PC 端（免登录）生成扫码登录二维码。\n"
        "- 二维码有效期固定 120 秒，过期后重新调用本接口即可刷新。\n"
        "- 返回的 content 为二维码承载内容，前端据此渲染二维码图片。\n"
        "- 之后 PC 端通过 /api/auth/qrcode/status 轮询扫码结果。"
    ),
)
def create_qrcode() -> QrCodeCreateResponse:
    qr_id = uuid4().hex
    ticket = uuid4().hex
    create_qr_session(qr_id, ticket)
    content = f"{QR_CONTENT_SCHEME}?ticket={ticket}&qrId={qr_id}"
    return QrCodeCreateResponse(
        qrId=qr_id,
        ticket=ticket,
        content=content,
        expireIn=QR_TTL_SECONDS,
        status=STATUS_PENDING,
    )


@router.get(
    "/status",
    response_model=QrCodeStatusResponse,
    summary="PC 轮询扫码状态",
    description=(
        "PC 端轮询二维码状态。\n"
        "- pending：待扫码；scanned：手机已扫码待确认；confirmed：已确认登录；cancelled：已取消；expired：已过期需刷新。\n"
        "- 当状态为 confirmed 时，本接口会一次性返回 PC 端 accessToken 与用户信息，随后该二维码立即失效。"
    ),
)
def qrcode_status(qr_id: Annotated[str, Query(alias="qrId", description="二维码 ID")]) -> QrCodeStatusResponse:
    session = get_qr_session(qr_id)
    if session is None:
        return QrCodeStatusResponse(qrId=qr_id, status=STATUS_EXPIRED)

    current_status = str(session.get("status") or STATUS_PENDING)
    if current_status != STATUS_CONFIRMED:
        return QrCodeStatusResponse(qrId=qr_id, status=current_status)

    # 已确认：一次性下发 token 后销毁会话，避免二维码被重复使用
    access_token = session.get("access_token")
    user_info_raw = session.get("user_info")
    delete_qr_session(qr_id)
    user_info = None
    if isinstance(user_info_raw, str):
        try:
            user_info = json.loads(user_info_raw)
        except (TypeError, ValueError):
            user_info = None
    elif isinstance(user_info_raw, dict):
        user_info = user_info_raw

    return QrCodeStatusResponse(
        qrId=qr_id,
        status=STATUS_CONFIRMED,
        accessToken=access_token if isinstance(access_token, str) else None,
        token=access_token if isinstance(access_token, str) else None,
        user=user_info,
    )


@router.post(
    "/scan",
    response_model=QrCodeScanResponse,
    summary="手机 App 扫码",
    description=(
        "手机 App 扫描 PC 二维码后调用（需登录，携带 Bearer Token）。\n"
        "- 若 App 未登录，返回 401，前端需引导用户先在 App 内登录。\n"
        "- 校验二维码未过期后，状态由 pending 变为 scanned，等待用户在 App 内确认。"
    ),
)
def qrcode_scan(
    payload: QrCodeScanRequest,
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> QrCodeScanResponse:
    qr_id = payload.qr_id
    session = _session_by_ticket(qr_id, payload.ticket)

    current_status = str(session.get("status") or STATUS_PENDING)
    if current_status == STATUS_CONFIRMED:
        raise fail(status.HTTP_400_BAD_REQUEST, "该二维码已完成登录")
    if current_status == STATUS_CANCELLED:
        raise fail(status.HTTP_400_BAD_REQUEST, "该二维码已取消，请刷新后重新扫码")

    updated = update_qr_session(
        qr_id,
        status=STATUS_SCANNED,
        user_id=current_user.user_id,
    )
    if updated is None:
        raise fail(status.HTTP_400_BAD_REQUEST, "二维码已过期，请刷新后重新扫码")

    return QrCodeScanResponse(qrId=qr_id, status=STATUS_SCANNED, message="扫码成功，请在手机上确认登录")


@router.post(
    "/confirm",
    response_model=QrCodeConfirmResponse,
    summary="手机 App 确认/取消登录",
    description=(
        "手机 App 在扫码后确认或取消 PC 登录（需登录，携带 Bearer Token）。\n"
        "- action=confirm：确认登录，为当前用户签发 PC 端 accessToken，状态变为 confirmed。\n"
        "- action=cancel：取消登录，状态变为 cancelled。\n"
        "- 仅扫码本人可确认，且必须先完成扫码。"
    ),
)
def qrcode_confirm(
    payload: QrCodeConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[Session, Depends(get_db)],
) -> QrCodeConfirmResponse:
    qr_id = payload.qr_id
    session = _session_by_ticket(qr_id, payload.ticket)

    current_status = str(session.get("status") or STATUS_PENDING)
    if current_status == STATUS_PENDING:
        raise fail(status.HTTP_400_BAD_REQUEST, "请先扫码再确认")
    if current_status == STATUS_CONFIRMED:
        raise fail(status.HTTP_400_BAD_REQUEST, "该二维码已完成登录")
    if current_status == STATUS_CANCELLED:
        raise fail(status.HTTP_400_BAD_REQUEST, "该二维码已取消，请刷新后重新扫码")

    # 只能由扫码本人确认
    if session.get("user_id") != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "扫码用户与确认用户不一致")

    if payload.action == "cancel":
        update_qr_session(qr_id, status=STATUS_CANCELLED)
        return QrCodeConfirmResponse(qrId=qr_id, status=STATUS_CANCELLED, message="已取消登录")

    # 确认登录：记录 PC 登录来源并发放每日登录奖励
    current_user.client_type = CLIENT_TYPE_PC
    current_user.last_time = utc_now()
    grant_daily_login(db, current_user)
    db.commit()
    db.refresh(current_user)

    access_token = create_access_token(current_user.user_id)
    updated = update_qr_session(
        qr_id,
        status=STATUS_CONFIRMED,
        access_token=access_token,
        user_info=json.dumps(user_payload(current_user), ensure_ascii=False),
    )
    if updated is None:
        raise fail(status.HTTP_400_BAD_REQUEST, "二维码已过期，请刷新后重新扫码")

    return QrCodeConfirmResponse(qrId=qr_id, status=STATUS_CONFIRMED, message="登录成功")
