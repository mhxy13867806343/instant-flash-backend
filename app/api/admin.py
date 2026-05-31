from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.security import create_access_token, decode_access_token
from app.db.base import utc_now
from app.db.session import get_db
from app.models.admin_agreement import AdminAgreement
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_bearer = HTTPBearer(auto_error=True)


DEFAULT_AGREEMENTS = {
    "privacy": "<h2>即闪隐私政策</h2><p>请在后台编辑最新隐私政策内容。</p>",
    "user": "<h2>即闪用户协议</h2><p>请在后台编辑最新用户协议内容。</p>",
}


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminUserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(normal|banned)$")


class AgreementUpdate(BaseModel):
    content: str


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": None},
    )


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def get_admin_subject(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(admin_bearer)],
) -> str:
    if credentials.scheme.lower() != "bearer":
        raise fail(status.HTTP_401_UNAUTHORIZED, "登录失效，请重新登录")
    subject = decode_access_token(credentials.credentials)
    if subject is None or not subject.startswith("admin:"):
        raise fail(status.HTTP_401_UNAUTHORIZED, "登录失效，请重新登录")
    return subject.removeprefix("admin:")


def user_item(db: Session, user: User) -> dict[str, Any]:
    post_count = (
        db.query(func.count(Post.id))
        .filter(Post.user_id == user.user_id, Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    comment_count = (
        db.query(func.count(Comment.id))
        .filter(Comment.user_id == user.user_id, Comment.is_deleted.is_(False))
        .scalar()
        or 0
    )
    likes_received = (
        db.query(func.coalesce(func.sum(Post.like_count), 0))
        .filter(Post.user_id == user.user_id, Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    return {
        "user_id": user.user_id,
        "nickname": user.nickname or "即闪用户",
        "avatar": user.avatar or "",
        "phone": user.phone or "",
        "newPhone": user.phone or "",
        "status": "normal" if user.is_active else "banned",
        "regTime": format_time(user.create_time),
        "postCount": post_count,
        "commentCount": comment_count,
        "likesReceived": likes_received,
        "bio": "",
        "gender": user.gender or "保密",
    }


def post_status(post: Post) -> str:
    return "offline" if post.status == "offline" else "online"


def post_item(post: Post) -> dict[str, Any]:
    author = post.author
    return {
        "post_id": post.post_id,
        "user_id": post.user_id,
        "nickname": author.nickname if author and author.nickname else "即闪用户",
        "avatar": author.avatar if author and author.avatar else "",
        "content": post.content,
        "images": post.images,
        "likes": post.like_count,
        "comments": post.comment_count,
        "shares": post.share_count,
        "status": post_status(post),
        "pubTime": format_time(post.create_time),
    }


def comment_item(db: Session, comment: Comment) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == comment.user_id).one_or_none()
    reply_to = (
        db.query(User).filter(User.user_id == comment.reply_to_user_id).one_or_none()
        if comment.reply_to_user_id
        else None
    )
    return {
        "comment_id": comment.comment_id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "nickname": user.nickname if user and user.nickname else "即闪用户",
        "avatar": user.avatar if user and user.avatar else "",
        "content": comment.content,
        "parent_id": comment.parent_id,
        "reply_to_user_id": comment.reply_to_user_id,
        "reply_to_nickname": reply_to.nickname if reply_to else None,
        "pubTime": format_time(comment.create_time),
    }


def get_or_create_agreement(db: Session, agreement_type: str) -> AdminAgreement:
    agreement = db.query(AdminAgreement).filter(AdminAgreement.type == agreement_type).one_or_none()
    if agreement is not None:
        return agreement
    agreement = AdminAgreement(
        type=agreement_type,
        content=DEFAULT_AGREEMENTS[agreement_type],
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


@router.post("/auth/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, Any]:
    if payload.username == "admin" and payload.password == "123456":
        token = create_access_token(f"admin:{payload.username}")
        return ok({"token": token, "username": payload.username}, "登录成功")
    raise fail(status.HTTP_400_BAD_REQUEST, "用户名或密码错误")


@router.get("/dashboard/metrics")
def dashboard_metrics(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    post_query = db.query(Post).filter(Post.is_deleted.is_(False))
    total_posts = post_query.count()
    offline_posts = post_query.filter(Post.status == "offline").count()
    online_posts = total_posts - offline_posts
    total_comments = db.query(func.count(Comment.id)).filter(Comment.is_deleted.is_(False)).scalar() or 0
    total_likes = (
        db.query(func.coalesce(func.sum(Post.like_count), 0))
        .filter(Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    return ok(
        {
            "totalUsers": total_users,
            "activeUsers": active_users,
            "totalPosts": total_posts,
            "onlinePosts": online_posts,
            "offlinePosts": offline_posts,
            "totalComments": total_comments,
            "totalLikes": total_likes,
        }
    )


@router.get("/users")
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    user_id: str | None = None,
    nickname: str | None = None,
    phone: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    query = db.query(User)
    if user_id:
        query = query.filter(User.user_id == user_id)
    if nickname:
        query = query.filter(User.nickname.ilike(f"%{nickname}%"))
    if phone:
        query = query.filter(User.phone.ilike(f"%{phone}%"))
    if status_filter == "normal":
        query = query.filter(User.is_active.is_(True))
    elif status_filter == "banned":
        query = query.filter(User.is_active.is_(False))

    total = query.count()
    users = query.order_by(User.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [user_item(db, user) for user in users], "total": total})


@router.get("/users/{user_id}")
def get_admin_user(
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    return ok(user_item(db, user))


@router.put("/users/{user_id}")
def update_admin_user_status(
    user_id: str,
    payload: AdminUserStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    user.is_active = payload.status == "normal"
    user.last_time = utc_now()
    db.commit()
    return ok(None, "操作成功")


@router.get("/posts")
def list_admin_posts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    nickname: str | None = None,
    user_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    content: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 5,
) -> dict[str, Any]:
    query = db.query(Post).options(joinedload(Post.author)).filter(Post.is_deleted.is_(False))
    if user_id:
        query = query.filter(Post.user_id == user_id)
    if status_filter == "online":
        query = query.filter(Post.status != "offline")
    elif status_filter == "offline":
        query = query.filter(Post.status == "offline")
    if content:
        query = query.filter(Post.content.ilike(f"%{content}%"))
    if nickname:
        query = query.join(User, User.user_id == Post.user_id).filter(User.nickname.ilike(f"%{nickname}%"))

    total = query.count()
    posts = query.order_by(Post.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [post_item(post) for post in posts], "total": total})


@router.get("/posts/{post_id}")
def get_admin_post(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.post_id == post_id, Post.is_deleted.is_(False))
        .one_or_none()
    )
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    return ok(post_item(post))


@router.put("/posts/{post_id}/offline")
def offline_admin_post(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post = db.query(Post).filter(Post.post_id == post_id, Post.is_deleted.is_(False)).one_or_none()
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    post.status = "offline"
    post.last_time = utc_now()
    db.commit()
    return ok(None, "内容已成功下架")


@router.put("/posts/{post_id}/restore")
def restore_admin_post(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post = db.query(Post).filter(Post.post_id == post_id, Post.is_deleted.is_(False)).one_or_none()
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    post.status = "online"
    post.last_time = utc_now()
    db.commit()
    return ok(None, "内容已恢复上架")


@router.get("/comments")
def list_admin_comments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    post_id: str | None = None,
    user_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    query = db.query(Comment).filter(Comment.is_deleted.is_(False))
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)
    total = query.count()
    comments = query.order_by(Comment.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [comment_item(db, comment) for comment in comments], "total": total})


@router.delete("/comments/{comment_id}")
def delete_admin_comment(
    comment_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    comment = db.query(Comment).filter(Comment.comment_id == comment_id, Comment.is_deleted.is_(False)).one_or_none()
    if comment is None:
        raise fail(status.HTTP_404_NOT_FOUND, "评论未找到")
    post = db.query(Post).filter(Post.post_id == comment.post_id).one_or_none()
    comment.is_deleted = True
    comment.delete_time = utc_now()
    comment.last_time = comment.delete_time
    if post is not None:
        post.comment_count = max(0, post.comment_count - 1)
        post.last_time = utc_now()
    db.commit()
    return ok(None, "评论已成功删除")


@router.get("/agreement/{agreement_type}")
def get_admin_agreement(
    agreement_type: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    return ok(agreement.content)


@router.put("/agreement/{agreement_type}")
def update_admin_agreement(
    agreement_type: str,
    payload: AgreementUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    agreement.content = payload.content
    agreement.last_time = utc_now()
    db.commit()
    return ok(None, "协议更新成功")
