from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user_optional, get_current_user_required
from app.api.serializers import comment_out, post_out, share_out
from app.api.utils import new_business_id
from app.core.configs import IMAGE_SUFFIXES, VIDEO_SUFFIXES
from app.db.base import utc_now
from app.db.session import get_db
from app.models.comment import Comment
from app.models.post import Post
from app.models.post_like import PostLike
from app.models.post_share import PostShare
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentListResponse, CommentOut
from app.schemas.post import LikeResponse, PostCreate, PostListResponse, PostOut, PostUpdate
from app.schemas.share import ShareCreate, ShareOut

router = APIRouter(prefix="/api/posts", tags=["用户端内容"])

VISIBLE_POST_STATUSES = ("online", "published")
PUBLIC_VISIBILITY = "public"


def _media_kind_from_url(url: str) -> str | None:
    path = url.split("?", 1)[0].lower()
    if path.endswith(IMAGE_SUFFIXES) or "/image/" in path:
        return "image"
    if path.endswith(VIDEO_SUFFIXES) or "/video/" in path:
        return "video"
    return None


def _media_kind(item: object) -> str | None:
    if isinstance(item, str):
        return _media_kind_from_url(item)
    if isinstance(item, dict):
        explicit_type = str(item.get("type") or item.get("mediaType") or "").strip().lower()
        if explicit_type in {"image", "video"}:
            return explicit_type
        url = item.get("url")
        if isinstance(url, str):
            return _media_kind_from_url(url)
    return None


def _normalize_media_item(item: object, fallback_type: str | None = None) -> object:
    resolved_type = _media_kind(item) or fallback_type
    if isinstance(item, str):
        if fallback_type == "video":
            return {"url": item, "type": "video", "mediaType": "video"}
        return item
    if isinstance(item, dict):
        normalized = dict(item)
        if resolved_type:
            normalized.setdefault("type", resolved_type)
            normalized.setdefault("mediaType", resolved_type)
        return normalized
    return item


def _combined_media(
    images: list[object] | None = None,
    videos: list[object] | None = None,
    media: list[object] | None = None,
) -> list[object]:
    combined: list[object] = []
    for item in media or []:
        combined.append(_normalize_media_item(item))
    for item in images or []:
        combined.append(_normalize_media_item(item, "image"))
    for item in videos or []:
        combined.append(_normalize_media_item(item, "video"))
    return combined


def _normalize_topics(topics: list[object] | None) -> list[object]:
    normalized: list[object] = []
    for topic in topics or []:
        if isinstance(topic, str):
            value = topic.strip()
            if value:
                normalized.append(value)
            continue
        if isinstance(topic, dict):
            value = topic.get("label") or topic.get("name") or topic.get("title") or topic.get("value") or topic.get("topic")
            if isinstance(value, str) and value.strip():
                normalized.append(value.strip())
            else:
                normalized.append(topic)
            continue
        if topic is not None:
            normalized.append(topic)
    return normalized


def _payload_field_was_set(payload: object, field_name: str) -> bool:
    fields_set = getattr(payload, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(payload, "__fields_set__", set())
    return field_name in fields_set


def _page_to_limit_offset(page: int | None, page_size: int | None, limit: int, offset: int) -> tuple[int, int]:
    if page is None:
        return limit, offset
    resolved_limit = page_size or limit
    return resolved_limit, (page - 1) * resolved_limit


def _get_visible_post(db: Session, post_id: str) -> Post:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(
            Post.post_id == post_id,
            Post.is_deleted.is_(False),
            Post.status.in_(VISIBLE_POST_STATUSES),
            Post.visibility == PUBLIC_VISIBILITY,
        )
        .one_or_none()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _get_post_for_detail(db: Session, post_id: str, current_user: User | None) -> Post:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.post_id == post_id, Post.is_deleted.is_(False))
        .one_or_none()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    is_owner = current_user is not None and current_user.user_id == post.user_id
    if post.status in VISIBLE_POST_STATUSES and (post.visibility == PUBLIC_VISIBILITY or is_owner):
        return post
    if is_owner:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


def _get_owner_post(db: Session, post_id: str, current_user: User) -> Post:
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.post_id == post_id, Post.is_deleted.is_(False))
        .one_or_none()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can edit")
    return post


def _liked_post_ids(db: Session, user: User | None, post_ids: list[str]) -> set[str]:
    if user is None or not post_ids:
        return set()
    rows = (
        db.query(PostLike.post_id)
        .filter(PostLike.user_id == user.user_id, PostLike.post_id.in_(post_ids))
        .all()
    )
    return {row[0] for row in rows}


