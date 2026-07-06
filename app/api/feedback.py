from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.api.utils import new_business_id
from app.core.response import fail, ok
from app.db.session import get_db
from app.models.system_config import AdminFeedbackField, AdminFeedbackFormConfig, FeedbackSubmission
from app.models.user import User

router = APIRouter(prefix="/api/feedback", tags=["用户端反馈"])

DEFAULT_FEEDBACK_CONFIG_ID = "default"


class FeedbackSubmitPayload(BaseModel):
    phone: str | None = Field(default=None, max_length=32, title="手机号码", description="反馈人手机号码")
    title: str | None = Field(default=None, max_length=128, title="反馈标题", description="反馈标题或菜单名称")
    content: str | None = Field(default=None, title="反馈内容", description="反馈详细内容")
    data: dict[str, Any] = Field(default_factory=dict, title="动态字段数据", description="动态表单字段提交值")


def field_item(field: AdminFeedbackField) -> dict[str, Any]:
    return {
        "fieldId": field.field_id,
        "fieldKey": field.field_key,
        "label": field.label,
        "type": field.type,
        "placeholder": field.placeholder or "",
        "required": field.required,
        "options": field.options or [],
        "sort": field.sort,
        "status": field.status,
        "isDefault": field.is_default,
        "remark": field.remark or "",
    }


def feedback_form_payload(db: Session) -> dict[str, Any]:
    config = db.query(AdminFeedbackFormConfig).filter(AdminFeedbackFormConfig.config_id == DEFAULT_FEEDBACK_CONFIG_ID).one_or_none()
    if config is None or config.status != "enabled":
        raise fail(status.HTTP_404_NOT_FOUND, "反馈表单未启用")
    fields = (
        db.query(AdminFeedbackField)
        .filter(AdminFeedbackField.form_id == config.config_id, AdminFeedbackField.status == "enabled")
        .order_by(AdminFeedbackField.sort.asc(), AdminFeedbackField.create_time.asc())
        .all()
    )
    return {
        "configId": config.config_id,
        "title": config.title,
        "menuTitle": config.menu_title,
        "description": config.description or "",
        "submitButtonText": config.submit_button_text,
        "successMessage": config.success_message,
        "fields": [field_item(field) for field in fields],
    }


def merged_feedback_data(payload: FeedbackSubmitPayload) -> dict[str, Any]:
    data = dict(payload.data or {})
    if payload.phone is not None:
        data["phone"] = payload.phone
    if payload.title is not None:
        data["title"] = payload.title
    if payload.content is not None:
        data["content"] = payload.content
    return data


def validate_required_fields(fields: list[AdminFeedbackField], data: dict[str, Any]) -> None:
    missing = []
    for field in fields:
        if not field.required:
            continue
        value = data.get(field.field_key)
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            missing.append(field.label)
    if missing:
        raise fail(status.HTTP_400_BAD_REQUEST, f"请填写：{', '.join(missing)}")


@router.get("/form", summary="反馈动态表单", description="用户端读取后台配置的反馈动态表单字段。")
@router.get("/config", include_in_schema=False)
def get_feedback_form(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    return ok(feedback_form_payload(db))


@router.post("", summary="提交反馈", description="用户端按动态表单提交反馈。phone/title/content 可以直接传，也可以放在 data 中。")
def submit_feedback(
    payload: FeedbackSubmitPayload,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> dict[str, object]:
    config = db.query(AdminFeedbackFormConfig).filter(AdminFeedbackFormConfig.config_id == DEFAULT_FEEDBACK_CONFIG_ID).one_or_none()
    if config is None or config.status != "enabled":
        raise fail(status.HTTP_404_NOT_FOUND, "反馈表单未启用")
    fields = (
        db.query(AdminFeedbackField)
        .filter(AdminFeedbackField.form_id == config.config_id, AdminFeedbackField.status == "enabled")
        .order_by(AdminFeedbackField.sort.asc(), AdminFeedbackField.create_time.asc())
        .all()
    )
    data = merged_feedback_data(payload)
    validate_required_fields(fields, data)
    phone = str(data.get("phone") or "").strip() or None
    title = str(data.get("title") or "").strip() or None
    content = str(data.get("content") or "").strip()
    if not content:
        raise fail(status.HTTP_400_BAD_REQUEST, "反馈内容不能为空")
    feedback = FeedbackSubmission(
        feedback_id=new_business_id("fb"),
        user_id=current_user.user_id if current_user else None,
        phone=phone,
        title=title,
        content=content,
        payload=data,
        status="pending",
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return ok(
        {
            "feedbackId": feedback.feedback_id,
            "status": feedback.status,
            "successMessage": config.success_message,
        },
        config.success_message,
    )
