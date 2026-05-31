from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user_optional, get_current_user_required
from app.api.serializers import comment_out, post_out, share_out
from app.api.utils import new_business_id
from app.db.base import utc_now
from app.db.session import get_db
from app.models.comment import Comment
from app.models.post import Post
from app.models.post_like import PostLike
from app.models.post_share import PostShare
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut
from app.schemas.post import LikeResponse, PostCreate, PostListResponse, PostOut, PostUpdate
from app.schemas.share import ShareCreate, ShareOut

router = APIRouter(prefix="/api/posts", tags=["posts"])

VISIBLE_POST_STATUSES = ("online", "published")


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
        )
        .one_or_none()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
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


@router.get("", response_model=PostListResponse)
def list_posts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100)] = None,
) -> PostListResponse:
    limit, offset = _page_to_limit_offset(page, page_size, limit, offset)
    base_query = db.query(Post).filter(
        Post.is_deleted.is_(False),
        Post.status.in_(VISIBLE_POST_STATUSES),
    )
    total = base_query.with_entities(func.count(Post.id)).scalar() or 0
    posts = (
        base_query.options(joinedload(Post.author))
        .order_by(Post.create_time.desc())
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


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_post_comments(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
) -> list[CommentOut]:
    _get_visible_post(db, post_id)
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.is_deleted.is_(False))
        .order_by(Comment.create_time.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [comment_out(comment) for comment in comments]


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PostOut:
    post = Post(
        post_id=new_business_id("post"),
        user_id=current_user.user_id,
        content=payload.content,
        images=payload.images,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.author = current_user
    return post_out(post, current_user, is_liked=False)


@router.get("/{post_id}", response_model=PostOut)
def get_post_detail(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> PostOut:
    post = _get_visible_post(db, post_id)
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


@router.put("/{post_id}", response_model=PostOut)
def update_post(
    post_id: str,
    payload: PostUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PostOut:
    post = _get_visible_post(db, post_id)
    if post.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can edit")

    if payload.content is not None:
        post.content = payload.content
    if payload.images is not None:
        post.images = payload.images
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


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> None:
    post = _get_visible_post(db, post_id)
    if post.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can delete")

    now = utc_now()
    post.is_deleted = True
    post.delete_time = now
    post.last_time = now
    db.commit()


@router.post("/{post_id}/like", response_model=LikeResponse)
def toggle_like(
    post_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> LikeResponse:
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


@router.post("/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: str,
    payload: CommentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> CommentOut:
    post = _get_visible_post(db, post_id)
    comment = Comment(
        comment_id=new_business_id("cmt"),
        post_id=post_id,
        user_id=current_user.user_id,
        content=payload.content,
        parent_id=payload.parentId,
        reply_to_user_id=payload.replyToUserId,
    )
    post.comment_count += 1
    post.last_time = utc_now()
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment_out(comment)


@router.post("/{post_id}/share", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
def create_share(
    post_id: str,
    payload: ShareCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> ShareOut:
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
