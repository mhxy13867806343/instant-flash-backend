from __future__ import annotations

from datetime import datetime

from app.core.points import point_type_name
from app.models.comment import Comment
from app.models.message import Message
from app.models.point_record import PointRecord
from app.models.post import Post
from app.models.post_share import PostShare
from app.models.user import User
from app.schemas.comment import CommentOut
from app.schemas.message import MessageOut
from app.schemas.post import PostOut
from app.schemas.share import ShareOut
from app.schemas.user import UserProfile


def _format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def point_record_item(record: PointRecord) -> dict[str, object]:
    return {
        "recordId": record.record_id,
        "userId": record.user_id,
        "type": record.type,
        "typeName": point_type_name(record.type),
        "direction": record.direction,
        "changeAmount": record.change_amount,
        "balanceAfter": record.balance_after,
        "title": record.title or "",
        "remark": record.remark or "",
        "sourceId": record.source_id or "",
        "createdAt": _format_time(record.create_time),
        "createTime": _format_time(record.create_time),
    }


def user_profile(user: User) -> UserProfile:
    return UserProfile(
        userId=user.user_id,
        openid=user.openid,
        unionid=user.unionid,
        phone=user.phone,
        newPhone=user.new_phone,
        clientType=user.client_type,
        clientSubtype=user.client_subtype,
        nickname=user.nickname,
        avatar=user.avatar,
        gender=user.gender,
        bio=user.bio,
        signature=user.bio,
        province=user.province,
        city=user.city,
        district=user.district,
        isActive=user.is_active,
        createTime=user.create_time,
        updateTime=user.update_time,
        lastTime=user.last_time,
    )


def media_type(item: object) -> str | None:
    if isinstance(item, dict):
        explicit_type = str(item.get("type") or item.get("mediaType") or "").strip().lower()
        if explicit_type in {"image", "video"}:
            return explicit_type
        url = item.get("url")
        if isinstance(url, str):
            return media_type(url)
    if isinstance(item, str):
        path = item.split("?", 1)[0].lower()
        if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")) or "/image/" in path:
            return "image"
        if path.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi")) or "/video/" in path:
            return "video"
    return None


def post_out(post: Post, current_user: User | None, is_liked: bool) -> PostOut:
    is_owner = current_user is not None and current_user.user_id == post.user_id
    media = post.images or []
    videos = [item for item in media if media_type(item) == "video"]
    return PostOut(
        postId=post.post_id,
        userId=post.user_id,
        nickname=post.author.nickname if post.author else None,
        avatar=post.author.avatar if post.author else None,
        content=post.content,
        images=media,
        videos=videos,
        media=media,
        topics=post.topics or [],
        location=post.location,
        province=post.province,
        city=post.city,
        district=post.district,
        visibility=post.visibility,
        likeCount=post.like_count,
        commentCount=post.comment_count,
        shareCount=post.share_count,
        status=post.status,
        isLiked=is_liked,
        isOwner=is_owner,
        canEdit=is_owner,
        canDelete=is_owner,
        createdAt=post.create_time,
        updatedAt=post.update_time,
    )


def comment_out(
    comment: Comment,
    user: User | None = None,
    reply_to: User | None = None,
    children: list[CommentOut] | None = None,
) -> CommentOut:
    resolved_children = children or []
    return CommentOut(
        commentId=comment.comment_id,
        postId=comment.post_id,
        userId=comment.user_id,
        nickname=user.nickname if user and user.nickname else None,
        avatar=user.avatar if user else None,
        content=comment.content,
        parentId=comment.parent_id,
        replyToUserId=comment.reply_to_user_id,
        replyToNickname=reply_to.nickname if reply_to and reply_to.nickname else None,
        children=resolved_children,
        replies=resolved_children,
        replyCount=len(resolved_children),
        createdAt=comment.create_time,
        updatedAt=comment.update_time,
    )


def share_out(share: PostShare) -> ShareOut:
    return ShareOut(
        postId=share.post_id,
        userId=share.user_id,
        scene=share.scene,
        platform=share.platform,
        createdAt=share.create_time,
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        messageId=message.message_id,
        userId=message.user_id,
        senderId=message.sender_id,
        type=message.type,
        title=message.title,
        content=message.content,
        postId=message.post_id,
        commentId=message.comment_id,
        isRead=message.is_read,
        createdAt=message.create_time,
        updatedAt=message.update_time,
    )
