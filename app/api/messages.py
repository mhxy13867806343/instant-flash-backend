from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.serializers import message_out
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageOut

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("", response_model=list[MessageOut])
def list_messages(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    unread_only: Annotated[bool, Query(alias="unreadOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100)] = None,
) -> list[MessageOut]:
    if page is not None:
        limit = page_size or limit
        offset = (page - 1) * limit
    query = db.query(Message).filter(Message.user_id == current_user.user_id)
    if unread_only:
        query = query.filter(Message.is_read.is_(False))
    messages = query.order_by(Message.create_time.desc()).offset(offset).limit(limit).all()
    return [message_out(message) for message in messages]
