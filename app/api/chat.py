from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.chat_ws import manager
from app.db.base import utc_now
from app.db.session import get_db
from app.models.chat import (
    GlobalChatSession,
    GlobalChatMessage,
    ChatGroup,
    ChatGroupMember,
    ChatGroupMessage,
    ChatMessageFavorite,
)
from app.models.user import User, UserFollow
from app.schemas.chat import (
    PrivateMessageCreate,
    PrivateMessageOut,
    GroupCreate,
    GroupUpdate,
    GroupOut,
    GroupMemberOut,
    GroupInvite,
    GroupMessageCreate,
    GroupMessageOut,
    MessageForward,
    MessageFavoriteOut,
    MessageRecall,
    JoinByLinkPayload,
)

router = APIRouter(prefix="/api/chat", tags=["聊天系统"])


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data if data is not None else {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def _private_msg_out(m: GlobalChatMessage) -> PrivateMessageOut:
    return PrivateMessageOut(
        messageId=m.message_id,
        sessionId=m.session_id,
        senderId=m.sender_id,
        receiverId=m.receiver_id,
        content=m.content,
        msgType=m.msg_type,
        productId=m.product_id,
        bargainId=m.bargain_id,
        mediaUrl=m.media_url,
        thumbnailUrl=m.thumbnail_url,
        fileName=m.file_name,
        fileSize=m.file_size,
        duration=m.duration,
        replyToId=m.reply_to_id,
        forwardFromId=m.forward_from_id,
        isRead=m.is_read,
        isRecalled=m.is_recalled,
        createTime=m.create_time,
    )


# ===================================================================
#  一、私聊增强 (替代旧的 /api/chat/messages 路由)
# ===================================================================

@router.post(
    "/messages/send",
    response_model=PrivateMessageOut,
    summary="发送私聊消息",
    description="在私聊会话中发送消息，支持文本、图片、视频、语音、文件、商品卡片、转发和位置等类型。",
)
async def send_private_message(
    payload: PrivateMessageCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PrivateMessageOut:
    session = db.query(GlobalChatSession).filter(
        GlobalChatSession.session_id == payload.sessionId
    ).first()
    if session is None:
        raise fail(status.HTTP_404_NOT_FOUND, "会话未找到")

    if session.user_one_id == current_user.user_id:
        receiver_id = session.user_two_id
    elif session.user_two_id == current_user.user_id:
        receiver_id = session.user_one_id
    else:
        raise fail(status.HTTP_403_FORBIDDEN, "无权在当前会话发消息")

    # 陌生人限制校验
    is_following = db.query(UserFollow).filter(
        UserFollow.user_id == current_user.user_id,
        UserFollow.following_id == receiver_id,
    ).first() is not None
    is_followed = db.query(UserFollow).filter(
        UserFollow.user_id == receiver_id,
        UserFollow.following_id == current_user.user_id,
    ).first() is not None

    if not is_following and not is_followed:
        # 陌生人关系，校验发送数量
        sent_count = db.query(GlobalChatMessage).filter(
            GlobalChatMessage.session_id == payload.sessionId,
            GlobalChatMessage.sender_id == current_user.user_id,
            GlobalChatMessage.is_recalled.is_(False),
        ).count()
        if sent_count >= 1:
            raise fail(status.HTTP_400_BAD_REQUEST, "对方与您并非关注/粉丝关系，陌生人私聊最多只能发送一条消息")

    msg = GlobalChatMessage(
        message_id=new_business_id("gmsg"),
        session_id=payload.sessionId,
        sender_id=current_user.user_id,
        receiver_id=receiver_id,
        content=payload.content,
        msg_type=payload.msgType,
        product_id=payload.productId,
        bargain_id=payload.bargainId,
        media_url=payload.mediaUrl,
        thumbnail_url=payload.thumbnailUrl,
        file_name=payload.fileName,
        file_size=payload.fileSize,
        duration=payload.duration,
        reply_to_id=payload.replyToId,
        is_read=False,
        is_recalled=False,
    )
    db.add(msg)

    now_str = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    preview = payload.content[:50]
    if payload.msgType == "image":
        preview = "[图片]"
    elif payload.msgType == "video":
        preview = "[视频]"
    elif payload.msgType == "voice":
        preview = "[语音]"
    elif payload.msgType == "file":
        preview = f"[文件] {payload.fileName or ''}"
    elif payload.msgType == "location":
        preview = "[位置]"
    session.last_message = preview
    session.last_message_time = now_str
    session.last_time = utc_now()

    db.commit()
    db.refresh(msg)
    
    out = _private_msg_out(msg)
    await manager.send_private_message(current_user.user_id, receiver_id, out.model_dump(mode="json"))
    return out


@router.delete(
    "/messages/{message_id}",
    summary="删除私聊消息",
    description="删除一条自己发送的私聊消息记录（仅发送者可删除）。",
)
def delete_private_message(
    message_id: Annotated[str, Path(description="消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    msg = db.query(GlobalChatMessage).filter(
        GlobalChatMessage.message_id == message_id,
    ).first()
    if msg is None:
        raise fail(status.HTTP_404_NOT_FOUND, "消息不存在")
    if msg.sender_id != current_user.user_id and msg.receiver_id != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "无权删除此消息")
    db.delete(msg)
    db.commit()
    return ok(message="消息已删除")


# ===================================================================
#  二、消息撤回
# ===================================================================

@router.post(
    "/messages/{message_id}/recall",
    summary="撤回消息",
    description="撤回一条自己发送的消息（私聊或群聊，发送后 2 分钟以内可撤回）。",
)
async def recall_message(
    message_id: Annotated[str, Path(description="消息 ID")],
    payload: MessageRecall,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    if payload.messageType == "private":
        msg = db.query(GlobalChatMessage).filter(GlobalChatMessage.message_id == message_id).first()
    else:
        msg = db.query(ChatGroupMessage).filter(ChatGroupMessage.message_id == message_id).first()

    if msg is None:
        raise fail(status.HTTP_404_NOT_FOUND, "消息不存在")
    if msg.sender_id != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "只能撤回自己发送的消息")
    if msg.is_recalled:
        raise fail(status.HTTP_400_BAD_REQUEST, "该消息已经撤回")

    # 2 分钟内可撤回
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    msg_time = msg.create_time if hasattr(msg.create_time, 'tzinfo') and msg.create_time.tzinfo else msg.create_time.replace(tzinfo=timezone.utc)
    if (now - msg_time).total_seconds() > 120:
        raise fail(status.HTTP_400_BAD_REQUEST, "超过 2 分钟无法撤回消息")

    msg.is_recalled = True
    msg.content = "该消息已撤回"
    db.commit()

    # WebSocket 广播撤回事件
    if payload.messageType == "private":
        await manager.broadcast_system_event(
            [msg.sender_id, msg.receiver_id],
            "message_recall",
            {"messageId": message_id, "messageType": "private", "sessionId": msg.session_id}
        )
    else:
        members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == msg.group_id).all()
        member_ids = [m.user_id for m in members]
        await manager.broadcast_system_event(
            member_ids,
            "message_recall",
            {"messageId": message_id, "messageType": "group", "groupId": msg.group_id}
        )

    return ok(message="消息已撤回")


# ===================================================================
#  三、消息转发（逐条/合并）
# ===================================================================

@router.post(
    "/messages/forward",
    summary="转发消息",
    description="支持逐条转发和合并转发。可转发到私聊会话或群聊。最多可选 20 条消息。",
)
async def forward_messages(
    payload: MessageForward,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    # 获取原始消息
    private_msgs = db.query(GlobalChatMessage).filter(
        GlobalChatMessage.message_id.in_(payload.messageIds)
    ).all()
    group_msgs = db.query(ChatGroupMessage).filter(
        ChatGroupMessage.message_id.in_(payload.messageIds)
    ).all()
    all_msgs = [(m, "private") for m in private_msgs] + [(m, "group") for m in group_msgs]

    if not all_msgs:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到要转发的消息")

    forwarded = []
    created_private_msgs = []
    created_group_msgs = []
    receiver_id = None

    if payload.mergeForward:
        # 合并转发：生成一条聚合消息
        lines = []
        for m, _ in all_msgs:
            sender = db.query(User).filter(User.user_id == m.sender_id).first()
            name = (sender.nickname if sender else m.sender_id) or m.sender_id
            lines.append(f"{name}: {m.content}")
        merged_content = "\n".join(lines)

        if payload.targetType == "private":
            session = db.query(GlobalChatSession).filter(GlobalChatSession.session_id == payload.targetId).first()
            if not session:
                raise fail(status.HTTP_404_NOT_FOUND, "目标会话不存在")
            receiver_id = session.user_two_id if session.user_one_id == current_user.user_id else session.user_one_id
            msg = GlobalChatMessage(
                message_id=new_business_id("gmsg"),
                session_id=payload.targetId,
                sender_id=current_user.user_id,
                receiver_id=receiver_id,
                content=merged_content,
                msg_type="forward",
                is_read=False,
                is_recalled=False,
            )
            db.add(msg)
            created_private_msgs.append(msg)
            forwarded.append(msg.message_id)
            session.last_message = "[合并转发]"
            session.last_message_time = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            group = db.query(ChatGroup).filter(ChatGroup.group_id == payload.targetId, ChatGroup.status == "active").first()
            if not group:
                raise fail(status.HTTP_404_NOT_FOUND, "目标群聊不存在")
            msg = ChatGroupMessage(
                message_id=new_business_id("grpm"),
                group_id=payload.targetId,
                sender_id=current_user.user_id,
                content=merged_content,
                msg_type="forward",
                is_recalled=False,
            )
            db.add(msg)
            created_group_msgs.append(msg)
            forwarded.append(msg.message_id)
            group.last_message = "[合并转发]"
            group.last_message_time = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        # 逐条转发
        for orig, _ in all_msgs:
            if payload.targetType == "private":
                session = db.query(GlobalChatSession).filter(GlobalChatSession.session_id == payload.targetId).first()
                if not session:
                    raise fail(status.HTTP_404_NOT_FOUND, "目标会话不存在")
                receiver_id = session.user_two_id if session.user_one_id == current_user.user_id else session.user_one_id
                msg = GlobalChatMessage(
                    message_id=new_business_id("gmsg"),
                    session_id=payload.targetId,
                    sender_id=current_user.user_id,
                    receiver_id=receiver_id,
                    content=orig.content,
                    msg_type=orig.msg_type,
                    media_url=getattr(orig, "media_url", None),
                    thumbnail_url=getattr(orig, "thumbnail_url", None),
                    file_name=getattr(orig, "file_name", None),
                    file_size=getattr(orig, "file_size", None),
                    duration=getattr(orig, "duration", None),
                    forward_from_id=orig.message_id,
                    is_read=False,
                    is_recalled=False,
                )
                db.add(msg)
                created_private_msgs.append(msg)
                forwarded.append(msg.message_id)
            else:
                group = db.query(ChatGroup).filter(ChatGroup.group_id == payload.targetId, ChatGroup.status == "active").first()
                if not group:
                    raise fail(status.HTTP_404_NOT_FOUND, "目标群聊不存在")
                msg = ChatGroupMessage(
                    message_id=new_business_id("grpm"),
                    group_id=payload.targetId,
                    sender_id=current_user.user_id,
                    content=orig.content,
                    msg_type=orig.msg_type,
                    media_url=getattr(orig, "media_url", None),
                    thumbnail_url=getattr(orig, "thumbnail_url", None),
                    file_name=getattr(orig, "file_name", None),
                    file_size=getattr(orig, "file_size", None),
                    duration=getattr(orig, "duration", None),
                    forward_from_id=orig.message_id,
                    is_recalled=False,
                )
                db.add(msg)
                created_group_msgs.append(msg)
                forwarded.append(msg.message_id)

    db.commit()

    # WebSocket 推送
    if payload.targetType == "private" and receiver_id:
        for pm in created_private_msgs:
            db.refresh(pm)
            await manager.send_private_message(
                current_user.user_id,
                receiver_id,
                _private_msg_out(pm).model_dump(mode="json")
            )
    elif payload.targetType == "group":
        members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == payload.targetId).all()
        member_ids = [m.user_id for m in members]
        for gm in created_group_msgs:
            db.refresh(gm)
            out = GroupMessageOut.model_validate(gm)
            out.senderName = current_user.nickname
            out.senderAvatar = current_user.avatar
            await manager.broadcast_to_group(payload.targetId, member_ids, out.model_dump(mode="json"))

    return ok({"forwardedCount": len(forwarded), "messageIds": forwarded}, "转发成功")


# ===================================================================
#  四、消息收藏
# ===================================================================

@router.post(
    "/messages/{message_id}/favorite",
    summary="收藏消息",
    description="将一条私聊或群聊消息加入收藏列表，支持分类归档，表情最多收藏 5024 个。",
)
def favorite_message(
    message_id: Annotated[str, Path(description="消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    source_type: Annotated[str, Query(alias="sourceType", pattern="^(private|group)$")] = "private",
    category: Annotated[str, Query(pattern="^(text|image|video|file|emoji|link|other)$")] = "text",
) -> dict[str, Any]:
    if source_type == "private":
        msg = db.query(GlobalChatMessage).filter(GlobalChatMessage.message_id == message_id).first()
    else:
        msg = db.query(ChatGroupMessage).filter(ChatGroupMessage.message_id == message_id).first()
    if msg is None:
        raise fail(status.HTTP_404_NOT_FOUND, "消息不存在")

    # 查重
    exists = db.query(ChatMessageFavorite).filter(
        ChatMessageFavorite.user_id == current_user.user_id,
        ChatMessageFavorite.source_message_id == message_id,
    ).first()
    if exists:
        raise fail(status.HTTP_400_BAD_REQUEST, "该消息已收藏")

    # 表情限制校验
    if category == "emoji":
        emoji_count = db.query(ChatMessageFavorite).filter(
            ChatMessageFavorite.user_id == current_user.user_id,
            ChatMessageFavorite.category == "emoji",
        ).count()
        if emoji_count >= 5024:
            raise fail(status.HTTP_400_BAD_REQUEST, "表情收藏数量已达上限(最大5024个)")

    sender = db.query(User).filter(User.user_id == msg.sender_id).first()
    fav = ChatMessageFavorite(
        favorite_id=new_business_id("fav"),
        user_id=current_user.user_id,
        source_type=source_type,
        source_message_id=message_id,
        content=msg.content,
        msg_type=msg.msg_type,
        category=category,
        media_url=getattr(msg, "media_url", None),
        sender_id=msg.sender_id,
        sender_name=sender.nickname if sender else None,
    )
    db.add(fav)
    db.commit()
    return ok(message="已收藏")


@router.get(
    "/favorites",
    response_model=list[MessageFavoriteOut],
    summary="我的收藏消息列表",
    description="获取我的收藏消息，支持按分类（text/image/video/file/emoji/link/other）筛选，支持分页。",
)
def list_favorites(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    category: Annotated[str | None, Query(pattern="^(text|image|video|file|emoji|link|other)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[MessageFavoriteOut]:
    query = db.query(ChatMessageFavorite).filter(
        ChatMessageFavorite.user_id == current_user.user_id
    )
    if category is not None:
        query = query.filter(ChatMessageFavorite.category == category)
        
    favs = query.order_by(
        ChatMessageFavorite.create_time.desc()
    ).offset((page - 1) * limit).limit(limit).all()
    return [MessageFavoriteOut.model_validate(f) for f in favs]


@router.delete(
    "/favorites/{favorite_id}",
    summary="取消收藏",
)
def delete_favorite(
    favorite_id: Annotated[str, Path(description="收藏记录 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    fav = db.query(ChatMessageFavorite).filter(
        ChatMessageFavorite.favorite_id == favorite_id,
        ChatMessageFavorite.user_id == current_user.user_id,
    ).first()
    if fav is None:
        raise fail(status.HTTP_404_NOT_FOUND, "收藏记录不存在")
    db.delete(fav)
    db.commit()
    return ok(message="已取消收藏")


# ===================================================================
#  五、群聊管理
# ===================================================================

@router.post(
    "/groups",
    response_model=GroupOut,
    summary="创建群聊",
    description="创建一个新群聊，创建者自动成为群主。可在创建时邀请初始成员。",
)
async def create_group(
    payload: GroupCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GroupOut:
    group = ChatGroup(
        group_id=new_business_id("grp"),
        name=payload.name,
        avatar=payload.avatar,
        owner_id=current_user.user_id,
        member_count=1,
        status="active",
    )
    db.add(group)
    db.flush()

    # 群主自动加入
    owner_member = ChatGroupMember(
        group_id=group.group_id,
        user_id=current_user.user_id,
        role="owner",
    )
    db.add(owner_member)

    # 邀请初始成员
    added = 0
    invited_uids = []
    for uid in payload.memberIds:
        if uid == current_user.user_id:
            continue
        user = db.query(User).filter(User.user_id == uid).first()
        if user:
            member = ChatGroupMember(
                group_id=group.group_id,
                user_id=uid,
                role="member",
            )
            db.add(member)
            added += 1
            invited_uids.append(uid)

    group.member_count = 1 + added

    # 发送系统消息
    names = []
    for uid in payload.memberIds[:5]:
        u = db.query(User).filter(User.user_id == uid).first()
        if u:
            names.append(u.nickname or uid)
    sys_msg = ChatGroupMessage(
        message_id=new_business_id("grpm"),
        group_id=group.group_id,
        sender_id=current_user.user_id,
        content=f"{current_user.nickname or current_user.user_id} 创建了群聊" + (f"，并邀请了 {', '.join(names)} 等 {added} 人加入" if added else ""),
        msg_type="system",
        is_recalled=False,
    )
    db.add(sys_msg)

    db.commit()
    db.refresh(group)

    # WS 实时广播群创建通知给被邀请者与创建者
    all_invited_ids = invited_uids + [current_user.user_id]
    await manager.broadcast_system_event(
        all_invited_ids,
        "group_created",
        {"groupId": group.group_id, "groupName": group.name, "avatar": group.avatar}
    )

    return GroupOut.model_validate(group)


@router.get(
    "/groups",
    response_model=list[GroupOut],
    summary="我的群聊列表",
)
def list_groups(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[GroupOut]:
    member_rows = db.query(ChatGroupMember.group_id).filter(
        ChatGroupMember.user_id == current_user.user_id
    ).subquery()
    groups = db.query(ChatGroup).filter(
        ChatGroup.group_id.in_(db.query(member_rows.c.group_id)),
        ChatGroup.status == "active",
    ).order_by(ChatGroup.update_time.desc()).all()
    return [GroupOut.model_validate(g) for g in groups]


@router.get(
    "/groups/{group_id}",
    response_model=GroupOut,
    summary="群详情",
)
def get_group(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GroupOut:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在或已解散")
    return GroupOut.model_validate(group)


@router.put(
    "/groups/{group_id}",
    response_model=GroupOut,
    summary="修改群信息",
    description="群主或管理员可修改群名称、头像、公告、全员禁言等信息。",
)
async def update_group(
    group_id: Annotated[str, Path(description="群 ID")],
    payload: GroupUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GroupOut:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在")

    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None or member.role not in ("owner", "admin"):
        raise fail(status.HTTP_403_FORBIDDEN, "只有群主或管理员可以修改群信息")

    data = payload.model_dump(exclude_unset=True)
    field_map = {"isMuted": "is_muted"}
    for k, v in data.items():
        setattr(group, field_map.get(k, k), v)

    if payload.announcement is not None:
        sys_msg = ChatGroupMessage(
            message_id=new_business_id("grpm"),
            group_id=group_id,
            sender_id=current_user.user_id,
            content=f"群公告已更新：{payload.announcement[:100]}",
            msg_type="system",
            is_recalled=False,
        )
        db.add(sys_msg)

    db.commit()
    db.refresh(group)

    # WS 实时广播群信息更新给所有群成员
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members]
    await manager.broadcast_system_event(
        member_ids,
        "group_info_updated",
        {
            "groupId": group_id,
            "name": group.name,
            "avatar": group.avatar,
            "announcement": group.announcement,
            "isMuted": group.is_muted
        }
    )

    return GroupOut.model_validate(group)


@router.delete(
    "/groups/{group_id}",
    summary="解散群聊",
    description="仅群主可以解散群聊。",
)
async def dissolve_group(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在")
    if group.owner_id != current_user.user_id:
        raise fail(status.HTTP_403_FORBIDDEN, "只有群主可以解散群聊")

    # 在设置 dissolved 之前，先获取所有群成员的 ID 用以通知
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members]

    group.status = "dissolved"
    db.commit()

    # WS 实时广播解散通知给所有群成员
    await manager.broadcast_system_event(
        member_ids,
        "group_dissolved",
        {"groupId": group_id}
    )

    return ok(message="群聊已解散")


# ===================================================================
#  六、群成员管理
# ===================================================================

@router.get(
    "/groups/{group_id}/members",
    response_model=list[GroupMemberOut],
    summary="群成员列表",
)
def list_group_members(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[GroupMemberOut]:
    members = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id
    ).order_by(
        ChatGroupMember.role.asc(), ChatGroupMember.create_time.asc()
    ).all()

    result = []
    for m in members:
        user = db.query(User).filter(User.user_id == m.user_id).first()
        out = GroupMemberOut(
            userId=m.user_id,
            role=m.role,
            nicknameInGroup=m.nickname_in_group,
            isMuted=m.is_muted,
            nickname=user.nickname if user else None,
            avatar=user.avatar if user else None,
            createTime=m.create_time,
        )
        result.append(out)
    return result


@router.post(
    "/groups/{group_id}/members",
    summary="邀请成员入群",
)
async def invite_members(
    group_id: Annotated[str, Path(description="群 ID")],
    payload: GroupInvite,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在")

    # 检查邀请者是否是群成员
    inviter = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if inviter is None:
        raise fail(status.HTTP_403_FORBIDDEN, "你不是该群的成员，无法邀请")

    added = 0
    names = []
    for uid in payload.userIds:
        if group.member_count >= group.max_members:
            break
        exists = db.query(ChatGroupMember).filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.user_id == uid,
        ).first()
        if exists:
            continue
        user = db.query(User).filter(User.user_id == uid).first()
        if user is None:
            continue
        member = ChatGroupMember(
            group_id=group_id,
            user_id=uid,
            role="member",
        )
        db.add(member)
        group.member_count += 1
        added += 1
        names.append(user.nickname or uid)

    if added > 0:
        sys_msg = ChatGroupMessage(
            message_id=new_business_id("grpm"),
            group_id=group_id,
            sender_id=current_user.user_id,
            content=f"{current_user.nickname or current_user.user_id} 邀请了 {', '.join(names[:5])} {'等' if len(names) > 5 else ''}加入群聊",
            msg_type="system",
            is_recalled=False,
        )
        db.add(sys_msg)

    db.commit()

    if added > 0:
        # WS 实时广播群成员更新给所有当前群成员
        members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
        member_ids = [m.user_id for m in members]
        await manager.broadcast_system_event(
            member_ids,
            "group_members_updated",
            {"groupId": group_id, "addedUserIds": payload.userIds}
        )

    return ok({"addedCount": added}, f"已邀请 {added} 人入群")


@router.delete(
    "/groups/{group_id}/members/{user_id}",
    summary="移除群成员",
    description="群主或管理员可移除普通成员。群主可移除管理员。",
)
async def remove_member(
    group_id: Annotated[str, Path(description="群 ID")],
    user_id: Annotated[str, Path(description="被移除的用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在")

    operator = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if operator is None or operator.role not in ("owner", "admin"):
        raise fail(status.HTTP_403_FORBIDDEN, "无权操作")

    target = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == user_id,
    ).first()
    if target is None:
        raise fail(status.HTTP_404_NOT_FOUND, "该用户不在群内")
    if target.role == "owner":
        raise fail(status.HTTP_403_FORBIDDEN, "不能移除群主")
    if target.role == "admin" and operator.role != "owner":
        raise fail(status.HTTP_403_FORBIDDEN, "只有群主可以移除管理员")

    db.delete(target)
    group.member_count = max(group.member_count - 1, 1)
    db.commit()

    # WS 实时广播移除通知（通知其他在线群成员和被移除的人）
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members] + [user_id]
    await manager.broadcast_system_event(
        member_ids,
        "group_members_updated",
        {"groupId": group_id, "removedUserId": user_id}
    )

    return ok(message="已移除该成员")


@router.post(
    "/groups/{group_id}/leave",
    summary="退出群聊",
    description="主动退出群聊。群主不能退出，需先转让或解散。",
)
async def leave_group(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None:
        raise fail(status.HTTP_404_NOT_FOUND, "你不在该群内")
    if member.role == "owner":
        raise fail(status.HTTP_400_BAD_REQUEST, "群主不能退出群聊，请先转让群主或解散群聊")

    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id).first()
    db.delete(member)
    if group:
        group.member_count = max(group.member_count - 1, 1)

    sys_msg = ChatGroupMessage(
        message_id=new_business_id("grpm"),
        group_id=group_id,
        sender_id=current_user.user_id,
        content=f"{current_user.nickname or current_user.user_id} 退出了群聊",
        msg_type="system",
        is_recalled=False,
    )
    db.add(sys_msg)
    db.commit()

    # WS 实时广播退出通知
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members]
    await manager.broadcast_system_event(
        member_ids,
        "group_members_updated",
        {"groupId": group_id, "leftUserId": current_user.user_id}
    )

    return ok(message="已退出群聊")


@router.put(
    "/groups/{group_id}/members/me",
    summary="修改我的群昵称",
)
def update_my_group_nickname(
    group_id: Annotated[str, Path(description="群 ID")],
    nickname: Annotated[str, Query(max_length=64, description="新群昵称")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None:
        raise fail(status.HTTP_404_NOT_FOUND, "你不在该群内")
    member.nickname_in_group = nickname
    db.commit()
    return ok(message="群昵称已更新")


# ===================================================================
#  七、群消息
# ===================================================================

@router.post(
    "/groups/{group_id}/messages",
    response_model=GroupMessageOut,
    summary="发送群消息",
    description="在群聊中发送消息，支持文本、图片、视频、语音、文件、商品卡片、位置和转发等消息类型。",
)
async def send_group_message(
    group_id: Annotated[str, Path(description="群 ID")],
    payload: GroupMessageCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> GroupMessageOut:
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在或已解散")

    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None:
        raise fail(status.HTTP_403_FORBIDDEN, "你不是该群的成员")

    # 禁言检查
    if group.is_muted and member.role == "member":
        raise fail(status.HTTP_403_FORBIDDEN, "群已开启全员禁言，仅群主和管理员可发言")
    if member.is_muted:
        raise fail(status.HTTP_403_FORBIDDEN, "你已被禁言")

    at_str = ",".join(payload.atUserIds) if payload.atUserIds else None
    msg = ChatGroupMessage(
        message_id=new_business_id("grpm"),
        group_id=group_id,
        sender_id=current_user.user_id,
        content=payload.content,
        msg_type=payload.msgType,
        media_url=payload.mediaUrl,
        thumbnail_url=payload.thumbnailUrl,
        file_name=payload.fileName,
        file_size=payload.fileSize,
        duration=payload.duration,
        reply_to_id=payload.replyToId,
        at_user_ids=at_str,
        is_recalled=False,
    )
    db.add(msg)

    preview = payload.content[:50]
    type_preview_map = {"image": "[图片]", "video": "[视频]", "voice": "[语音]", "file": f"[文件] {payload.fileName or ''}", "location": "[位置]"}
    if payload.msgType in type_preview_map:
        preview = type_preview_map[payload.msgType]
    group.last_message = f"{current_user.nickname or current_user.user_id}: {preview}"
    group.last_message_time = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")

    db.commit()
    db.refresh(msg)

    out = GroupMessageOut.model_validate(msg)
    out.senderName = current_user.nickname
    out.senderAvatar = current_user.avatar
    out.atUserIds = payload.atUserIds

    # WS 实时广播群消息给所有群成员
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members]
    await manager.broadcast_to_group(group_id, member_ids, out.model_dump(mode="json"))

    return out


@router.get(
    "/groups/{group_id}/messages",
    response_model=list[GroupMessageOut],
    summary="群消息历史",
    description="获取群聊历史消息记录，最新在最后。",
)
def list_group_messages(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[GroupMessageOut]:
    # 检查是否是群成员
    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None:
        raise fail(status.HTTP_403_FORBIDDEN, "你不是该群的成员")

    msgs = db.query(ChatGroupMessage).filter(
        ChatGroupMessage.group_id == group_id
    ).order_by(
        ChatGroupMessage.create_time.asc()
    ).offset((page - 1) * limit).limit(limit).all()

    result = []
    for m in msgs:
        out = GroupMessageOut.model_validate(m)
        user = db.query(User).filter(User.user_id == m.sender_id).first()
        out.senderName = user.nickname if user else m.sender_id
        out.senderAvatar = user.avatar if user else None
        if m.at_user_ids:
            out.atUserIds = [uid.strip() for uid in m.at_user_ids.split(",") if uid.strip()]
        result.append(out)
    return result


# ===================================================================
#  八、群分享链接邀请进群
# ===================================================================

@router.post(
    "/groups/{group_id}/invite-link",
    summary="生成群邀请分享链接/Token",
    description="生成一个用于邀请人进群的加密 Token，默认 7 天后失效。",
)
def generate_group_invite_link(
    group_id: Annotated[str, Path(description="群 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    expire_days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> dict[str, Any]:
    from jose import jwt
    from datetime import datetime, timezone, timedelta
    from app.core.config import settings

    # 确认群存在且活跃
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "群聊不存在或已解散")

    # 确认当前用户是群成员
    member = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if member is None:
        raise fail(status.HTTP_403_FORBIDDEN, "你不是该群的成员，无法生成邀请链接")

    expire = datetime.now(timezone.utc) + timedelta(days=expire_days)
    payload = {
        "group_id": group_id,
        "inviter_id": current_user.user_id,
        "exp": expire,
        "typ": "group_invite"
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # 组装一个可用的跳转 URL，这里返回相对路径，前端可拼接成完整地址
    invite_url = f"/api/chat/groups/join-by-link?token={token}"

    return ok({
        "token": token,
        "inviteUrl": invite_url,
        "expireTime": expire.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "groupName": group.name,
        "groupAvatar": group.avatar,
    }, "生成群邀请链接成功")


@router.post(
    "/groups/join-by-link",
    summary="通过分享链接/Token 加入群聊",
    description="解析加密 Token，校验时效性，加入对应群聊并实时推送通知给群内在线成员。",
)
async def join_group_by_link(
    payload: JoinByLinkPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    from jose import jwt, JWTError
    from app.core.config import settings

    # 1. 解析校验 Token
    try:
        data = jwt.decode(payload.token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if data.get("typ") != "group_invite":
            raise fail(status.HTTP_400_BAD_REQUEST, "无效的群邀请 Token")
        group_id = data.get("group_id")
        inviter_id = data.get("inviter_id")
    except JWTError:
        raise fail(status.HTTP_400_BAD_REQUEST, "群邀请已过期或无效")

    if not group_id or not inviter_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "无效的群邀请数据")

    # 2. 校验群状态
    group = db.query(ChatGroup).filter(ChatGroup.group_id == group_id, ChatGroup.status == "active").first()
    if group is None:
        raise fail(status.HTTP_404_NOT_FOUND, "要加入的群聊不存在或已解散")

    # 3. 检查是否已经是群成员
    exists = db.query(ChatGroupMember).filter(
        ChatGroupMember.group_id == group_id,
        ChatGroupMember.user_id == current_user.user_id,
    ).first()
    if exists:
        raise fail(status.HTTP_400_BAD_REQUEST, "你已经是该群的成员了")

    # 4. 检查人数上限
    if group.member_count >= group.max_members:
        raise fail(status.HTTP_400_BAD_REQUEST, "该群聊人数已达上限")

    # 5. 查询邀请者信息（系统通知显示需要）
    inviter = db.query(User).filter(User.user_id == inviter_id).first()
    inviter_name = (inviter.nickname if inviter else inviter_id) or inviter_id

    # 6. 新增群成员
    new_member = ChatGroupMember(
        group_id=group_id,
        user_id=current_user.user_id,
        role="member",
    )
    db.add(new_member)
    group.member_count += 1

    # 7. 生成系统群聊消息
    sys_msg = ChatGroupMessage(
        message_id=new_business_id("grpm"),
        group_id=group_id,
        sender_id=current_user.user_id,
        content=f"{current_user.nickname or current_user.user_id} 通过 {inviter_name} 分享的链接加入了群聊",
        msg_type="system",
        is_recalled=False,
    )
    db.add(sys_msg)
    db.commit()

    # 8. WebSocket 广播群成员变更给群内所有在线成员
    members = db.query(ChatGroupMember.user_id).filter(ChatGroupMember.group_id == group_id).all()
    member_ids = [m.user_id for m in members]
    await manager.broadcast_system_event(
        member_ids,
        "group_members_updated",
        {"groupId": group_id, "addedUserIds": [current_user.user_id], "viaLink": True}
    )

    return ok({
        "groupId": group_id,
        "groupName": group.name,
        "avatar": group.avatar,
        "memberCount": group.member_count,
    }, "加入群聊成功")