def _comment_tree(db: Session, comments: list[Comment]) -> list[CommentOut]:
    user_ids = {comment.user_id for comment in comments}
    user_ids.update(comment.reply_to_user_id for comment in comments if comment.reply_to_user_id)
    users = {
        user.user_id: user
        for user in db.query(User).filter(User.user_id.in_(user_ids)).all()
    } if user_ids else {}
    nodes = {
        comment.comment_id: comment_out(
            comment,
            users.get(comment.user_id),
            users.get(comment.reply_to_user_id),
        )
        for comment in comments
    }
    by_id = {comment.comment_id: comment for comment in comments}
    root_ids: dict[str, str] = {}

    def root_id_for(comment: Comment) -> str:
        cached = root_ids.get(comment.comment_id)
        if cached:
            return cached
        seen = {comment.comment_id}
        current = comment
        while current.parent_id and current.parent_id in by_id and current.parent_id not in seen:
            current = by_id[current.parent_id]
            seen.add(current.comment_id)
        root_ids[comment.comment_id] = current.comment_id
        return current.comment_id

    roots: list[CommentOut] = []
    for comment in sorted(comments, key=lambda item: item.create_time):
        node = nodes[comment.comment_id]
        if comment.parent_id:
            root = nodes.get(root_id_for(comment))
            if root and root.commentId != node.commentId:
                node.children = []
                node.replies = []
                node.replyCount = 0
                root.children.append(node)
                root.replies = root.children
                root.replyCount = len(root.children)
            else:
                roots.append(node)
        else:
            roots.append(node)
    return roots


def _comment_nodes(db: Session, comments: list[Comment]) -> dict[str, CommentOut]:
    user_ids = {comment.user_id for comment in comments}
    user_ids.update(comment.reply_to_user_id for comment in comments if comment.reply_to_user_id)
    users = {
        user.user_id: user
        for user in db.query(User).filter(User.user_id.in_(user_ids)).all()
    } if user_ids else {}
    return {
        comment.comment_id: comment_out(
            comment,
            users.get(comment.user_id),
            users.get(comment.reply_to_user_id),
        )
        for comment in comments
    }


def _thread_root_id(comments_by_id: dict[str, Comment], comment: Comment) -> str:
    seen = {comment.comment_id}
    current = comment
    while current.parent_id and current.parent_id in comments_by_id and current.parent_id not in seen:
        current = comments_by_id[current.parent_id]
        seen.add(current.comment_id)
    return current.comment_id


def _flatten_comment_replies(db: Session, comments: list[Comment], root_comment_id: str) -> list[CommentOut]:
    nodes = _comment_nodes(db, comments)
    comments_by_id = {comment.comment_id: comment for comment in comments}
    replies: list[CommentOut] = []
    for comment in sorted(comments, key=lambda item: item.create_time):
        if comment.comment_id == root_comment_id:
            continue
        if _thread_root_id(comments_by_id, comment) != root_comment_id:
            continue
        node = nodes[comment.comment_id]
        node.children = []
        node.replies = []
        node.replyCount = 0
        replies.append(node)
    return replies


def _resolve_parent_comment(db: Session, post_id: str, payload: CommentCreate) -> Comment | None:
    if payload.parentId:
        parent = (
            db.query(Comment)
            .filter(
                Comment.comment_id == payload.parentId,
                Comment.post_id == post_id,
                Comment.is_deleted.is_(False),
            )
            .one_or_none()
        )
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")
        return parent
    if payload.replyToUserId:
        return (
            db.query(Comment)
            .filter(
                Comment.post_id == post_id,
                Comment.user_id == payload.replyToUserId,
                Comment.is_deleted.is_(False),
            )
            .order_by(Comment.create_time.desc())
            .first()
        )
    return None


def _resolve_feed_type(*values: str | None) -> str:
    for value in values:
        if not value:
            continue
        normalized = value.strip().lower()
        if normalized in {"recommend", "recommended", "hot", "score", "推荐", "热门"}:
            return "recommend"
        if normalized in {"latest", "new", "newest", "time", "最新"}:
            return "latest"
    return "latest"


