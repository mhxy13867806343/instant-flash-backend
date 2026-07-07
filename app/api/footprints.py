from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_required
from app.api.utils import new_business_id
from app.core.pagination import paginate_with_total
from app.core.response import ok
from app.api.admin import fail
from app.db.session import get_db
from app.models.footprint import UserFootprint
from app.models.user import User
from app.schemas.footprint import FootprintCreate, FootprintUpdate, FootprintOut

router = APIRouter(prefix="/api/user/footprints", tags=["用户足迹"])


def _footprint_out(f: UserFootprint) -> FootprintOut:
    return FootprintOut.model_validate(f)


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="新建足迹",
    description="上传当前坐标并保存足迹信息。",
)
def create_footprint(
    payload: FootprintCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    f = UserFootprint(
        footprint_id=new_business_id("ftp"),
        user_id=current_user.user_id,
        title=payload.title,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.locationName,
        images=payload.images,
        is_deleted=False,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return ok(_footprint_out(f), "保存足迹成功")


@router.get(
    "/list",
    summary="获取足迹分页列表",
    description="分页加载当前用户的足迹记录，按时间降序。",
)
def list_footprints(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页限制")] = 20,
) -> dict:
    query = db.query(UserFootprint).filter(
        UserFootprint.user_id == current_user.user_id,
        UserFootprint.is_deleted.is_(False),
    ).order_by(UserFootprint.create_time.desc())

    items, total = paginate_with_total(query, page, limit)
    return ok({
        "list": [_footprint_out(item) for item in items],
        "total": total,
    })


@router.get(
    "/{footprintId}",
    summary="获取足迹详情",
    description="查看单条足迹的坐标和文字信息。",
)
def get_footprint_detail(
    footprintId: Annotated[str, Path(description="足迹 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    f = db.query(UserFootprint).filter(
        UserFootprint.footprint_id == footprintId,
        UserFootprint.user_id == current_user.user_id,
        UserFootprint.is_deleted.is_(False),
    ).first()
    if not f:
        raise fail(status.HTTP_404_NOT_FOUND, "足迹未找到")
    return ok(_footprint_out(f))


@router.put(
    "/{footprintId}",
    summary="编辑足迹",
    description="更新足迹的坐标、位置名称、标题与描述信息。",
)
def update_footprint(
    footprintId: Annotated[str, Path(description="足迹 ID")],
    payload: FootprintUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    f = db.query(UserFootprint).filter(
        UserFootprint.footprint_id == footprintId,
        UserFootprint.user_id == current_user.user_id,
        UserFootprint.is_deleted.is_(False),
    ).first()
    if not f:
        raise fail(status.HTTP_404_NOT_FOUND, "足迹未找到")

    # 更新字段
    for k, v in payload.model_dump(exclude_unset=True).items():
        # 转为 snake_case 写入数据库属性
        field_map = {
            "locationName": "location_name",
        }
        db_col = field_map.get(k, k)
        setattr(f, db_col, v)

    db.commit()
    db.refresh(f)
    return ok(_footprint_out(f), "修改足迹成功")


@router.delete(
    "/{footprintId}",
    summary="删除足迹",
    description="删除（软删除）指定的足迹记录。",
)
def delete_footprint(
    footprintId: Annotated[str, Path(description="足迹 ID")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> dict:
    f = db.query(UserFootprint).filter(
        UserFootprint.footprint_id == footprintId,
        UserFootprint.user_id == current_user.user_id,
        UserFootprint.is_deleted.is_(False),
    ).first()
    if not f:
        raise fail(status.HTTP_404_NOT_FOUND, "足迹未找到")

    # 软删除
    f.is_deleted = True
    db.commit()
    return ok(None, "删除足迹成功")
