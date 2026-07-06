from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.admin import fail, get_admin_subject, ok
from app.db.session import get_db
from app.models import User, UserFollow, UserPersona, UserPersonaComment, UserPersonaFavorite

router = APIRouter(prefix="/api/admin/social", tags=["后台管理"])


# ---------------------------------------------------------------------------
# Pydantic Schemas for PC Admin
# ---------------------------------------------------------------------------

class AdminFollowRelationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    followId: str
    userId: str
    userNickname: str | None = None
    userAvatar: str | None = None
    followingId: str
    followingNickname: str | None = None
    followingAvatar: str | None = None
    createTime: datetime


class AdminPersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    personaId: str
    userId: str
    nickname: str | None = None
    avatar: str | None = None
    title: str | None = None
    content: str
    images: list[str]
    tags: list[str]
    privacy: str
    expireTime: datetime | None = None
    viewCount: int
    createTime: datetime
    commentCount: int = 0
    favoriteCount: int = 0


class AdminPersonaCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    commentId: str
    personaId: str
    userId: str
    nickname: str | None = None
    avatar: str | None = None
    content: str
    createTime: datetime


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _admin_persona_out(p: UserPersona, db: Session) -> AdminPersonaOut:
    owner = db.query(User).filter(User.user_id == p.user_id).first()
    comment_count = db.query(UserPersonaComment).filter(UserPersonaComment.persona_id == p.persona_id).count()
    favorite_count = db.query(UserPersonaFavorite).filter(UserPersonaFavorite.persona_id == p.persona_id).count()

    return AdminPersonaOut(
        personaId=p.persona_id,
        userId=p.user_id,
        nickname=owner.nickname if owner else None,
        avatar=owner.avatar if owner else None,
        title=p.title,
        content=p.content,
        images=p.images or [],
        tags=p.tags or [],
        privacy=p.privacy,
        expireTime=p.expire_time,
        viewCount=p.view_count,
        createTime=p.create_time,
        commentCount=comment_count,
        favoriteCount=favorite_count,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/follow-relations",
    response_model=list[AdminFollowRelationOut],
    summary="[PC端] 获取关注与粉丝关系列表",
    description="支持通过关注者 userId 或被关注者 followingId 进行筛选。",
)
def get_follow_relations(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
    user_id: Annotated[str | None, Query(alias="userId")] = None,
    following_id: Annotated[str | None, Query(alias="followingId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminFollowRelationOut]:
    query = db.query(UserFollow)
    if user_id:
        query = query.filter(UserFollow.user_id == user_id)
    if following_id:
        query = query.filter(UserFollow.following_id == following_id)

    items = query.order_by(UserFollow.create_time.desc()).offset((page - 1) * limit).limit(limit).all()

    results = []
    for f in items:
        u_owner = db.query(User).filter(User.user_id == f.user_id).first()
        u_target = db.query(User).filter(User.user_id == f.following_id).first()

        results.append(
            AdminFollowRelationOut(
                id=f.id,
                followId=f.follow_id,
                userId=f.user_id,
                userNickname=u_owner.nickname if u_owner else None,
                userAvatar=u_owner.avatar if u_owner else None,
                followingId=f.following_id,
                followingNickname=u_target.nickname if u_target else None,
                followingAvatar=u_target.avatar if u_target else None,
                createTime=f.create_time,
            )
        )
    return results


@router.get(
    "/personas",
    response_model=list[AdminPersonaOut],
    summary="[PC端] 获取画像列表",
    description="支持通过所有者 userId、标题或正文内容模糊搜索，以及按照公开/私有状态筛选。",
)
def get_personas_list(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
    user_id: Annotated[str | None, Query(alias="userId")] = None,
    title: Annotated[str | None, Query()] = None,
    content: Annotated[str | None, Query()] = None,
    privacy: Annotated[str | None, Query(pattern="^(public|private)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminPersonaOut]:
    query = db.query(UserPersona)
    if user_id:
        query = query.filter(UserPersona.user_id == user_id)
    if title:
        query = query.filter(UserPersona.title.ilike(f"%{title}%"))
    if content:
        query = query.filter(UserPersona.content.ilike(f"%{content}%"))
    if privacy:
        query = query.filter(UserPersona.privacy == privacy)

    items = query.order_by(UserPersona.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return [_admin_persona_out(p, db) for p in items]


@router.get(
    "/personas/{persona_id}",
    response_model=AdminPersonaOut,
    summary="[PC端] 画像详情查看",
)
def get_persona_detail(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
) -> AdminPersonaOut:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到该用户画像")
    return _admin_persona_out(p, db)


@router.delete(
    "/personas/{persona_id}",
    summary="[PC端] 强行删除下架用户画像",
    description="管理员权限下架删除画像，同时清空相关联的评论和收藏记录。",
)
def delete_persona(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
) -> dict[str, Any]:
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到该画像")

    db.delete(p)
    db.commit()
    return ok(message="管理员成功下架删除该用户画像")


@router.get(
    "/personas/{persona_id}/comments",
    response_model=list[AdminPersonaCommentOut],
    summary="[PC端] 画像评论列表",
)
def get_persona_comments(
    persona_id: Annotated[str, Path(description="画像 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminPersonaCommentOut]:
    # Check persona exists
    p = db.query(UserPersona).filter(UserPersona.persona_id == persona_id).first()
    if p is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户画像未找到")

    rows = db.query(UserPersonaComment, User).join(
        User, UserPersonaComment.user_id == User.user_id
    ).filter(
        UserPersonaComment.persona_id == persona_id
    ).order_by(
        UserPersonaComment.create_time.desc()
    ).offset((page - 1) * limit).limit(limit).all()

    results = []
    for comment, user in rows:
        results.append(
            AdminPersonaCommentOut(
                commentId=comment.comment_id,
                personaId=comment.persona_id,
                userId=comment.user_id,
                nickname=user.nickname,
                avatar=user.avatar,
                content=comment.content,
                createTime=comment.create_time,
            )
        )
    return results


@router.delete(
    "/personas/comments/{comment_id}",
    summary="[PC端] 强行删除用户评论",
)
def delete_persona_comment(
    comment_id: Annotated[str, Path(description="评论 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[Any, Depends(get_admin_subject)],
) -> dict[str, Any]:
    comment = db.query(UserPersonaComment).filter(UserPersonaComment.comment_id == comment_id).first()
    if comment is None:
        raise fail(status.HTTP_404_NOT_FOUND, "未找到该评论")

    db.delete(comment)
    db.commit()
    return ok(message="管理员成功删除该画像评论")
