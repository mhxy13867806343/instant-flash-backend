from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.serializers import message_out
from app.db.base import utc_now
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageOut

router = APIRouter(prefix="/api/messages", tags=["用户端消息"])


def ok(data: object = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data}


def notification_item(message: Message) -> dict[str, object | None]:
    return {
        "messageId": message.message_id,
        "title": message.title or "",
        "content": message.content or "",
        "type": message.type,
        "isRead": message.is_read,
        "time": message.create_time,
        "createdAt": message.create_time,
        "updatedAt": message.update_time,
        "postId": message.post_id,
        "commentId": message.comment_id,
        "senderId": message.sender_id,
    }


@router.get(
    "",
    response_model=list[MessageOut],
    summary="消息列表",
    description="获取当前登录用户的消息列表，可按未读筛选并分页。",
)
def list_messages(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    unread_only: Annotated[bool, Query(alias="unreadOnly", description="是否只查询未读消息")] = False,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，兼容 limit/offset 分页")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量，兼容 limit/offset 分页")] = 0,
    page: Annotated[int | None, Query(ge=1, description="页码，兼容 page/pageSize 分页")] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100, description="每页数量，兼容 page/pageSize 分页")] = None,
) -> list[MessageOut]:
    if page is not None:
        limit = page_size or limit
        offset = (page - 1) * limit
    query = db.query(Message).filter(Message.user_id == current_user.user_id)
    if unread_only:
        query = query.filter(Message.is_read.is_(False))
    messages = query.order_by(Message.create_time.desc()).offset(offset).limit(limit).all()
    return [message_out(message) for message in messages]


@router.get(
    "/notifications",
    summary="用户端通知下拉",
    description="用户端消息通知下拉接口，返回未读数量和最近通知列表。",
)
def list_user_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    limit: Annotated[int, Query(ge=1, le=50, description="返回数量")] = 10,
) -> dict[str, object]:
    query = db.query(Message).filter(Message.user_id == current_user.user_id)
    unread_count = query.filter(Message.is_read.is_(False)).count()
    messages = query.order_by(Message.create_time.desc()).limit(limit).all()
    return ok({"unreadCount": unread_count, "list": [notification_item(message) for message in messages]})


@router.put(
    "/read-all",
    summary="用户端消息全部已读",
    description="将当前登录用户的所有消息标记为已读。",
)
def read_all_user_messages(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    db.query(Message).filter(Message.user_id == current_user.user_id, Message.is_read.is_(False)).update(
        {Message.is_read: True, Message.last_time: utc_now()},
        synchronize_session=False,
    )
    db.commit()
    return ok(None, "已全部标记为已读")


@router.put(
    "/{messageId}/read",
    summary="用户端消息已读",
    description="将当前登录用户的单条消息标记为已读。",
)
def read_user_message(
    messageId: Annotated[str, Path(description="消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    message = db.query(Message).filter(Message.user_id == current_user.user_id, Message.message_id == messageId).one_or_none()
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": "消息未找到", "data": {}},
        )
    message.is_read = True
    message.last_time = utc_now()
    db.commit()
    return ok(notification_item(message), "已标记为已读")
