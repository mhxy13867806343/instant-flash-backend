from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/address", tags=["公共地区"])

ADDRESS_FILE = Path(__file__).resolve().parents[2] / "static" / "v1" / "address" / "address_min.json"

_address_cache: list[dict[str, Any]] | None = None


def cascader_node(node: dict[str, Any]) -> dict[str, Any]:
    children = [cascader_node(child) for child in node.get("children", [])]
    return {
        "code": node["code"],
        "name": node["name"],
        "value": node["code"],
        "label": node["name"],
        "children": children,
    }


def load_address_tree() -> list[dict[str, Any]]:
    global _address_cache
    if _address_cache is not None:
        return _address_cache
    if not ADDRESS_FILE.exists():
        logger.warning("地区数据文件不存在，返回空地区树：%s", ADDRESS_FILE)
        return []
    try:
        with ADDRESS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("地区数据文件读取失败，返回空地区树：%s", exc)
        return []
    _address_cache = [cascader_node(node) for node in data]
    return _address_cache


@router.get(
    "/tree",
    summary="三级地区树",
    description="公共省市区三级地区接口，PC 后台和用户端共用；返回 code/name 和 value/label，方便级联选择器直接使用。",
)
def get_address_tree() -> dict[str, Any]:
    return {
        "code": 200,
        "message": "success",
        "data": load_address_tree(),
    }
