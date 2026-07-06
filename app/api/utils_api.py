from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Query
from app.core.response import ok
from app.core.link_parser import parse_url_metadata

router = APIRouter(prefix="/api/utils", tags=["系统工具"])


@router.get(
    "/parse-link",
    summary="解析超链接网页信息",
    description="解析传入的超链接地址，提取网页标题、描述、图标以及封面图信息用于预览卡片。",
)
def parse_link(
    url: Annotated[str, Query(description="要解析的超链接网页地址")]
) -> dict:
    meta = parse_url_metadata(url)
    return ok(meta)
