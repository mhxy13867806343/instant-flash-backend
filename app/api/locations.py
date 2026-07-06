from __future__ import annotations

import json
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.configs import (
    DEFAULT_LOCATION_KEYWORDS,
    TIANDITU_GEOCODER_URL,
    TIANDITU_SEARCH_URL,
)
from app.core.response import fail, ok
from app.db.session import get_db

router = APIRouter(prefix="/api/locations", tags=["用户端位置"])


def resolve_coordinate(primary: float | None, *aliases: float | None) -> float | None:
    if primary is not None:
        return primary
    for value in aliases:
        if value is not None:
            return value
    return None


def tianditu_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    try:
        with urlopen(f"{url}?{query}", timeout=5) as response:  # noqa: S310 - fixed trusted API host
            raw_text = response.read().decode("utf-8")
    except HTTPError as exc:
        message = "天地图服务参数错误" if exc.code == 400 else "天地图服务暂时不可用"
        raise fail(status.HTTP_502_BAD_GATEWAY, message) from exc
    except (TimeoutError, URLError) as exc:
        raise fail(status.HTTP_502_BAD_GATEWAY, "天地图服务暂时不可用") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise fail(status.HTTP_502_BAD_GATEWAY, "天地图服务返回格式异常") from exc
    if not isinstance(parsed, dict):
        raise fail(status.HTTP_502_BAD_GATEWAY, "天地图服务返回格式异常")
    return parsed


def reverse_geocode_city(longitude: float, latitude: float) -> str:
    if not settings.tianditu_server_key:
        return ""
    post_str = json.dumps({"lon": longitude, "lat": latitude, "ver": 1}, ensure_ascii=False)
    data = tianditu_get(
        TIANDITU_GEOCODER_URL,
        {"postStr": post_str, "type": "geocode", "tk": settings.tianditu_server_key},
    )
    result = data.get("result") or {}
    address_component = result.get("addressComponent") or {}
    return clean_city_name(
        address_component.get("city")
        or address_component.get("county")
        or address_component.get("province")
        or ""
    )


def search_nearby_pois(
    longitude: float,
    latitude: float,
    keyword: str,
    radius: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    if not settings.tianditu_server_key:
        raise fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "天地图服务端 key 未配置")
    post_str = json.dumps(
        {
            "keyWord": keyword,
            "level": 18,
            "mapBound": "-180,-90,180,90",
            "queryType": 3,
            "pointLonlat": f"{longitude},{latitude}",
            "queryRadius": radius,
            "start": offset,
            "count": limit,
        },
        ensure_ascii=False,
    )
    return tianditu_get(
        TIANDITU_SEARCH_URL,
        {"postStr": post_str, "type": "query", "tk": settings.tianditu_server_key},
    )


