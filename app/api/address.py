from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/address", tags=["公共地区"])

ADDRESS_FILE = Path(__file__).resolve().parents[2] / "static" / "v1" / "address" / "address_min.json"


def cascader_node(node: dict[str, Any]) -> dict[str, Any]:
    children = [cascader_node(child) for child in node.get("children", [])]
    return {
        "code": node["code"],
        "name": node["name"],
        "value": node["code"],
        "label": node["name"],
        "children": children,
    }


@lru_cache(maxsize=1)
def load_address_tree() -> list[dict[str, Any]]:
    with ADDRESS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return [cascader_node(node) for node in data]


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
