from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.admin import fail, read_user_import_rows, user_export_response
from app.api.deps import get_current_user_required
from app.api.serializers import comment_out, post_out, share_out, user_profile
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
from app.schemas.user import UserProfile, UserProfileUpdate

router = APIRouter(prefix="/api/user", tags=["用户端用户"])


def ok(data: object | None = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data or {}}


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
        setattr(current_user, field, value)
    current_user.last_time = utc_now()
    db.commit()
    db.refresh(current_user)
    return user_profile(current_user)


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
    for field in ("phone", "nickname", "avatar", "gender", "province", "city", "district"):
        value = row.get(field)
        if value:
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
