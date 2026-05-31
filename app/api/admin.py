from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.utils import new_business_id
from app.core.security import create_access_token, decode_access_token
from app.db.base import utc_now
from app.db.session import get_db
from app.models.admin_agreement import AdminAgreement
from app.models.comment import Comment
from app.models.message import Message
from app.models.post import Post
from app.models.system_config import AdminDictionary, AdminRegion, AdminSystemMessage, AdminTag
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["后台管理"])
admin_bearer = HTTPBearer(auto_error=False)


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


class AdminTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64, title="标签名称", description="标签管理中的标签名称")
    color: str | None = Field(default=None, max_length=32, title="标签颜色", description="标签颜色，例如 #1677ff")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")
    remark: str | None = Field(default=None, title="备注", description="标签备注")


class AdminRegionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64, title="地区名称", description="省市区名称")
    code: str = Field(min_length=1, max_length=32, title="地区编码", description="行政区划编码或前端自定义编码")
    parentId: str | None = Field(default=None, max_length=64, title="上级地区 ID", description="上级业务地区 ID，顶级地区可为空")
    level: int = Field(default=1, ge=1, le=4, title="层级", description="1 省级，2 市级，3 区县，4 街道")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")


class AdminDictionaryPayload(BaseModel):
    type: str = Field(min_length=1, max_length=64, title="字典类型", description="字典分组编码，例如 post_status")
    label: str = Field(min_length=1, max_length=128, title="字典标签", description="展示给用户看的中文名称")
    value: str = Field(min_length=1, max_length=128, title="字典值", description="前后端传递使用的值")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")
    remark: str | None = Field(default=None, title="备注", description="字典项备注")


class AdminSystemMessagePayload(BaseModel):
    title: str = Field(min_length=1, max_length=128, title="消息标题", description="系统消息标题")
    content: str = Field(min_length=1, title="消息内容", description="系统消息正文")
    type: str = Field(default="notice", max_length=32, title="消息类型", description="notice 通知，warning 警告，activity 活动")
    target: str = Field(default="all", max_length=32, title="发送范围", description="all 全部用户，admin 后台，user 用户端")
    status: str = Field(default="draft", pattern="^(draft|published|disabled)$", title="状态", description="draft 草稿，published 已发布，disabled 已停用")
    isPinned: bool = Field(default=False, title="是否置顶", description="是否在系统消息列表置顶展示")


class AdminResponse(BaseModel):
    code: int = Field(title="业务状态码", description="200 表示成功，其他值表示业务失败")
    message: str = Field(title="提示信息", description="接口处理结果说明")
    data: Any = Field(default=None, title="响应数据", description="接口返回的业务数据")


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def get_admin_subject(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(admin_bearer)],
) -> str:
    if credentials is None:
        raise fail(status.HTTP_401_UNAUTHORIZED, "未登录，请先登录")
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
        "userId": user.user_id,
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
        "postId": post.post_id,
        "userId": post.user_id,
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
        "commentId": comment.comment_id,
        "postId": comment.post_id,
        "userId": comment.user_id,
        "nickname": user.nickname if user and user.nickname else "即闪用户",
        "avatar": user.avatar if user and user.avatar else "",
        "content": comment.content,
        "parentId": comment.parent_id,
        "replyToUserId": comment.reply_to_user_id,
        "replyToNickname": reply_to.nickname if reply_to else None,
        "pubTime": format_time(comment.create_time),
    }


def tag_item(tag: AdminTag) -> dict[str, Any]:
    return {
        "tagId": tag.tag_id,
        "name": tag.name,
        "color": tag.color or "",
        "sort": tag.sort,
        "status": tag.status,
        "remark": tag.remark or "",
        "createdAt": format_time(tag.create_time),
        "updatedAt": format_time(tag.update_time),
    }


def region_item(region: AdminRegion) -> dict[str, Any]:
    return {
        "regionId": region.region_id,
        "parentId": region.parent_id,
        "name": region.name,
        "code": region.code,
        "level": region.level,
        "sort": region.sort,
        "status": region.status,
        "createdAt": format_time(region.create_time),
        "updatedAt": format_time(region.update_time),
    }


