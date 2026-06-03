from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from starlette.responses import Response

from app.api.utils import new_business_id
from app.core.security import decode_access_token_payload
from app.db.session import SessionLocal
from app.models.system_config import AdminAccount, AdminOperationLog
from app.models.user import User


SKIP_LOG_PREFIXES = (
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
    "/health",
    "/api/admin/logs",
    "/api/admin/security/login-logs",
)
SKIP_LOG_PATHS = {
    "/api/admin/auth/login",
    "/api/auth/dev-token",
    "/api/auth/wx-login",
}

ADMIN_MODULE_TITLES = {
    "dashboard": "数据看板",
    "users": "用户管理",
    "posts": "内容管理",
    "comments": "评论管理",
    "announcements": "公告管理",
    "versions": "版本管理",
    "packages": "安装包管理",
    "menus": "菜单管理",
    "permissions": "权限模块",
    "roles": "角色管理",
    "accounts": "账号管理",
    "security": "安全设置",
    "access-rules": "黑白名单",
    "notifications": "消息通知",
}
USER_MODULE_TITLES = {
    "posts": "用户端内容",
    "user": "用户资料",
    "messages": "用户消息",
    "auth": "用户鉴权",
}


@dataclass
class Actor:
    actor_type: str
    account_id: str
    username: str


def should_skip_log(path: str) -> bool:
    if path in SKIP_LOG_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in SKIP_LOG_PREFIXES)


def request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return "127.0.0.1"
    return request.client.host or "127.0.0.1"


def ip_location(ip: str) -> str:
    if ip.startswith("127.") or ip == "::1" or ip.startswith("192.168.") or ip.startswith("10."):
        return "中国·浙江·杭州"
    return "未知"


def resolve_actor(request: Request) -> Actor | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    payload = decode_access_token_payload(authorization.split(" ", 1)[1].strip())
    if payload is None:
        return None
    subject = payload.get("sub")
    token_type = payload.get("typ")
    if not isinstance(subject, str):
        return None

    db = SessionLocal()
    try:
        if token_type == "admin" and subject.startswith("admin:"):
            username = subject.removeprefix("admin:")
            account = db.query(AdminAccount).filter(AdminAccount.username == username).one_or_none()
            return Actor("admin", account.account_id if account is not None else "", username)
        user = db.query(User).filter(User.user_id == subject).one_or_none()
        username = user.nickname or user.phone or subject if user is not None else subject
        return Actor("user", subject, username)
    finally:
        db.close()


def admin_title(path: str, method: str) -> tuple[str, str]:
    parts = [part for part in path.split("/") if part]
    module_key = parts[2] if len(parts) >= 3 else "admin"
    module_title = ADMIN_MODULE_TITLES.get(module_key, "后台管理")
    if path == "/api/admin/auth/logout":
        return "logout", "后台退出登录"
    if path == "/api/admin/menus/routes":
        return "menu_route", "获取后台动态路由"
    if method == "POST":
        return "create", f"新增{module_title}"
    if method in {"PUT", "PATCH"}:
        return "update", f"修改{module_title}"
    if method == "DELETE":
        return "delete", f"删除{module_title}"
    return "query", f"查询{module_title}"


def user_title(path: str, method: str) -> tuple[str, str]:
    parts = [part for part in path.split("/") if part]
    module_key = parts[1] if len(parts) >= 2 else "user"
    module_title = USER_MODULE_TITLES.get(module_key, "用户端")
    if path == "/api/auth/logout":
        return "logout", "用户端退出登录"
    if module_key == "posts" and method == "POST" and path.endswith("/like"):
        return "like", "用户端点赞或取消点赞"
    if module_key == "posts" and method == "POST" and path.endswith("/comments"):
        return "comment", "用户端发表评论或回复"
    if module_key == "posts" and method == "POST" and path.endswith("/share"):
        return "share", "用户端分享内容"
    if module_key == "posts" and method == "POST":
        return "create", "用户端发布内容"
    if method in {"PUT", "PATCH"}:
        return "update", f"修改{module_title}"
    if method == "DELETE":
        return "delete", f"删除{module_title}"
    return "query", f"查询{module_title}"


def build_log_meta(request: Request, actor: Actor) -> tuple[str, str, str, str]:
    path = request.url.path
    if actor.actor_type == "admin":
        action, title = admin_title(path, request.method)
        return "admin_operation", action, title, f"PC 后台 {request.method} {path}"
    action, title = user_title(path, request.method)
    return "user_operation", action, title, f"小程序/用户端 {request.method} {path}"


def record_operation_log(request: Request, response: Response, actor: Actor) -> None:
    category, action, title, content = build_log_meta(request, actor)
    status_value = "success" if response.status_code < 400 else "error"
    ip = request_ip(request)
    db = SessionLocal()
    try:
        db.add(
            AdminOperationLog(
                log_id=new_business_id("log"),
                account_id=actor.account_id,
                username=actor.username,
                category=category,
                action=action,
                title=title,
                content=f"{content}，响应状态 {response.status_code}",
                status=status_value,
                ip=ip,
                location=ip_location(ip),
                user_agent=request.headers.get("user-agent", ""),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
