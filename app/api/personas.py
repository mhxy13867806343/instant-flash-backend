from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_current_user_required
from app.api.utils import new_business_id
from app.db.base import utc_now
from app.db.session import get_db
from app.models import User, UserPersona, UserPersonaComment, UserPersonaFavorite
from app.schemas.persona import (
    PersonaCommentCreatePayload,
    PersonaCommentOut,
    PersonaCreatePayload,
    PersonaOut,
    PersonaUpdatePayload,
)

router = APIRouter(prefix="/api/user/personas", tags=["用户画像"])


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data or {}}


def _persona_out(p: UserPersona, current_user_id: str | None, db: Session) -> PersonaOut:
    owner = db.query(User).filter(User.user_id == p.user_id).first()
    comment_count = db.query(UserPersonaComment).filter(UserPersonaComment.persona_id == p.persona_id).count()
    favorite_count = db.query(UserPersonaFavorite).filter(UserPersonaFavorite.persona_id == p.persona_id).count()

    is_favorited = False
    if current_user_id:
        is_favorited = db.query(UserPersonaFavorite).filter(
            UserPersonaFavorite.persona_id == p.persona_id,
            UserPersonaFavorite.user_id == current_user_id,
        ).first() is not None

    return PersonaOut(
        personaId=p.persona_id,
        userId=p.user_id,
        title=p.title,
        content=p.content,
        images=p.images or [],
        tags=p.tags or [],
        privacy=p.privacy,
        expireTime=p.expire_time,
        viewCount=p.view_count,
        createTime=p.create_time,
        nickname=owner.nickname if owner else None,
        avatar=owner.avatar if owner else None,
        commentCount=comment_count,
        favoriteCount=favorite_count,
        isFavorited=is_favorited,
    )