def dictionary_item(dictionary: AdminDictionary) -> dict[str, Any]:
    return {
        "dictId": dictionary.dict_id,
        "type": dictionary.type,
        "label": dictionary.label,
        "value": dictionary.value,
        "sort": dictionary.sort,
        "status": dictionary.status,
        "remark": dictionary.remark or "",
        "createdAt": format_time(dictionary.create_time),
        "updatedAt": format_time(dictionary.update_time),
    }


def system_message_item(message: AdminSystemMessage) -> dict[str, Any]:
    return {
        "messageId": message.message_id,
        "title": message.title,
        "content": message.content,
        "type": message.type,
        "target": message.target,
        "status": message.status,
        "isPinned": message.is_pinned,
        "createdAt": format_time(message.create_time),
        "updatedAt": format_time(message.update_time),
    }


def notification_item(message: Message) -> dict[str, Any]:
    return {
        "messageId": message.message_id,
        "title": message.title or "",
        "content": message.content or "",
        "type": message.type,
        "isRead": message.is_read,
        "time": format_time(message.create_time),
        "createdAt": format_time(message.create_time),
        "updatedAt": format_time(message.update_time),
        "sourceId": message.post_id,
    }


def ensure_admin_notification(db: Session, admin_subject: str, message: AdminSystemMessage) -> None:
    admin_user_id = f"admin:{admin_subject}"
    exists = (
        db.query(Message)
        .filter(Message.user_id == admin_user_id, Message.type == "admin_system", Message.post_id == message.message_id)
        .one_or_none()
    )
    if exists is not None:
        exists.title = message.title
        exists.content = message.content
        exists.last_time = utc_now()
        return
    db.add(
        Message(
            message_id=new_business_id("ntf"),
            user_id=admin_user_id,
            sender_id=None,
            type="admin_system",
            title=message.title,
            content=message.content,
            post_id=message.message_id,
            is_read=False,
        )
    )