def _resolve_keyword(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


@router.get(
    "",
    response_model=PostListResponse,
    summary="首页内容列表",
    description="公开内容列表接口。游客可访问；带 token 时会返回 isLiked/isOwner 等当前用户视角字段。",
)
def list_posts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，兼容 limit/offset 分页")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量，兼容 limit/offset 分页")] = 0,
    page: Annotated[int | None, Query(ge=1, description="页码，兼容 page/pageSize 分页")] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100, description="每页数量，兼容 page/pageSize 分页")] = None,
    tab: Annotated[str | None, Query(description="内容流类型：recommend 推荐，latest 最新")] = None,
    type_alias: Annotated[str | None, Query(alias="type", description="兼容旧参数 type", include_in_schema=False)] = None,
    sort: Annotated[str | None, Query(description="排序类型：recommend/latest")] = None,
    mode: Annotated[str | None, Query(description="兼容模式参数：recommend/latest")] = None,
    keyword: Annotated[str | None, Query(description="搜索关键词：匹配动态内容、用户昵称、用户 ID、地点")] = None,
    search: Annotated[str | None, Query(description="兼容搜索参数 search", include_in_schema=False)] = None,
    q: Annotated[str | None, Query(description="兼容搜索参数 q", include_in_schema=False)] = None,
    province: Annotated[str | None, Query(description="省份筛选")] = None,
    city: Annotated[str | None, Query(description="城市筛选")] = None,
    district: Annotated[str | None, Query(description="区县筛选")] = None,
    location: Annotated[str | None, Query(description="地点关键词筛选")] = None,
) -> PostListResponse:
    limit, offset = _page_to_limit_offset(page, page_size, limit, offset)
    feed_type = _resolve_feed_type(tab, type_alias, sort, mode)
    resolved_keyword = _resolve_keyword(keyword, search, q)
    base_query = db.query(Post).filter(
        Post.is_deleted.is_(False),
        Post.status.in_(VISIBLE_POST_STATUSES),
        Post.visibility == PUBLIC_VISIBILITY,
    )
    if any([resolved_keyword, province, city, district, location]):
        base_query = base_query.join(User, User.user_id == Post.user_id)
    if resolved_keyword:
        like_keyword = f"%{resolved_keyword}%"
        base_query = base_query.filter(
            or_(
                Post.content.ilike(like_keyword),
                Post.location.ilike(like_keyword),
                Post.province.ilike(like_keyword),
                Post.city.ilike(like_keyword),
                Post.district.ilike(like_keyword),
                User.nickname.ilike(like_keyword),
                User.user_id.ilike(like_keyword),
                User.province.ilike(like_keyword),
                User.city.ilike(like_keyword),
                User.district.ilike(like_keyword),
            )
        )
    if province:
        base_query = base_query.filter(or_(Post.province.ilike(f"%{province}%"), User.province.ilike(f"%{province}%")))
    if city:
        base_query = base_query.filter(or_(Post.city.ilike(f"%{city}%"), User.city.ilike(f"%{city}%")))
    if district:
        base_query = base_query.filter(or_(Post.district.ilike(f"%{district}%"), User.district.ilike(f"%{district}%")))
    if location:
        like_location = f"%{location}%"
        base_query = base_query.filter(
            or_(
                Post.location.ilike(like_location),
                Post.province.ilike(like_location),
                Post.city.ilike(like_location),
                Post.district.ilike(like_location),
                User.province.ilike(like_location),
                User.city.ilike(like_location),
                User.district.ilike(like_location),
            )
        )
    total = base_query.with_entities(func.count(Post.id)).scalar() or 0
    if feed_type == "recommend":
        order_by = (
            (Post.like_count * 3 + Post.comment_count * 2 + Post.share_count * 2).desc(),
            Post.create_time.desc(),
        )
    else:
        order_by = (Post.create_time.desc(),)
    posts = (
        base_query.options(joinedload(Post.author))
        .order_by(*order_by)
        .offset(offset)
        .limit(limit)
        .all()
    )
    liked = _liked_post_ids(db, current_user, [post.post_id for post in posts])
    return PostListResponse(
        items=[post_out(post, current_user, post.post_id in liked) for post in posts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{postId}/comments",
    response_model=CommentListResponse,
    summary="内容评论列表",
    description="获取某条内容下的分页评论和回复列表。一级评论分页，所有内部回复平铺在对应一级评论的 children/replies 中。",
)
def list_post_comments(
    postId: Annotated[str, Path(description="内容 ID")],
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int | None, Query(ge=1, description="页码")] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100, description="每页数量")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，兼容移动端分页")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量，兼容移动端分页")] = 0,
) -> CommentListResponse:
    post_id = postId
    _get_visible_post(db, post_id)
    resolved_limit, resolved_offset = _page_to_limit_offset(page, page_size, limit, offset)
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.is_deleted.is_(False))
        .order_by(Comment.create_time.asc())
        .all()
    )
    roots = _comment_tree(db, comments)
    response.headers["X-Total-Count"] = str(len(roots))
    response.headers["X-Comment-Total"] = str(len(comments))
    response.headers["X-Limit"] = str(resolved_limit)
    response.headers["X-Offset"] = str(resolved_offset)
    page_items = roots[resolved_offset : resolved_offset + resolved_limit]
    resolved_page = (resolved_offset // resolved_limit) + 1
    return CommentListResponse(
        comments=page_items,
        items=page_items,
        total=len(roots),
        commentTotal=len(comments),
        limit=resolved_limit,
        offset=resolved_offset,
        page=resolved_page,
        pageSize=resolved_limit,
        hasMore=resolved_offset + resolved_limit < len(roots),
    )


@router.get(
    "/{postId}/comments/{commentId}/replies",
    response_model=CommentListResponse,
    summary="评论回复分页列表",
    description="点击某条评论的回复入口时调用。返回该评论所在一级评论下的所有内部回复，按时间平铺分页展示。",
)
@router.get(
    "/{postId}/comments/{commentId}/children",
    response_model=CommentListResponse,
    include_in_schema=False,
)
def list_comment_replies(
    postId: Annotated[str, Path(description="内容 ID")],
    commentId: Annotated[str, Path(description="评论 ID")],
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int | None, Query(ge=1, description="页码")] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100, description="每页数量")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，兼容移动端分页")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量，兼容移动端分页")] = 0,
) -> CommentListResponse:
    post_id = postId
    comment_id = commentId
    _get_visible_post(db, post_id)
    resolved_limit, resolved_offset = _page_to_limit_offset(page, page_size, limit, offset)
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.is_deleted.is_(False))
        .order_by(Comment.create_time.asc())
        .all()
    )
    comments_by_id = {comment.comment_id: comment for comment in comments}
    source_comment = comments_by_id.get(comment_id)
    if source_comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    root_comment_id = _thread_root_id(comments_by_id, source_comment)
    replies = _flatten_comment_replies(db, comments, root_comment_id)
    requested_offset = resolved_offset
    if page is None and replies and requested_offset == len(replies):
        resolved_offset = len(replies) - 1
    page_items = replies[resolved_offset : resolved_offset + resolved_limit]
    resolved_page = (resolved_offset // resolved_limit) + 1
    response.headers["X-Total-Count"] = str(len(replies))
    response.headers["X-Comment-Total"] = str(len(replies))
    response.headers["X-Limit"] = str(resolved_limit)
    response.headers["X-Offset"] = str(resolved_offset)
    response.headers["X-Requested-Offset"] = str(requested_offset)
    response.headers["X-Root-Comment-Id"] = root_comment_id
    return CommentListResponse(
        comments=page_items,
        items=page_items,
        total=len(replies),
        commentTotal=len(replies),
        limit=resolved_limit,
        offset=resolved_offset,
        page=resolved_page,
        pageSize=resolved_limit,
        hasMore=resolved_offset + resolved_limit < len(replies),
    )


@router.post(
    "",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    summary="发布内容",
    description="登录用户发布新内容；发布者 userId 从 token 中获取，前端不传 userId。",
)
def create_post(
    payload: PostCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PostOut:
    post = Post(
        post_id=new_business_id("post"),
        user_id=current_user.user_id,
        content=payload.content,
        images=_combined_media(payload.images, payload.videos, payload.media),
        topics=_normalize_topics(payload.topics),
        location=payload.location,
        province=payload.province,
        city=payload.city,
        district=payload.district,
        visibility=payload.visibility,
        status=payload.status,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.author = current_user
    return post_out(post, current_user, is_liked=False)


@router.get(
    "/{postId}",
    response_model=PostOut,
    summary="内容详情",
    description="公开内容详情接口。带 token 时返回当前用户是否点赞、是否作者、是否可编辑等字段。",
)
def get_post_detail(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> PostOut:
    post_id = postId
    post = _get_post_for_detail(db, post_id, current_user)
    liked = bool(
        current_user
        and db.query(PostLike.id)
        .filter(PostLike.post_id == post_id, PostLike.user_id == current_user.user_id)
        .first()
    )
    post.last_time = utc_now()
    db.commit()
    db.refresh(post)
    return post_out(post, current_user, liked)


@router.put(
    "/{postId}",
    response_model=PostOut,
    summary="编辑内容",
    description="登录用户编辑自己发布的内容；后端校验当前用户是否为发布者。",
)
def update_post(
    postId: Annotated[str, Path(description="内容 ID")],
    payload: PostUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PostOut:
    post_id = postId
    post = _get_owner_post(db, post_id, current_user)

    if payload.content is not None:
        post.content = payload.content
    if any(_payload_field_was_set(payload, field_name) for field_name in ("images", "videos", "media")):
        post.images = _combined_media(payload.images, payload.videos, payload.media)
    if payload.topics is not None:
        post.topics = _normalize_topics(payload.topics)
    if payload.location is not None:
        post.location = payload.location
    if payload.province is not None:
        post.province = payload.province
    if payload.city is not None:
        post.city = payload.city
    if payload.district is not None:
        post.district = payload.district
    if payload.visibility is not None:
        post.visibility = payload.visibility
    if payload.status is not None:
        post.status = payload.status
    post.last_time = utc_now()

    db.commit()
    db.refresh(post)
    liked = bool(
        db.query(PostLike.id)
        .filter(PostLike.post_id == post_id, PostLike.user_id == current_user.user_id)
        .first()
    )
    return post_out(post, current_user, liked)


@router.delete(
    "/{postId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除内容",
    description="登录用户删除自己发布的内容；后端做软删除。",
)
def delete_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> None:
    post_id = postId
    post = _get_owner_post(db, post_id, current_user)

    now = utc_now()
    post.is_deleted = True
    post.delete_time = now
    post.last_time = now
    db.commit()


@router.post(
    "/{postId}/like",
    response_model=LikeResponse,
    summary="点赞/取消点赞",
    description="登录用户点赞或取消点赞内容。重复调用会在点赞和取消点赞之间切换。",
)
def toggle_like(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> LikeResponse:
    post_id = postId
    post = _get_visible_post(db, post_id)
    like = (
        db.query(PostLike)
        .filter(PostLike.post_id == post_id, PostLike.user_id == current_user.user_id)
        .one_or_none()
    )
    if like is None:
        db.add(PostLike(post_id=post_id, user_id=current_user.user_id))
        post.like_count += 1
        is_liked = True
    else:
        db.delete(like)
        post.like_count = max(0, post.like_count - 1)
        is_liked = False

    post.last_time = utc_now()
    db.commit()
    db.refresh(post)
    return LikeResponse(postId=post_id, isLiked=is_liked, likeCount=post.like_count)


@router.post(
    "/{postId}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="发表评论/回复",
    description="登录用户对内容发表评论，也可通过 parentId/replyToUserId 发表回复。",
)
def create_comment(
    postId: Annotated[str, Path(description="内容 ID")],
    payload: CommentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> CommentOut:
    post_id = postId
    post = _get_visible_post(db, post_id)
    parent = _resolve_parent_comment(db, post_id, payload)
    parent_id = parent.comment_id if parent is not None else None
    reply_to_user_id = payload.replyToUserId or (parent.user_id if parent is not None else None)
    comment = Comment(
        comment_id=new_business_id("cmt"),
        post_id=post_id,
        user_id=current_user.user_id,
        content=payload.content,
        parent_id=parent_id,
        reply_to_user_id=reply_to_user_id,
    )
    post.comment_count += 1
    post.last_time = utc_now()
    db.add(comment)
    db.commit()
    db.refresh(comment)
    reply_to_user = db.query(User).filter(User.user_id == reply_to_user_id).one_or_none() if reply_to_user_id else None
    return comment_out(comment, current_user, reply_to_user)


@router.post(
    "/{postId}/share",
    response_model=ShareOut,
    status_code=status.HTTP_201_CREATED,
    summary="分享内容",
    description="记录内容分享次数。游客可调用；登录用户会额外保存分享记录。",
)
def create_share(
    postId: Annotated[str, Path(description="内容 ID")],
    payload: ShareCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> ShareOut:
    post_id = postId
    post = _get_visible_post(db, post_id)
    post.share_count += 1
    post.last_time = utc_now()
    if current_user is None:
        db.commit()
        return ShareOut(
            postId=post_id,
            userId="",
            scene=payload.scene,
            platform=payload.platform,
            createdAt=post.last_time,
        )

    share = PostShare(
        post_id=post_id,
        user_id=current_user.user_id,
        scene=payload.scene,
        platform=payload.platform,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share_out(share)
