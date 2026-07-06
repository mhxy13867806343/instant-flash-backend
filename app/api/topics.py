from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.core.response import ok
from app.db.session import get_db
from app.models.system_config import AdminTag

topics_router = APIRouter(prefix="/api/topics", tags=["用户端话题"])
tags_router = APIRouter(prefix="/api/tags", tags=["用户端话题"])

DEFAULT_TOPIC_NAMES = [
    "同城发现",
    "灵感记录",
    "今日穿搭",
    "周末去哪",
    "探店日常",
    "夜市打卡",
    "咖啡时间",
    "运动搭子",
]
DEFAULT_TOPIC_ORDER = {name: index for index, name in enumerate(DEFAULT_TOPIC_NAMES, start=1)}


def seed_default_topics(db: Session) -> None:
    existing_names = {row[0] for row in db.query(AdminTag.name).all()}
    missing_topics = [
            AdminTag(
                tag_id=new_business_id("tag"),
                name=name,
                color="#ff7457" if index == 1 else "",
                sort=index,
                status="enabled",
                remark="用户端默认推荐话题",
            )
            for index, name in enumerate(DEFAULT_TOPIC_NAMES, start=1)
        if name not in existing_names
    ]
    if not missing_topics:
        return
    db.add_all(missing_topics)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def topic_item(tag: AdminTag) -> dict[str, Any]:
    label = f"#{tag.name}"
    return {
        "tagId": tag.tag_id,
        "topicId": tag.tag_id,
        "name": tag.name,
        "label": label,
        "value": tag.name,
        "displayName": label,
        "color": tag.color or "",
        "sort": tag.sort,
    }


def topic_sort_key(tag: AdminTag) -> tuple[int, int, int, Any]:
    default_order = DEFAULT_TOPIC_ORDER.get(tag.name)
    if default_order is not None:
        return (0, default_order, tag.sort, tag.create_time)
    return (1, tag.sort, 0, tag.create_time)


def topic_payload(
    db: Session,
    keyword: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    seed_default_topics(db)
    base_query = db.query(AdminTag).filter(AdminTag.status == "enabled")
    all_enabled_tags = base_query.order_by(AdminTag.sort.asc(), AdminTag.create_time.asc()).all()
    recommended_tags = sorted(all_enabled_tags, key=topic_sort_key)[:limit]
    search_results: list[AdminTag] = []
    search_total = 0
    if keyword:
        search_query = base_query.filter(AdminTag.name.ilike(f"%{keyword}%"))
        matched_tags = sorted(search_query.order_by(AdminTag.sort.asc(), AdminTag.create_time.asc()).all(), key=topic_sort_key)
        search_total = len(matched_tags)
        search_results = matched_tags[offset : offset + limit]

    return {
        "recommended": [topic_item(tag) for tag in recommended_tags],
        "list": [topic_item(tag) for tag in recommended_tags],
        "searchResults": [topic_item(tag) for tag in search_results],
        "searchList": [topic_item(tag) for tag in search_results],
        "total": len(recommended_tags),
        "searchTotal": search_total,
        "keyword": keyword or "",
        "limit": limit,
        "offset": offset,
    }


def list_user_topics(
    db: Annotated[Session, Depends(get_db)],
    keyword: Annotated[str | None, Query(description="搜索话题关键词；不影响 recommended 固定推荐列表")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="返回数量，默认只展示前 10 个")] = 10,
    offset: Annotated[int, Query(ge=0, description="搜索结果偏移量")] = 0,
) -> dict[str, object]:
    return ok(topic_payload(db, keyword, limit, offset))


topics_router.get(
    "",
    summary="用户端推荐话题",
    description="用户端搜索话题页接口。默认返回启用话题排序前 10 个；keyword 只影响 searchResults，recommended 固定不跟搜索联动。",
)(list_user_topics)

tags_router.get(
    "",
    summary="用户端推荐标签",
    description="兼容标签叫法的用户端话题接口，返回结构与 /api/topics 一致。",
)(list_user_topics)
