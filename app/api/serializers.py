from __future__ import annotations

from app.models.comment import Comment
from app.models.message import Message
from app.models.post import Post
from app.models.post_share import PostShare
from app.models.user import User
from app.schemas.comment import CommentOut
from app.schemas.message import MessageOut
from app.schemas.post import PostOut
from app.schemas.share import ShareOut
from app.schemas.user import UserProfile


def user_profile(user: User) -> UserProfile:
    return UserProfile(
        userId=user.user_id,
        openid=user.openid,
        unionid=user.unionid,
        phone=user.phone,
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


def post_out(post: Post, current_user: User | None, is_liked: bool) -> PostOut:
    is_owner = current_user is not None and current_user.user_id == post.user_id
    return PostOut(
        postId=post.post_id,
        userId=post.user_id,
        nickname=post.author.nickname if post.author else None,
        avatar=post.author.avatar if post.author else None,
        content=post.content,
        images=post.images,
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


def comment_out(comment: Comment) -> CommentOut:
    return CommentOut(
        commentId=comment.comment_id,
        postId=comment.post_id,
        userId=comment.user_id,
        content=comment.content,
        parentId=comment.parent_id,
        replyToUserId=comment.reply_to_user_id,
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
