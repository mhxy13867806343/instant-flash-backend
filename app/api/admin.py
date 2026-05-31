from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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

router = APIRouter(prefix="/api/admin", tags=["后台管理"])
admin_bearer = HTTPBearer(auto_error=True)


DEFAULT_AGREEMENTS = {
    "privacy": "<h2>即闪隐私政策</h2><p>请在后台编辑最新隐私政策内容。</p>",
    "user": "<h2>即闪用户协议</h2><p>请在后台编辑最新用户协议内容。</p>",
}


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, title="管理员账号", description="后台管理员登录账号")
    password: str = Field(min_length=1, max_length=128, title="管理员密码", description="后台管理员登录密码")


class AdminUserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(normal|banned)$", title="用户状态", description="normal 表示正常，banned 表示禁用")


class AgreementUpdate(BaseModel):
    content: str = Field(title="协议内容", description="HTML 格式的协议正文")


class AdminResponse(BaseModel):
    code: int = Field(title="业务状态码", description="200 表示成功，其他值表示业务失败")
    message: str = Field(title="提示信息", description="接口处理结果说明")
    data: Any = Field(default=None, title="响应数据", description="接口返回的业务数据")


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


@router.post(
    "/auth/login",
    response_model=AdminResponse,
    summary="后台登录",
    description="后台管理系统登录接口。演示账号 admin，密码 123456。",
)
def admin_login(payload: AdminLoginRequest) -> dict[str, Any]:
    if payload.username == "admin" and payload.password == "123456":
        token = create_access_token(f"admin:{payload.username}")
        return ok({"token": token, "username": payload.username}, "登录成功")
    raise fail(status.HTTP_400_BAD_REQUEST, "用户名或密码错误")


@router.get(
    "/dashboard/metrics",
    response_model=AdminResponse,
    summary="看板指标",
    description="获取后台首页数据看板指标，包括用户、内容、评论和点赞统计。",
)
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


@router.get(
    "/users",
    response_model=AdminResponse,
    summary="用户列表",
    description="后台用户管理列表，支持按用户 ID、昵称、手机号、账号状态筛选。",
)
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    user_id: Annotated[str | None, Query(description="业务用户 ID，精确匹配")] = None,
    nickname: Annotated[str | None, Query(description="用户昵称，模糊匹配")] = None,
    phone: Annotated[str | None, Query(description="手机号，模糊匹配")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="账号状态：normal 正常，banned 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
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


@router.get(
    "/users/{user_id}",
    response_model=AdminResponse,
    summary="用户详情",
    description="后台查看单个业务用户详情。",
)
def get_admin_user(
    user_id: Annotated[str, Path(description="业务用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    return ok(user_item(db, user))


@router.put(
    "/users/{user_id}",
    response_model=AdminResponse,
    summary="修改用户状态",
    description="后台禁用或解禁用户。禁用后该用户 token 将无法访问需要登录的用户端接口。",
)
def update_admin_user_status(
    user_id: Annotated[str, Path(description="业务用户 ID")],
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


@router.get(
    "/posts",
    response_model=AdminResponse,
    summary="内容列表",
    description="后台内容管理列表，支持按发布人、内容关键词和上架状态筛选。",
)
def list_admin_posts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    nickname: Annotated[str | None, Query(description="发布人昵称，模糊匹配")] = None,
    user_id: Annotated[str | None, Query(description="发布人业务用户 ID，精确匹配")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="内容状态：online 已上架，offline 已下架")] = None,
    content: Annotated[str | None, Query(description="内容正文关键词，模糊匹配")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 5,
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


@router.get(
    "/posts/{post_id}",
    response_model=AdminResponse,
    summary="内容详情",
    description="后台查看单条内容详情；后台可查看已下架内容。",
)
def get_admin_post(
    post_id: Annotated[str, Path(description="内容 ID")],
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


@router.put(
    "/posts/{post_id}/offline",
    response_model=AdminResponse,
    summary="内容下架",
    description="后台将内容置为 offline。下架后用户端公开列表和详情不可见。",
)
def offline_admin_post(
    post_id: Annotated[str, Path(description="内容 ID")],
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


@router.put(
    "/posts/{post_id}/restore",
    response_model=AdminResponse,
    summary="恢复上架",
    description="后台将已下架内容恢复为 online，恢复后用户端可见。",
)
def restore_admin_post(
    post_id: Annotated[str, Path(description="内容 ID")],
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


@router.get(
    "/comments",
    response_model=AdminResponse,
    summary="评论列表",
    description="后台评论管理列表，支持按内容 ID 或评论人用户 ID 筛选。",
)
def list_admin_comments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    post_id: Annotated[str | None, Query(description="内容 ID，精确匹配")] = None,
    user_id: Annotated[str | None, Query(description="评论人业务用户 ID，精确匹配")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(Comment).filter(Comment.is_deleted.is_(False))
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)
    total = query.count()
    comments = query.order_by(Comment.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [comment_item(db, comment) for comment in comments], "total": total})


@router.delete(
    "/comments/{comment_id}",
    response_model=AdminResponse,
    summary="删除评论",
    description="后台删除评论。当前为软删除，并同步扣减内容评论数。",
)
def delete_admin_comment(
    comment_id: Annotated[str, Path(description="评论 ID")],
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


@router.get(
    "/agreement/{agreement_type}",
    response_model=AdminResponse,
    summary="获取协议",
    description="获取后台维护的协议内容。agreement_type 支持 privacy 或 user。",
)
def get_admin_agreement(
    agreement_type: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    return ok(agreement.content)


@router.put(
    "/agreement/{agreement_type}",
    response_model=AdminResponse,
    summary="更新协议",
    description="更新后台维护的协议内容。agreement_type 支持 privacy 或 user。",
)
def update_admin_agreement(
    agreement_type: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
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
