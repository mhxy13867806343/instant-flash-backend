from __future__ import annotations

import hashlib
import re
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.admin import fail, read_user_import_rows, user_export_response
from app.api.deps import get_current_user_required
from app.api.serializers import comment_out, post_out, share_out, user_profile
from app.api.user_identity import mobile_user_id, normalize_client_subtype, normalize_client_type, normalize_phone, phone_from_user_id
from app.core.security import create_access_token
from app.db.base import utc_now
from app.db.session import get_db
from app.models.comment import Comment
from app.models.post import Post
from app.models.post_like import PostLike
from app.models.post_share import PostShare
from app.models.user import User
from app.schemas.comment import CommentOut
from app.schemas.post import PostListResponse, PostOut
from app.schemas.share import ShareOut
from app.schemas.user import UserBindPhoneRequest, UserProfile, UserProfileUpdate

router = APIRouter(prefix="/api/user", tags=["用户端用户"])
AVATAR_UPLOAD_ROOT = FilePath(__file__).resolve().parents[2] / "static" / "uploads" / "avatars"
ALLOWED_AVATAR_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data or {}}


def safe_avatar_filename(filename: str) -> str:
    stem = FilePath(filename or "avatar").stem
    suffix = FilePath(filename or "").suffix.lower() or ".png"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-") or "avatar"
    return f"{safe_stem}{suffix}"


def save_avatar_upload(file: UploadFile, user_id: str) -> tuple[str, int, str]:
    original_filename = safe_avatar_filename(file.filename or "avatar.png")
    suffix = FilePath(original_filename).suffix.lower()
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        raise fail(status.HTTP_400_BAD_REQUEST, "头像格式不正确，仅支持 jpg、jpeg、png、webp、gif")
    content = file.file.read()
    if not content:
        raise fail(status.HTTP_400_BAD_REQUEST, "头像文件不能为空")
    if len(content) > MAX_AVATAR_SIZE:
        raise fail(status.HTTP_400_BAD_REQUEST, "头像文件不能超过 5MB")
    md5 = hashlib.md5(content).hexdigest()
    upload_dir = AVATAR_UPLOAD_ROOT / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    relative_path = FilePath("uploads") / "avatars" / user_id / f"{md5}{suffix}"
    file_path = FilePath("static") / relative_path
    file_path.write_bytes(content)
    return f"/static/{relative_path.as_posix()}", len(content), md5


@router.get(
    "/profile",
    response_model=UserProfile,
    summary="我的资料",
    description="获取当前登录用户资料。用户身份从 Authorization Bearer Token 中解析。",
)
def get_profile(current_user: Annotated[User, Depends(get_current_user_required)]) -> UserProfile:
    return user_profile(current_user)


