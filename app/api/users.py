from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

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

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: Annotated[User, Depends(get_current_user_required)]) -> UserProfile:
    return user_profile(current_user)


@router.put("/profile", response_model=UserProfile)
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


@router.get("/posts", response_model=PostListResponse)
def my_posts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PostListResponse:
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


@router.get("/likes", response_model=list[PostOut])
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


@router.get("/comments", response_model=list[CommentOut])
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


@router.get("/shares", response_model=list[ShareOut])
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