def publish_system_message_to_users(db: Session, message: AdminSystemMessage) -> int:
    query = db.query(User).filter(User.is_active.is_(True))
    if message.target == "new":
        query = query.order_by(User.create_time.desc()).limit(200)
    users = query.all()
    created = 0
    for user in users:
        exists = (
            db.query(Message)
            .filter(Message.user_id == user.user_id, Message.type == "system", Message.post_id == message.message_id)
            .one_or_none()
        )
        if exists is not None:
            exists.title = message.title
            exists.content = message.content
            exists.last_time = utc_now()
            continue
        db.add(
            Message(
                message_id=new_business_id("ntf"),
                user_id=user.user_id,
                sender_id=None,
                type="system",
                title=message.title,
                content=message.content,
                post_id=message.message_id,
                is_read=False,
            )
        )
        created += 1
    return created


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
    "/notifications",
    response_model=AdminResponse,
    summary="后台通知下拉",
    description="PC 后台右上角消息通知下拉接口，返回未读数量和最近通知列表。",
)
def list_admin_notifications(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
    limit: Annotated[int, Query(ge=1, le=50, description="返回数量")] = 10,
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    recent_system_messages = db.query(AdminSystemMessage).order_by(AdminSystemMessage.create_time.desc()).limit(limit).all()
    for system_message in recent_system_messages:
        ensure_admin_notification(db, admin_subject, system_message)
    db.commit()

    query = db.query(Message).filter(Message.user_id == admin_user_id)
    unread_count = query.filter(Message.is_read.is_(False)).count()
    messages = query.order_by(Message.create_time.desc()).limit(limit).all()
    return ok({"unreadCount": unread_count, "list": [notification_item(message) for message in messages]})


@router.get(
    "/notifications/{messageId}",
    response_model=AdminResponse,
    summary="后台通知详情",
    description="PC 后台点击右上角通知时调用；按当前 admin 标记该条通知为已读并返回详情。",
)
def get_admin_notification_detail(
    messageId: Annotated[str, Path(description="通知消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    message = db.query(Message).filter(Message.user_id == admin_user_id, Message.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "通知未找到")
    message.is_read = True
    message.last_time = utc_now()
    db.commit()
    db.refresh(message)
    return ok(notification_item(message), "已读取通知详情")


@router.put(
    "/notifications/read-all",
    response_model=AdminResponse,
    summary="后台通知全部已读",
    description="PC 后台右上角消息通知下拉全部标记已读。",
)
def read_all_admin_notifications(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    db.query(Message).filter(Message.user_id == admin_user_id, Message.is_read.is_(False)).update(
        {Message.is_read: True, Message.last_time: utc_now()},
        synchronize_session=False,
    )
    db.commit()
    return ok(None, "已全部标记为已读")


@router.put(
    "/notifications/{messageId}/read",
    response_model=AdminResponse,
    summary="后台通知已读",
    description="PC 后台右上角消息通知下拉单条标记已读。",
)
def read_admin_notification(
    messageId: Annotated[str, Path(description="通知消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    message = db.query(Message).filter(Message.user_id == admin_user_id, Message.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "通知未找到")
    message.is_read = True
    message.last_time = utc_now()
    db.commit()
    return ok(notification_item(message), "已标记为已读")


@router.get(
    "/users",
    response_model=AdminResponse,
    summary="用户列表",
    description="后台用户管理列表，支持按用户 ID、昵称、手机号、账号状态筛选。",
)
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: Annotated[str | None, Query(description="业务用户 ID，精确匹配")] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    nickname: Annotated[str | None, Query(description="用户昵称，模糊匹配")] = None,
    phone: Annotated[str | None, Query(description="手机号，模糊匹配")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="账号状态：normal 正常，banned 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    user_id = userId or user_id_legacy
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
    "/users/{userId}",
    response_model=AdminResponse,
    summary="用户详情",
    description="后台查看单个业务用户详情。",
)
def get_admin_user(
    userId: Annotated[str, Path(description="业务用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user_id = userId
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    return ok(user_item(db, user))


@router.put(
    "/users/{userId}",
    response_model=AdminResponse,
    summary="修改用户状态",
    description="后台禁用或解禁用户。禁用后该用户 token 将无法访问需要登录的用户端接口。",
)
def update_admin_user_status(
    userId: Annotated[str, Path(description="业务用户 ID")],
    payload: AdminUserStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user_id = userId
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
    userId: Annotated[str | None, Query(description="发布人业务用户 ID，精确匹配")] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="内容状态：online 已上架，offline 已下架")] = None,
    content: Annotated[str | None, Query(description="内容正文关键词，模糊匹配")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 5,
) -> dict[str, Any]:
    user_id = userId or user_id_legacy
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
    "/posts/{postId}",
    response_model=AdminResponse,
    summary="内容详情",
    description="后台查看单条内容详情；后台可查看已下架内容。",
)
def get_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
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
    "/posts/{postId}/offline",
    response_model=AdminResponse,
    summary="内容下架",
    description="后台将内容置为 offline。下架后用户端公开列表和详情不可见。",
)
def offline_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
    post = db.query(Post).filter(Post.post_id == post_id, Post.is_deleted.is_(False)).one_or_none()
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    post.status = "offline"
    post.last_time = utc_now()
    db.commit()
    return ok(None, "内容已成功下架")


@router.put(
    "/posts/{postId}/restore",
    response_model=AdminResponse,
    summary="恢复上架",
    description="后台将已下架内容恢复为 online，恢复后用户端可见。",
)
def restore_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
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
    postId: Annotated[str | None, Query(description="内容 ID，精确匹配")] = None,
    userId: Annotated[str | None, Query(description="评论人业务用户 ID，精确匹配")] = None,
    post_id_legacy: Annotated[str | None, Query(alias="post_id", description="兼容旧参数 post_id", include_in_schema=False)] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    post_id = postId or post_id_legacy
    user_id = userId or user_id_legacy
    query = db.query(Comment).filter(Comment.is_deleted.is_(False))
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)
    total = query.count()
    comments = query.order_by(Comment.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [comment_item(db, comment) for comment in comments], "total": total})


@router.delete(
    "/comments/{commentId}",
    response_model=AdminResponse,
    summary="删除评论",
    description="后台删除评论。当前为软删除，并同步扣减内容评论数。",
)
def delete_admin_comment(
    commentId: Annotated[str, Path(description="评论 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    comment_id = commentId
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
    "/agreement/{agreementType}",
    response_model=AdminResponse,
    summary="获取协议",
    description="获取后台维护的协议内容。agreementType 支持 privacy 或 user。",
)
def get_admin_agreement(
    agreementType: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    agreement_type = agreementType
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    return ok(agreement.content)


@router.put(
    "/agreement/{agreementType}",
    response_model=AdminResponse,
    summary="更新协议",
    description="更新后台维护的协议内容。agreementType 支持 privacy 或 user。",
)
def update_admin_agreement(
    agreementType: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    payload: AgreementUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    agreement_type = agreementType
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    agreement.content = payload.content
    agreement.last_time = utc_now()
    db.commit()
    return ok(None, "协议更新成功")


@router.get(
    "/tags",
    response_model=AdminResponse,
    summary="标签列表",
    description="系统配置 - 标签管理列表，支持按标签名称和状态筛选。",
)
def list_admin_tags(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="标签名称关键词")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(AdminTag)
    if keyword:
        query = query.filter(AdminTag.name.ilike(f"%{keyword}%"))
    if status_filter:
        query = query.filter(AdminTag.status == status_filter)
    total = query.count()
    tags = query.order_by(AdminTag.sort.asc(), AdminTag.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [tag_item(tag) for tag in tags], "total": total})


@router.post(
    "/tags",
    response_model=AdminResponse,
    summary="新增标签",
    description="系统配置 - 新增标签。",
)
def create_admin_tag(
    payload: AdminTagPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if db.query(AdminTag).filter(AdminTag.name == payload.name).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "标签名称已存在")
    tag = AdminTag(
        tag_id=new_business_id("tag"),
        name=payload.name,
        color=payload.color,
        sort=payload.sort,
        status=payload.status,
        remark=payload.remark,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return ok(tag_item(tag), "标签创建成功")


@router.get(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="标签详情",
    description="系统配置 - 查看标签详情。",
)
def get_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    return ok(tag_item(tag))


@router.put(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="修改标签",
    description="系统配置 - 修改标签信息。",
)
def update_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    payload: AdminTagPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    duplicate = db.query(AdminTag).filter(AdminTag.name == payload.name, AdminTag.tag_id != tagId).one_or_none()
    if duplicate is not None:
        raise fail(status.HTTP_400_BAD_REQUEST, "标签名称已存在")
    tag.name = payload.name
    tag.color = payload.color
    tag.sort = payload.sort
    tag.status = payload.status
    tag.remark = payload.remark
    tag.last_time = utc_now()
    db.commit()
    db.refresh(tag)
    return ok(tag_item(tag), "标签更新成功")


@router.delete(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="删除标签",
    description="系统配置 - 删除标签。",
)
def delete_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    db.delete(tag)
    db.commit()
    return ok(None, "标签删除成功")


@router.get(
    "/regions",
    response_model=AdminResponse,
    summary="地区列表",
    description="系统配置 - 地区管理列表，支持按名称、编码、上级地区和状态筛选。",
)
def list_admin_regions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="地区名称或编码关键词")] = None,
    parentId: Annotated[str | None, Query(description="上级地区 ID")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=200, description="每页数量")] = 50,
) -> dict[str, Any]:
    query = db.query(AdminRegion)
    if keyword:
        query = query.filter((AdminRegion.name.ilike(f"%{keyword}%")) | (AdminRegion.code.ilike(f"%{keyword}%")))
    if parentId:
        query = query.filter(AdminRegion.parent_id == parentId)
    if status_filter:
        query = query.filter(AdminRegion.status == status_filter)
    total = query.count()
    regions = query.order_by(AdminRegion.level.asc(), AdminRegion.sort.asc(), AdminRegion.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [region_item(region) for region in regions], "total": total})


@router.post(
    "/regions",
    response_model=AdminResponse,
    summary="新增地区",
    description="系统配置 - 新增地区。",
)
def create_admin_region(
    payload: AdminRegionPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if db.query(AdminRegion).filter(AdminRegion.code == payload.code).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "地区编码已存在")
    region = AdminRegion(
        region_id=new_business_id("reg"),
        parent_id=payload.parentId,
        name=payload.name,
        code=payload.code,
        level=payload.level,
        sort=payload.sort,
        status=payload.status,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return ok(region_item(region), "地区创建成功")


@router.get(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="地区详情",
    description="系统配置 - 查看地区详情。",
)
def get_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    return ok(region_item(region))


@router.put(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="修改地区",
    description="系统配置 - 修改地区信息。",
)
def update_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    payload: AdminRegionPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    duplicate = db.query(AdminRegion).filter(AdminRegion.code == payload.code, AdminRegion.region_id != regionId).one_or_none()
    if duplicate is not None:
        raise fail(status.HTTP_400_BAD_REQUEST, "地区编码已存在")
    region.parent_id = payload.parentId
    region.name = payload.name
    region.code = payload.code
    region.level = payload.level
    region.sort = payload.sort
    region.status = payload.status
    region.last_time = utc_now()
    db.commit()
    db.refresh(region)
    return ok(region_item(region), "地区更新成功")


@router.delete(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="删除地区",
    description="系统配置 - 删除地区；存在下级地区时不允许删除。",
)
def delete_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    if db.query(AdminRegion).filter(AdminRegion.parent_id == regionId).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "存在下级地区，不能删除")
    db.delete(region)
    db.commit()
    return ok(None, "地区删除成功")


@router.get(
    "/dictionaries",
    response_model=AdminResponse,
    summary="字典列表",
    description="系统配置 - 字典管理列表，支持按字典类型、标签和值筛选。",
)
def list_admin_dictionaries(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    type: Annotated[str | None, Query(description="字典类型，精确匹配")] = None,
    keyword: Annotated[str | None, Query(description="字典标签或值关键词")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(AdminDictionary)
    if type:
        query = query.filter(AdminDictionary.type == type)
    if keyword:
        query = query.filter((AdminDictionary.label.ilike(f"%{keyword}%")) | (AdminDictionary.value.ilike(f"%{keyword}%")))
    if status_filter:
        query = query.filter(AdminDictionary.status == status_filter)
    total = query.count()
    dictionaries = query.order_by(AdminDictionary.type.asc(), AdminDictionary.sort.asc(), AdminDictionary.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [dictionary_item(dictionary) for dictionary in dictionaries], "total": total})


@router.post(
    "/dictionaries",
    response_model=AdminResponse,
    summary="新增字典",
    description="系统配置 - 新增字典项。",
)
def create_admin_dictionary(
    payload: AdminDictionaryPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = AdminDictionary(
        dict_id=new_business_id("dict"),
        type=payload.type,
        label=payload.label,
        value=payload.value,
        sort=payload.sort,
        status=payload.status,
        remark=payload.remark,
    )
    db.add(dictionary)
    db.commit()
    db.refresh(dictionary)
    return ok(dictionary_item(dictionary), "字典创建成功")


@router.get(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="字典详情",
    description="系统配置 - 查看字典项详情。",
)
def get_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = db.query(AdminDictionary).filter(AdminDictionary.dict_id == dictId).one_or_none()
    if dictionary is None:
        raise fail(status.HTTP_404_NOT_FOUND, "字典未找到")
    return ok(dictionary_item(dictionary))


@router.put(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="修改字典",
    description="系统配置 - 修改字典项。",
)
def update_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    payload: AdminDictionaryPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = db.query(AdminDictionary).filter(AdminDictionary.dict_id == dictId).one_or_none()
    if dictionary is None:
        raise fail(status.HTTP_404_NOT_FOUND, "字典未找到")
    dictionary.type = payload.type
    dictionary.label = payload.label
    dictionary.value = payload.value
    dictionary.sort = payload.sort
    dictionary.status = payload.status
    dictionary.remark = payload.remark
    dictionary.last_time = utc_now()
    db.commit()
    db.refresh(dictionary)
    return ok(dictionary_item(dictionary), "字典更新成功")


@router.delete(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="删除字典",
    description="系统配置 - 删除字典项。",
)
def delete_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = db.query(AdminDictionary).filter(AdminDictionary.dict_id == dictId).one_or_none()
    if dictionary is None:
        raise fail(status.HTTP_404_NOT_FOUND, "字典未找到")
    db.delete(dictionary)
    db.commit()
    return ok(None, "字典删除成功")


@router.get(
    "/system-messages",
    response_model=AdminResponse,
    summary="系统消息列表",
    description="系统配置 - 系统消息列表，支持按标题、类型、发送范围和状态筛选。",
)
def list_admin_system_messages(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="消息标题或内容关键词")] = None,
    type: Annotated[str | None, Query(description="消息类型")] = None,
    target: Annotated[str | None, Query(description="发送范围：all/admin/user")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：draft/published/disabled")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(AdminSystemMessage)
    if keyword:
        query = query.filter((AdminSystemMessage.title.ilike(f"%{keyword}%")) | (AdminSystemMessage.content.ilike(f"%{keyword}%")))
    if type:
        query = query.filter(AdminSystemMessage.type == type)
    if target:
        query = query.filter(AdminSystemMessage.target == target)
    if status_filter:
        query = query.filter(AdminSystemMessage.status == status_filter)
    total = query.count()
    messages = query.order_by(AdminSystemMessage.is_pinned.desc(), AdminSystemMessage.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [system_message_item(message) for message in messages], "total": total})


@router.post(
    "/system-messages",
    response_model=AdminResponse,
    summary="新增系统消息",
    description="系统配置 - 新增系统消息。",
)
def create_admin_system_message(
    payload: AdminSystemMessagePayload,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = AdminSystemMessage(
        message_id=new_business_id("msg"),
        title=payload.title,
        content=payload.content,
        type=payload.type,
        target=payload.target,
        status=payload.status,
        is_pinned=payload.isPinned,
    )
    db.add(message)
    db.flush()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = 0
    if message.status == "published":
        pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息创建成功")


@router.get(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="系统消息详情",
    description="系统配置 - 查看系统消息详情。",
)
def get_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    return ok(system_message_item(message))


@router.put(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="修改系统消息",
    description="系统配置 - 修改系统消息。",
)
def update_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    payload: AdminSystemMessagePayload,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    old_status = message.status
    message.title = payload.title
    message.content = payload.content
    message.type = payload.type
    message.target = payload.target
    message.status = payload.status
    message.is_pinned = payload.isPinned
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = 0
    if message.status == "published" and old_status != "published":
        pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息更新成功")


@router.put(
    "/system-messages/{messageId}/push",
    response_model=AdminResponse,
    summary="推送系统消息",
    description="系统配置 - 将草稿系统消息发布，并同步生成用户端通知消息。",
)
def push_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    message.status = "published"
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息已推送")


@router.put(
    "/system-messages/{messageId}/retract",
    response_model=AdminResponse,
    summary="撤回系统消息",
    description="系统配置 - 将已发布系统消息撤回为草稿状态。",
)
def retract_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    message.status = "draft"
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    db.commit()
    db.refresh(message)
    return ok(system_message_item(message), "系统消息已撤回")


@router.delete(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="删除系统消息",
    description="系统配置 - 删除系统消息。",
)
def delete_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    db.delete(message)
    db.commit()
    return ok(None, "系统消息删除成功")
