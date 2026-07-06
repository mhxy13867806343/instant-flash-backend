from __future__ import annotations

import re


PHONE_USER_ID_RE = re.compile(r"^(?:h5|mp)-(?P<phone>\d{6,32})$")

CLIENT_TYPE_ALIASES = {
    "android": "android",
    "安卓": "android",
    "ios": "ios",
    "iphone": "ios",
    "apple": "ios",
    "鸿蒙": "harmonyos",
    "harmony": "harmonyos",
    "harmonyos": "harmonyos",
    "mp": "miniprogram",
    "mini": "miniprogram",
    "miniapp": "miniprogram",
    "mini_program": "miniprogram",
    "miniprogram": "miniprogram",
    "小程序": "miniprogram",
    "wechat": "miniprogram",
    "weixin": "miniprogram",
    "wx": "miniprogram",
    "h5": "h5",
    "pc": "pc",
    "web": "pc",
    "desktop": "pc",
    "windows": "pc",
    "mac": "pc",
    "electron": "pc",
    "电脑": "pc",
    "网页": "pc",
}

CLIENT_SUBTYPE_ALIASES = {
    "wechat": "wechat",
    "weixin": "wechat",
    "wx": "wechat",
    "微信": "wechat",
    "alipay": "alipay",
    "支付宝": "alipay",
    "douyin": "douyin",
    "tiktok": "douyin",
    "抖音": "douyin",
    "tt": "toutiao",
    "toutiao": "toutiao",
    "头条": "toutiao",
    "qq": "qq",
    "baidu": "baidu",
    "百度": "baidu",
}


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    phone = re.sub(r"\D+", "", value)
    return phone or None


def phone_from_user_id(user_id: str | None) -> str | None:
    if not user_id:
        return None
    match = PHONE_USER_ID_RE.match(user_id.strip())
    if match is None:
        return None
    return match.group("phone")


def mobile_user_id(phone: str) -> str:
    return f"mp-{phone}"


def normalize_client_type(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("-", "_")
    return CLIENT_TYPE_ALIASES.get(key, key[:32] if key else None)


def normalize_client_subtype(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("-", "_")
    return CLIENT_SUBTYPE_ALIASES.get(key, key[:64] if key else None)


def should_use_mobile_user_id(user_id: str | None, phone: str | None, client_type: str | None) -> bool:
    if not phone:
        return False
    if user_id is None:
        return True
    if phone_from_user_id(user_id) == phone:
        return True
    return client_type in {"android", "ios", "harmonyos", "miniprogram"}