def clean_city_name(value: str | None) -> str:
    if not value:
        return ""
    name = value.strip()
    for suffix in ("市", "地区", "自治州", "盟"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def city_from_address(address: str) -> str:
    for marker in ("市", "地区", "自治州", "盟"):
        if marker in address:
            before = address.split(marker, 1)[0]
            for splitter in ("省", "自治区", "特别行政区"):
                if splitter in before:
                    before = before.rsplit(splitter, 1)[-1]
            return clean_city_name(before + marker)
    return ""


def parse_lonlat(value: str | None) -> tuple[float | None, float | None]:
    if not value or "," not in value:
        return None, None
    lon_text, lat_text = value.split(",", 1)
    try:
        return float(lon_text), float(lat_text)
    except ValueError:
        return None, None


def poi_name(value: dict[str, Any]) -> str:
    return str(value.get("name") or value.get("displayName") or value.get("nameStr") or "").strip()


def poi_city(value: dict[str, Any], fallback_city: str) -> str:
    direct_city = value.get("city") or value.get("cityName") or value.get("region") or value.get("area")
    if direct_city:
        return clean_city_name(str(direct_city))
    address_city = city_from_address(str(value.get("address") or ""))
    return address_city or fallback_city


def poi_item(value: dict[str, Any], fallback_city: str) -> dict[str, Any] | None:
    name = poi_name(value)
    if not name:
        return None
    lon, lat = parse_lonlat(str(value.get("lonlat") or value.get("lonLat") or ""))
    city = poi_city(value, fallback_city)
    display_name = f"{city} · {name}" if city else name
    return {
        "name": name,
        "title": name,
        "displayName": display_name,
        "label": display_name,
        "value": display_name,
        "city": city,
        "address": value.get("address") or "",
        "longitude": lon,
        "latitude": lat,
        "lonlat": value.get("lonlat") or value.get("lonLat") or "",
        "poiId": value.get("hotPointID") or value.get("id") or "",
        "type": value.get("poiType") or value.get("type") or "",
        "source": "tianditu",
    }


def parse_pois(data: dict[str, Any], fallback_city: str) -> list[dict[str, Any]]:
    raw_pois = data.get("pois") or data.get("results") or data.get("data") or []
    if isinstance(raw_pois, str):
        try:
            raw_pois = json.loads(raw_pois)
        except json.JSONDecodeError:
            raw_pois = []
    if not isinstance(raw_pois, list):
        return []
    items = [poi_item(item, fallback_city) for item in raw_pois if isinstance(item, dict)]
    return [item for item in items if item is not None]


def poi_unique_key(item: dict[str, Any]) -> str:
    return str(item.get("poiId") or item.get("lonlat") or item.get("displayName") or item.get("name"))


def collect_location_candidates(
    longitude: float,
    latitude: float,
    keyword: str,
    radius: int,
    limit: int,
    offset: int,
    fallback_city: str,
) -> tuple[list[dict[str, Any]], int, str]:
    keywords = (keyword,) if keyword else DEFAULT_LOCATION_KEYWORDS
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    first_total = 0
    for current_keyword in keywords:
        data = search_nearby_pois(longitude, latitude, current_keyword, radius, limit + offset, 0)
        if not first_total:
            first_total = int(data.get("count") or data.get("total") or 0)
        for item in parse_pois(data, fallback_city):
            unique_key = poi_unique_key(item)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            candidates.append(item)
        if len(candidates) >= limit + offset:
            break
    page_items = candidates[offset : offset + limit]
    return page_items, max(first_total, len(candidates)), keyword


@router.get(
    "/nearby",
    summary="根据坐标获取附近位置",
    description="用户端发布位置候选接口。前端传经纬度，后端调用天地图周边搜索，返回可直接展示的 `城市 · POI` 列表。",
)
def nearby_locations(
    _: Annotated[Session, Depends(get_db)],
    longitude: Annotated[float | None, Query(description="经度 longitude")] = None,
    latitude: Annotated[float | None, Query(description="纬度 latitude")] = None,
    lng: Annotated[float | None, Query(description="兼容参数：经度 lng", include_in_schema=False)] = None,
    lon: Annotated[float | None, Query(description="兼容参数：经度 lon", include_in_schema=False)] = None,
    lat: Annotated[float | None, Query(description="兼容参数：纬度 lat", include_in_schema=False)] = None,
    keyword: Annotated[str, Query(max_length=64, description="POI 关键词，默认空表示附近位置")] = "",
    radius: Annotated[int, Query(ge=100, le=50000, description="搜索半径，单位米")] = 3000,
    limit: Annotated[int, Query(ge=1, le=20, description="返回数量")] = 10,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
) -> dict[str, object]:
    resolved_longitude = resolve_coordinate(longitude, lng, lon)
    resolved_latitude = resolve_coordinate(latitude, lat)
    if resolved_longitude is None or resolved_latitude is None:
        raise fail(status.HTTP_400_BAD_REQUEST, "请传入经纬度")
    fallback_city = reverse_geocode_city(resolved_longitude, resolved_latitude)
    normalized_keyword = keyword.strip()
    items, total, response_keyword = collect_location_candidates(
        resolved_longitude,
        resolved_latitude,
        normalized_keyword,
        radius,
        limit,
        offset,
        fallback_city,
    )
    return ok(
        {
            "list": items,
            "items": items,
            "total": total,
            "longitude": resolved_longitude,
            "latitude": resolved_latitude,
            "city": fallback_city,
            "keyword": response_keyword,
            "radius": radius,
            "limit": limit,
            "offset": offset,
        }
    )