@router.post(
    "",
    response_model=PersonaOut,
    summary="创建用户画像",
    description="支持公开和私有两类。如果设为公开，必须传倒计时 durationMinutes（180分钟至3天内）。",
)
def create_persona(
    payload: PersonaCreatePayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PersonaOut:
    expire_time = None
    if payload.privacy == "public":
        expire_time = utc_now() + timedelta(minutes=payload.duration_minutes)

    p = UserPersona(
        persona_id=new_business_id("per"),
        user_id=current_user.user_id,
        title=payload.title,
        content=payload.content,
        images=payload.images,
        tags=payload.tags,
        privacy=payload.privacy,
        expire_time=expire_time,
        view_count=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _persona_out(p, current_user.user_id, db)


@router.put(
    "/{persona_id}",
    response_model=PersonaOut,
    summary="更新用户画像",
    description="更新画像信息。如果可见性变更为私有，会自动彻底清空原有的评论与收藏数据。",
)
def update_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    payload: PersonaUpdatePayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PersonaOut:
    p = db.query(UserPersona).filter(
        UserPersona.persona_id == persona_id,
        UserPersona.user_id == current_user.user_id,
    ).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到该用户画像，或您无权编辑")

    # Visible state cleanup handling
    if payload.privacy == "private" and p.privacy == "public":
        # Delete comments & favorites
        db.query(UserPersonaComment).filter(UserPersonaComment.persona_id == persona_id).delete(synchronize_session=False)
        db.query(UserPersonaFavorite).filter(UserPersonaFavorite.persona_id == persona_id).delete(synchronize_session=False)
        p.expire_time = None
    elif payload.privacy == "public" and p.privacy == "private":
        # Must provide duration to transition to public
        if payload.duration_minutes is None:
            raise fail(status.HTTP_400_BAD_REQUEST, "私有变更为公开时，必须提供倒计时时长 durationMinutes")
        p.expire_time = utc_now() + timedelta(minutes=payload.duration_minutes)
    elif p.privacy == "public" and payload.duration_minutes is not None:
        # Just update expiration time for public one
        p.expire_time = utc_now() + timedelta(minutes=payload.duration_minutes)

    if payload.title is not None:
        p.title = payload.title
    if payload.content is not None:
        p.content = payload.content
    if payload.images is not None:
        p.images = payload.images
    if payload.tags is not None:
        p.tags = payload.tags
    if payload.privacy is not None:
        p.privacy = payload.privacy

    db.commit()
    db.refresh(p)
    return _persona_out(p, current_user.user_id, db)


@router.delete(
    "/{persona_id}",
    summary="删除用户画像",
    description="彻底删除该画像以及关联的评论和收藏。",
)
def delete_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    p = db.query(UserPersona).filter(
        UserPersona.persona_id == persona_id,
        UserPersona.user_id == current_user.user_id,
    ).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到该画像，或您无权删除")

    # Cascade delete is handled by database ON DELETE CASCADE, but sqlalchemy relationships also trigger it.
    db.delete(p)
    db.commit()
    return ok(message="画像删除成功，相应的所有状态已更新清理")


@router.get(
    "/my",
    response_model=list[PersonaOut],
    summary="获取我的用户画像列表",
)
def list_my_personas(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PersonaOut]:
    items = db.query(UserPersona).filter(
        UserPersona.user_id == current_user.user_id
    ).order_by(UserPersona.create_time.desc()).offset((page - 1) * limit).limit(limit).all()

    return [_persona_out(x, current_user.user_id, db) for x in items]


@router.get(
    "/feed",
    response_model=list[PersonaOut],
    summary="获取公共用户画像流",
    description="仅获取处于公开可见状态，且失效倒计时未结束的画像列表。",
)
def get_personas_feed(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PersonaOut]:
    now = utc_now()
    items = db.query(UserPersona).filter(
        UserPersona.privacy == "public",
        UserPersona.expire_time > now,
    ).order_by(UserPersona.create_time.desc()).offset((page - 1) * limit).limit(limit).all()

    uid = current_user.user_id if current_user else None
    return [_persona_out(x, uid, db) for x in items]


@router.get(
    "/{persona_id}",
    response_model=PersonaOut,
    summary="查看用户画像详情",
    description="查看详情，非所有者访问会增加浏览量。非所有者无法查看私有或已过期的画像。",
)
def get_persona_detail(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> PersonaOut:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户画像未找到")

    uid = current_user.user_id if current_user else None
    is_owner = (uid == p.user_id)

    # Access validation: non-owners cannot see private or expired
    if not is_owner:
        if p.privacy == "private":
            raise fail(status.HTTP_404_NOT_FOUND, "该画像已被设为私有，暂不可查看")
        if p.expire_time and p.expire_time <= utc_now():
            raise fail(status.HTTP_404_NOT_FOUND, "该公开画像已过期失效")

        # Increment view count
        p.view_count += 1
        db.commit()
        db.refresh(p)

    return _persona_out(p, uid, db)


# ---------------------------------------------------------------------------
# 画像评论接口 (Persona Comments)
# ---------------------------------------------------------------------------

@router.post(
    "/{persona_id}/comments",
    response_model=PersonaCommentOut,
    summary="发表画像评论",
    description="仅限其他用户发表评论，作者本人不能评论自己的画像。只有单层结构。",
)
def comment_on_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    payload: PersonaCommentCreatePayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> PersonaCommentOut:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到目标画像")

    # Author check
    if p.user_id == current_user.user_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "限其他用户评论，您不能评论自己的画像")

    # Access check for private/expired
    if p.privacy == "private":
        raise fail(status.HTTP_404_NOT_FOUND, "画像已设为私有，无法评论")
    if p.expire_time and p.expire_time <= utc_now():
        raise fail(status.HTTP_404_NOT_FOUND, "画像已过期，无法评论")

    comment = UserPersonaComment(
        comment_id=new_business_id("pcom"),
        persona_id=persona_id,
        user_id=current_user.user_id,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return PersonaCommentOut(
        commentId=comment.comment_id,
        personaId=comment.persona_id,
        userId=comment.user_id,
        content=comment.content,
        createTime=comment.create_time,
        nickname=current_user.nickname,
        avatar=current_user.avatar,
    )


@router.get(
    "/{persona_id}/comments",
    response_model=list[PersonaCommentOut],
    summary="获取画像评论列表（分页）",
)
def list_persona_comments(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PersonaCommentOut]:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户画像未找到")

    # Fetch comments join User
    rows = db.query(UserPersonaComment, User).join(
        User, UserPersonaComment.user_id == User.user_id
    ).filter(
        UserPersonaComment.persona_id == persona_id
    ).order_by(
        UserPersonaComment.create_time.desc()
    ).offset((page - 1) * limit).limit(limit).all()

    result = []
    for comment, user in rows:
        result.append(
            PersonaCommentOut(
                commentId=comment.comment_id,
                personaId=comment.persona_id,
                userId=comment.user_id,
                content=comment.content,
                createTime=comment.create_time,
                nickname=user.nickname,
                avatar=user.avatar,
            )
        )
    return result


@router.delete(
    "/comments/{comment_id}",
    summary="删除画像评论",
    description="仅评论者自己，或者画像的所有者，有权删除评论。",
)
def delete_persona_comment(
    comment_id: Annotated[str, Path(description="评论 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    comment = db.query(UserPersonaComment).filter(UserPersonaComment.comment_id == comment_id).first()
    if comment is None:
        raise fail(status.HTTP_404_NOT_FOUND, "评论未找到")

    persona = db.query(UserPersona).filter(UserPersona.persona_id == comment.persona_id).first()
    is_persona_owner = persona and (persona.user_id == current_user.user_id)
    is_commenter = (comment.user_id == current_user.user_id)

    if not is_commenter and not is_persona_owner:
        raise fail(status.HTTP_403_FORBIDDEN, "无权删除此评论")

    db.delete(comment)
    db.commit()
    return ok(message="评论删除成功")


# ---------------------------------------------------------------------------
# 画像收藏接口 (Persona Favorites)
# ---------------------------------------------------------------------------

@router.post(
    "/{persona_id}/favorite",
    summary="收藏用户画像",
    description="收藏别人的公开画像。不能重复收藏。",
)
def favorite_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户画像未找到")

    # Author cannot check or rather limit: usually users don't favorite their own but it's fine.
    # Check access for private/expired
    is_owner = (p.user_id == current_user.user_id)
    if not is_owner:
        if p.privacy == "private":
            raise fail(status.HTTP_404_NOT_FOUND, "该画像已被设为私有，暂不可收藏")
        if p.expire_time and p.expire_time <= utc_now():
            raise fail(status.HTTP_404_NOT_FOUND, "该公开画像已失效，不可收藏")

    exists = db.query(UserPersonaFavorite).filter(
        UserPersonaFavorite.persona_id == persona_id,
        UserPersonaFavorite.user_id == current_user.user_id,
    ).first()
    if exists:
        raise fail(status.HTTP_400_BAD_REQUEST, "您已收藏过此用户画像")

    fav = UserPersonaFavorite(
        favorite_id=new_business_id("pfav"),
        persona_id=persona_id,
        user_id=current_user.user_id,
    )
    db.add(fav)
    db.commit()
    return ok(message="画像收藏成功")


@router.delete(
    "/{persona_id}/favorite",
    summary="取消收藏用户画像",
)
def unfavorite_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict[str, Any]:
    fav = db.query(UserPersonaFavorite).filter(
        UserPersonaFavorite.persona_id == persona_id,
        UserPersonaFavorite.user_id == current_user.user_id,
    ).first()
    if fav is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未收藏过此画像，无法取消")

    db.delete(fav)
    db.commit()
    return ok(message="画像取消收藏成功")