@router.put(
    "/profile",
    response_model=UserProfile,
    summary="编辑我的资料",
    description="更新当前登录用户资料。用户身份从 token 中获取，前端不传 userId。",
)
def update_profile(
    payload: UserProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> UserProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "phone":
            value = normalize_phone(value)
        elif field == "client_type":
            value = normalize_client_type(value)
        elif field == "client_subtype":
            value = normalize_client_subtype(value)
        setattr(current_user, field, value)
    current_user.last_time = utc_now()
    db.commit()
    db.refresh(current_user)
    return user_profile(current_user)


@router.post(
    "/profile/avatar",
    summary="上传头像",
    description="用户端上传头像接口。支持 jpg、jpeg、png、webp、gif，上传成功后自动更新当前用户 avatar 字段。",
)
def upload_profile_avatar(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    file: Annotated[UploadFile, File(description="头像图片文件，最大 5MB")],
) -> dict[str, object]:
    avatar_url, size, md5 = save_avatar_upload(file, current_user.user_id)
    current_user.avatar = avatar_url
    current_user.last_time = utc_now()
    db.commit()
    db.refresh(current_user)
    return ok(
        {
            "avatar": avatar_url,
            "url": avatar_url,
            "size": size,
            "md5": md5,
            "profile": user_profile(current_user).model_dump(),
        },
        "头像上传成功",
    )


@router.post(
    "/bindPhone",
    summary="绑定手机号",
    description="用户端换绑手机号。请求传 oldPhone、newPhone、code；测试验证码固定 123456。旧手机号保留展示，新手机号写入 newPhone，之后登录使用新手机号。",
)
@router.post(
    "/bind-phone",
    include_in_schema=False,
)
def bind_phone(
    payload: UserBindPhoneRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, object]:
    old_phone = normalize_phone(payload.old_phone)
    new_phone = normalize_phone(payload.new_phone)
    if not old_phone:
        raise fail(status.HTTP_400_BAD_REQUEST, "旧手机号不能为空")
    if not new_phone:
        raise fail(status.HTTP_400_BAD_REQUEST, "新手机号不能为空")
    if payload.code != "123456":
        raise fail(status.HTTP_400_BAD_REQUEST, "验证码错误")

    current_phone = current_user.phone or phone_from_user_id(current_user.user_id)
    if current_user.new_phone:
        raise fail(status.HTTP_400_BAD_REQUEST, "已绑定新手机号，不能重复绑定")
    if old_phone != current_phone:
        raise fail(status.HTTP_400_BAD_REQUEST, "旧手机号不正确")
    if new_phone == current_phone:
        raise fail(status.HTTP_400_BAD_REQUEST, "新手机号不能和当前手机号相同")

    target_user_id = mobile_user_id(new_phone)
    existing = (
        db.query(User)
        .filter(or_(User.phone == new_phone, User.new_phone == new_phone, User.user_id == target_user_id), User.id != current_user.id)
        .first()
    )
    if existing is not None:
        raise fail(status.HTTP_400_BAD_REQUEST, "该手机号已绑定其他用户")

    user = current_user
    if current_phone:
        user.phone = current_phone
        user.new_phone = new_phone
    else:
        user.phone = new_phone
    user.last_time = utc_now()
    db.commit()
    db.refresh(user)

    token = create_access_token(user.user_id)
    profile = user_profile(user).model_dump()
    return ok(
        {
            "user": profile,
            "profile": profile,
            "userId": user.user_id,
            "phone": user.phone,
            "newPhone": user.new_phone,
            "accessToken": token,
            "token": token,
        },
        "手机号绑定成功",
    )


@router.get(
    "/export",
    summary="用户端导出",
    description="用户端通用导出入口。target/type 默认 users，导出当前登录用户资料，支持 .xls 和 .xlsx。",
)
def export_user_data(
    current_user: Annotated[User, Depends(get_current_user_required)],
    target: Annotated[str, Query(description="导出类型，默认 users")] = "users",
    type_alias: Annotated[str | None, Query(alias="type", description="兼容旧参数 type", include_in_schema=False)] = None,
    format: Annotated[str, Query(pattern="^(xls|xlsx)$", description="导出格式：xls 或 xlsx")] = "xls",
) -> StreamingResponse:
    export_target = (type_alias or target or "users").strip().lower()
    if export_target not in {"users", "user", "profile"}:
        raise fail(status.HTTP_400_BAD_REQUEST, "暂不支持该导出类型")
    return user_export_response([current_user], format)


@router.post(
    "/import",
    summary="用户端导入",
    description="用户端通用导入入口。target/type 默认 users，导入当前登录用户资料，支持 .xls 和 .xlsx。",
)
def import_user_data(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    file: Annotated[UploadFile, File(description="Excel 文件，仅支持 .xls/.xlsx")],
    target: Annotated[str, Query(description="导入类型，默认 users")] = "users",
    type_alias: Annotated[str | None, Query(alias="type", description="兼容旧参数 type", include_in_schema=False)] = None,
) -> dict[str, object]:
    import_target = (type_alias or target or "users").strip().lower()
    if import_target not in {"users", "user", "profile"}:
        raise fail(status.HTTP_400_BAD_REQUEST, "暂不支持该导入类型")
    rows = read_user_import_rows(file.filename or "", file.file.read())
    row = rows[0]
    for field in ("phone", "clientType", "clientSubtype", "nickname", "avatar", "gender", "bio", "province", "city", "district"):
        value = row.get(field)
        if value:
            if field == "phone":
                current_user.phone = normalize_phone(value)
            elif field == "clientType":
                current_user.client_type = normalize_client_type(value)
            elif field == "clientSubtype":
                current_user.client_subtype = normalize_client_subtype(value)
            else:
                setattr(current_user, field, value)
    current_user.last_time = utc_now()
    db.commit()
    db.refresh(current_user)
    return ok(user_profile(current_user).model_dump(), "用户资料导入成功")


@router.get(
    "/posts",
    response_model=PostListResponse,
    summary="我的发布",
    description="获取当前登录用户发布的内容列表。",
)
def my_posts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，兼容 limit/offset 分页")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量，兼容 limit/offset 分页")] = 0,
    page: Annotated[int | None, Query(ge=1, description="页码，兼容 page/pageSize 分页")] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100, description="每页数量，兼容 page/pageSize 分页")] = None,
) -> PostListResponse:
    if page is not None:
        limit = page_size or limit
        offset = (page - 1) * limit
    base_query = db.query(Post).filter(
        Post.user_id == current_user.user_id, Post.is_deleted.is_(False)
    )
    total = base_query.count()
    posts = (
        base_query.options(joinedload(Post.author))
        .order_by(Post.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    liked_rows = (
        db.query(PostLike.post_id)
        .filter(
            PostLike.user_id == current_user.user_id,
            PostLike.post_id.in_([post.post_id for post in posts]),
        )
        .all()
    )
    liked = {row[0] for row in liked_rows}
    return PostListResponse(
        items=[post_out(post, current_user, post.post_id in liked) for post in posts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/likes",
    response_model=list[PostOut],
    summary="我的点赞",
    description="获取当前登录用户点赞过的内容列表。",
)
def my_likes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[PostOut]:
    posts = (
        db.query(Post)
        .join(PostLike, PostLike.post_id == Post.post_id)
        .options(joinedload(Post.author))
        .filter(PostLike.user_id == current_user.user_id, Post.is_deleted.is_(False))
        .order_by(PostLike.create_time.desc())
        .all()
    )
    return [post_out(post, current_user, is_liked=True) for post in posts]


@router.get(
    "/comments",
    response_model=list[CommentOut],
    summary="我的评论",
    description="获取当前登录用户发表过的评论列表。",
)
def my_comments(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[CommentOut]:
    comments = (
        db.query(Comment)
        .filter(Comment.user_id == current_user.user_id, Comment.is_deleted.is_(False))
        .order_by(Comment.create_time.desc())
        .all()
    )
    return [comment_out(comment) for comment in comments]


@router.get(
    "/shares",
    response_model=list[ShareOut],
    summary="我的分享",
    description="获取当前登录用户分享过的内容记录。",
)
def my_shares(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[ShareOut]:
    shares = (
        db.query(PostShare)
        .filter(PostShare.user_id == current_user.user_id)
        .order_by(PostShare.create_time.desc())
        .all()
    )
    return [share_out(share) for share in shares]
