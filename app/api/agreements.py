from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.admin_agreement import AdminAgreement

router = APIRouter(prefix="/api/agreements", tags=["用户端协议"])
legacy_router = APIRouter(prefix="/api/agreement", tags=["用户端协议"])
user_router = APIRouter(prefix="/api/user/agreements", tags=["用户端协议"])

DEFAULT_AGREEMENTS = {
    "privacy": {
        "title": "隐私协议",
        "content": "<h2>即闪隐私政策</h2><p>请在后台编辑最新隐私政策内容。</p>",
    },
    "user": {
        "title": "用户协议",
        "content": "<h2>即闪用户协议</h2><p>请在后台编辑最新用户协议内容。</p>",
    },
}


def ok(data: object = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data or {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def format_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def get_or_create_agreement(db: Session, agreement_type: str) -> AdminAgreement:
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = db.query(AdminAgreement).filter(AdminAgreement.type == agreement_type).one_or_none()
    if agreement is not None:
        return agreement
    agreement = AdminAgreement(
        type=agreement_type,
        content=DEFAULT_AGREEMENTS[agreement_type]["content"],
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


def agreement_item(agreement: AdminAgreement) -> dict[str, Any]:
    default = DEFAULT_AGREEMENTS[agreement.type]
    return {
        "type": agreement.type,
        "agreementType": agreement.type,
        "title": default["title"],
        "content": agreement.content,
        "updatedAt": format_time(agreement.update_time),
        "createdAt": format_time(agreement.create_time),
    }


def get_user_agreement(
    agreementType: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    agreement = get_or_create_agreement(db, agreementType)
    return ok(agreement_item(agreement))


router.get(
    "/{agreementType}",
    summary="用户端协议详情",
    description="用户端公开读取后台维护的协议内容。agreementType 支持 privacy 或 user。",
)(get_user_agreement)

legacy_router.get(
    "/{agreementType}",
    include_in_schema=False,
)(get_user_agreement)

user_router.get(
    "/{agreementType}",
    include_in_schema=False,
)(get_user_agreement)
