from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.utils import new_business_id
from app.core.security import create_access_token, decode_access_token
from app.db.base import utc_now
from app.db.session import get_db
from app.models.admin_agreement import AdminAgreement
from app.models.comment import Comment
from app.models.message import Message
from app.models.post import Post
from app.models.system_config import AdminAccount, AdminAnnouncement, AdminDictionary, AdminMenu, AdminRegion, AdminSystemMessage, AdminTag, AdminVersion
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["后台管理"])
admin_bearer = HTTPBearer(auto_error=False)


DEFAULT_AGREEMENTS = {
    "privacy": "<h2>即闪隐私政策</h2><p>请在后台编辑最新隐私政策内容。</p>",
    "user": "<h2>即闪用户协议</h2><p>请在后台编辑最新用户协议内容。</p>",
}
SINGLE_BANNER_ANNOUNCEMENT_ID = "SINGLE_BANNER"
DEFAULT_ADMIN_MENUS: list[dict[str, Any]] = [
    {"menu_id": "menu_dashboard", "parent_id": None, "title": "数据看板", "path": "/dashboard", "name": "Dashboard", "component": "views/dashboard/Index", "icon": "Odometer", "type": "menu", "permission": "dashboard", "sort": 10, "affix": True, "remark": "后台首页数据看板"},
    {"menu_id": "menu_user", "parent_id": None, "title": "用户管理", "path": "/user", "name": "UserList", "component": "views/user/List", "icon": "User", "type": "menu", "permission": "user", "sort": 20},
    {"menu_id": "menu_content", "parent_id": None, "title": "内容管理", "path": "/content", "name": "ContentList", "component": "views/content/List", "icon": "Document", "type": "menu", "permission": "content", "sort": 30},
    {"menu_id": "menu_comment", "parent_id": None, "title": "评论管理", "path": "/comment", "name": "CommentList", "component": "views/comment/List", "icon": "ChatLineSquare", "type": "menu", "permission": "comment", "sort": 40},
    {"menu_id": "menu_simulator", "parent_id": None, "title": "App 仿真模拟", "path": "/simulator", "name": "AppSimulator", "component": "views/simulator/Index", "icon": "Smartphone", "type": "menu", "permission": "simulator", "sort": 50},
    {"menu_id": "menu_account", "parent_id": None, "title": "账号管理", "path": "/account", "name": "AccountList", "component": "views/account/List", "icon": "UserFilled", "type": "menu", "permission": "account", "sort": 60},
    {"menu_id": "menu_announcement", "parent_id": None, "title": "公告管理", "path": "/announcement", "name": "Announcement", "component": None, "redirect": "/announcement/single", "icon": "Bell", "type": "catalog", "permission": "announcement", "sort": 70},
    {"menu_id": "menu_announcement_single", "parent_id": "menu_announcement", "title": "单公告", "path": "/announcement/single", "name": "AnnouncementSingle", "component": "views/announcement/Single", "icon": "Promotion", "type": "menu", "permission": "announcement", "sort": 10},
    {"menu_id": "menu_announcement_list", "parent_id": "menu_announcement", "title": "公告列表", "path": "/announcement/list", "name": "AnnouncementList", "component": "views/announcement/List", "icon": "List", "type": "menu", "permission": "announcement", "sort": 20},
    {"menu_id": "menu_version", "parent_id": None, "title": "版本管理", "path": "/version", "name": "VersionList", "component": "views/version/List", "icon": "Upload", "type": "menu", "permission": "version", "sort": 80},
    {"menu_id": "menu_system", "parent_id": None, "title": "系统配置", "path": "/system", "name": "SystemConfig", "component": None, "redirect": "/tag", "icon": "Setting", "type": "catalog", "permission": None, "sort": 90},
    {"menu_id": "menu_tag", "parent_id": "menu_system", "title": "标签管理", "path": "/tag", "name": "TagList", "component": "views/tag/List", "icon": "PriceTag", "type": "menu", "permission": "tag", "sort": 10},
    {"menu_id": "menu_region", "parent_id": "menu_system", "title": "地区管理", "path": "/region", "name": "RegionList", "component": "views/region/List", "icon": "Location", "type": "menu", "permission": "region", "sort": 20},
    {"menu_id": "menu_dict", "parent_id": "menu_system", "title": "字典管理", "path": "/dict", "name": "DictList", "component": "views/dict/List", "icon": "Memo", "type": "menu", "permission": "dict", "sort": 30},
    {"menu_id": "menu_message", "parent_id": "menu_system", "title": "系统消息", "path": "/message", "name": "SysMessage", "component": "views/message/List", "icon": "Message", "type": "menu", "permission": "message", "sort": 40},
    {"menu_id": "menu_privacy", "parent_id": "menu_system", "title": "隐私协议", "path": "/agreement/privacy", "name": "PrivacyAgreement", "component": "views/agreement/Privacy", "icon": "Lock", "type": "menu", "permission": "agreement", "sort": 50},
    {"menu_id": "menu_user_agreement", "parent_id": "menu_system", "title": "用户协议", "path": "/agreement/user", "name": "UserAgreement", "component": "views/agreement/User", "icon": "Checked", "type": "menu", "permission": "agreement", "sort": 60},
]


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, title="管理员账号", description="后台管理员登录账号")
    password: str = Field(min_length=1, max_length=128, title="管理员密码", description="后台管理员登录密码")


class AdminUserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(normal|banned)$", title="用户状态", description="normal 表示正常，banned 表示禁用")


class AgreementUpdate(BaseModel):
    content: str = Field(title="协议内容", description="HTML 格式的协议正文")


class AdminTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64, title="标签名称", description="标签管理中的标签名称")
    color: str | None = Field(default=None, max_length=32, title="标签颜色", description="标签颜色，例如 #1677ff")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")
    remark: str | None = Field(default=None, title="备注", description="标签备注")


class AdminRegionPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64, title="地区名称", description="省市区名称")
    code: str = Field(min_length=1, max_length=32, title="地区编码", description="行政区划编码或前端自定义编码")
    parentId: str | None = Field(default=None, max_length=64, title="上级地区 ID", description="上级业务地区 ID，顶级地区可为空")
    level: int = Field(default=1, ge=1, le=4, title="层级", description="1 省级，2 市级，3 区县，4 街道")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")


class AdminDictionaryPayload(BaseModel):
    type: str = Field(min_length=1, max_length=64, title="字典类型", description="字典分组编码，例如 post_status")
    parentId: str | None = Field(default=None, max_length=64, title="上级字典 ID", description="上级字典项的业务 ID；为空表示顶级字典项")
    label: str = Field(min_length=1, max_length=128, title="字典标签", description="展示给用户看的中文名称")
    value: str = Field(min_length=1, max_length=128, title="字典值", description="前后端传递使用的值")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")
    remark: str | None = Field(default=None, title="备注", description="字典项备注")


class AdminAnnouncementPayload(BaseModel):
    title: str | None = Field(default=None, max_length=128, title="公告标题", description="公告标题")
    type: str | None = Field(default=None, pattern="^(info|warning|danger)$", title="公告类型", description="info 普通，warning 重要提醒，danger 紧急公告")
    content: str | None = Field(default=None, title="公告内容", description="公告正文，支持富文本")
    link: str | None = Field(default=None, max_length=512, title="跳转链接", description="公告关联链接")
    pinned: bool | None = Field(default=None, title="是否置顶", description="是否置顶展示")
    startTime: str | None = Field(default=None, max_length=32, title="开始时间", description="公告生效开始时间")
    endTime: str | None = Field(default=None, max_length=32, title="结束时间", description="公告生效结束时间")
    status: str | None = Field(default=None, pattern="^(active|inactive)$", title="状态", description="active 已发布，inactive 已停用")


class AdminVersionPayload(BaseModel):
    platform: str | None = Field(default=None, pattern="^(iOS|Android|HarmonyOS)$", title="平台", description="版本平台")
    version: str | None = Field(default=None, max_length=32, title="版本号", description="展示版本号")
    build: str | None = Field(default=None, max_length=32, title="Build 号", description="内部构建号")
    forceUpdate: bool | None = Field(default=None, title="是否强制更新", description="是否要求客户端强制更新")
    status: str | None = Field(default=None, pattern="^(released|beta|deprecated)$", title="状态", description="released 已发布，beta 灰度中，deprecated 已下线")
    betaPct: int | None = Field(default=None, ge=0, le=100, title="灰度比例", description="灰度发布比例")
    notes: str | None = Field(default=None, title="更新说明", description="更新说明，支持文本或富文本")
    notesType: str | None = Field(default=None, pattern="^(text|rich)$", title="说明类型", description="text 文本，rich 富文本")
    downloadUrl: str | None = Field(default=None, max_length=512, title="下载地址", description="安装包下载地址")


class AdminAccountPayload(BaseModel):
    username: str | None = Field(default=None, max_length=64, title="登录账号", description="后台账号用户名")
    nickname: str | None = Field(default=None, max_length=64, title="昵称", description="后台账号昵称")
    avatar: str | None = Field(default=None, max_length=512, title="头像", description="头像地址")
    role: str | None = Field(default=None, pattern="^(superadmin|admin|operator|viewer)$", title="角色", description="后台角色")
    permissions: list[str] | None = Field(default=None, title="权限模块", description="账号可访问的权限模块")
    status: str | None = Field(default=None, pattern="^(active|disabled)$", title="状态", description="active 正常，disabled 禁用")
    email: str | None = Field(default=None, max_length=128, title="邮箱", description="管理员邮箱")
    phone: str | None = Field(default=None, max_length=32, title="手机号", description="管理员手机号")
    remark: str | None = Field(default=None, title="备注", description="账号备注")


class AdminMenuPayload(BaseModel):
    parentId: str | None = Field(default=None, max_length=64, title="上级菜单 ID", description="父级菜单业务 ID；顶级菜单为空")
    title: str = Field(min_length=1, max_length=64, title="菜单标题", description="菜单展示中文名称")
    path: str = Field(min_length=1, max_length=128, title="路由路径", description="前端路由 path，例如 /dashboard")
    name: str = Field(min_length=1, max_length=64, title="路由名称", description="前端路由 name，必须唯一")
    component: str | None = Field(default=None, max_length=128, title="组件路径", description="前端组件路径，例如 views/dashboard/Index")
    redirect: str | None = Field(default=None, max_length=128, title="重定向地址", description="父级菜单默认跳转地址")
    icon: str | None = Field(default=None, max_length=64, title="图标", description="Element Plus 图标组件名")
    type: str = Field(default="menu", pattern="^(catalog|menu|button|link)$", title="菜单类型", description="catalog 目录，menu 菜单，button 按钮，link 外链")
    permission: str | None = Field(default=None, max_length=64, title="权限标识", description="账号权限模块，例如 dashboard/user/content")
    sort: int = Field(default=0, ge=0, title="排序值", description="数字越小越靠前")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$", title="状态", description="enabled 启用，disabled 禁用")
    visible: bool = Field(default=True, title="是否显示", description="是否在侧边菜单显示")
    keepAlive: bool = Field(default=False, title="是否缓存", description="前端 keepAlive 元信息")
    affix: bool = Field(default=False, title="是否固定页签", description="前端 affix 元信息")
    externalLink: str | None = Field(default=None, max_length=512, title="外链地址", description="外链菜单地址")
    remark: str | None = Field(default=None, title="备注", description="菜单备注")


class BatchIdsPayload(BaseModel):
    ids: list[str] = Field(default_factory=list, title="ID 列表", description="需要批量操作的业务 ID 列表")


class AdminSystemMessagePayload(BaseModel):
    title: str = Field(min_length=1, max_length=128, title="消息标题", description="系统消息标题")
    content: str = Field(min_length=1, title="消息内容", description="系统消息正文")
    type: str = Field(default="notice", max_length=32, title="消息类型", description="notice 通知，warning 警告，activity 活动")
    target: str = Field(default="all", max_length=32, title="发送范围", description="all 全部用户，admin 后台，user 用户端")
    status: str = Field(default="draft", pattern="^(draft|published|disabled)$", title="状态", description="draft 草稿，published 已发布，disabled 已停用")
    isPinned: bool = Field(default=False, title="是否置顶", description="是否在系统消息列表置顶展示")


class AdminResponse(BaseModel):
    code: int = Field(title="业务状态码", description="200 表示成功，其他值表示业务失败")
    message: str = Field(title="提示信息", description="接口处理结果说明")
    data: Any = Field(default=None, title="响应数据", description="接口返回的业务数据")


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def get_admin_subject(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(admin_bearer)],
) -> str:
    if credentials is None:
        raise fail(status.HTTP_401_UNAUTHORIZED, "未登录，请先登录")
    if credentials.scheme.lower() != "bearer":
        raise fail(status.HTTP_401_UNAUTHORIZED, "登录失效，请重新登录")
    subject = decode_access_token(credentials.credentials)
    if subject is None or not subject.startswith("admin:"):
        raise fail(status.HTTP_401_UNAUTHORIZED, "登录失效，请重新登录")
    return subject.removeprefix("admin:")


def user_item(db: Session, user: User) -> dict[str, Any]:
    post_count = (
        db.query(func.count(Post.id))
        .filter(Post.user_id == user.user_id, Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    comment_count = (
        db.query(func.count(Comment.id))
        .filter(Comment.user_id == user.user_id, Comment.is_deleted.is_(False))
        .scalar()
        or 0
    )
    likes_received = (
        db.query(func.coalesce(func.sum(Post.like_count), 0))
        .filter(Post.user_id == user.user_id, Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    return {
        "userId": user.user_id,
        "nickname": user.nickname or "即闪用户",
        "avatar": user.avatar or "",
        "phone": user.phone or "",
        "newPhone": user.phone or "",
        "status": "normal" if user.is_active else "banned",
        "regTime": format_time(user.create_time),
        "postCount": post_count,
        "commentCount": comment_count,
        "likesReceived": likes_received,
        "bio": "",
        "gender": user.gender or "保密",
    }


def post_status(post: Post) -> str:
    return "offline" if post.status == "offline" else "online"


def post_item(post: Post) -> dict[str, Any]:
    author = post.author
    return {
        "postId": post.post_id,
        "userId": post.user_id,
        "nickname": author.nickname if author and author.nickname else "即闪用户",
        "avatar": author.avatar if author and author.avatar else "",
        "content": post.content,
        "images": post.images,
        "likes": post.like_count,
        "comments": post.comment_count,
        "shares": post.share_count,
        "status": post_status(post),
        "pubTime": format_time(post.create_time),
    }


def comment_item(db: Session, comment: Comment) -> dict[str, Any]:
    user = db.query(User).filter(User.user_id == comment.user_id).one_or_none()
    reply_to = (
        db.query(User).filter(User.user_id == comment.reply_to_user_id).one_or_none()
        if comment.reply_to_user_id
        else None
    )
    return {
        "commentId": comment.comment_id,
        "postId": comment.post_id,
        "userId": comment.user_id,
        "nickname": user.nickname if user and user.nickname else "即闪用户",
        "avatar": user.avatar if user and user.avatar else "",
        "content": comment.content,
        "parentId": comment.parent_id,
        "replyToUserId": comment.reply_to_user_id,
        "replyToNickname": reply_to.nickname if reply_to else None,
        "pubTime": format_time(comment.create_time),
    }


SCAM_KEYWORDS = ("骗", "诈骗", "杀猪盘", "套路", "上当", "虚假", "刷单", "被扣", "举报")


def tag_search_count(name: str) -> int:
    value = 0
    for index, char in enumerate(name):
        value += ord(char) * (index + 3)
    return (value % 8500) + 1200


def tag_metrics(db: Session, name: str) -> dict[str, int]:
    tag_text = f"#{name}"
    post_query = db.query(Post).filter(
        Post.is_deleted.is_(False),
        Post.content.ilike(f"%{tag_text}%"),
    )
    post_count = post_query.count()
    scam_count = post_query.filter(or_(*(Post.content.ilike(f"%{keyword}%") for keyword in SCAM_KEYWORDS))).count()
    return {
        "postCount": post_count,
        "associatedPostCount": post_count,
        "linkedPostCount": post_count,
        "scamCount": scam_count,
        "fraudCount": scam_count,
        "searchCount": tag_search_count(name),
    }


def tag_item(db: Session, tag: AdminTag) -> dict[str, Any]:
    return {
        "tagId": tag.tag_id,
        "name": tag.name,
        "color": tag.color or "",
        "sort": tag.sort,
        "status": tag.status,
        "remark": tag.remark or "",
        **tag_metrics(db, tag.name),
        "createdAt": format_time(tag.create_time),
        "updatedAt": format_time(tag.update_time),
    }


def region_item(region: AdminRegion) -> dict[str, Any]:
    return {
        "regionId": region.region_id,
        "parentId": region.parent_id,
        "name": region.name,
        "code": region.code,
        "level": region.level,
        "sort": region.sort,
        "status": region.status,
        "createdAt": format_time(region.create_time),
        "updatedAt": format_time(region.update_time),
    }


def dictionary_item(dictionary: AdminDictionary) -> dict[str, Any]:
    return {
        "dictId": dictionary.dict_id,
        "parentId": dictionary.parent_id,
        "type": dictionary.type,
        "label": dictionary.label,
        "value": dictionary.value,
        "sort": dictionary.sort,
        "status": dictionary.status,
        "remark": dictionary.remark or "",
        "createdAt": format_time(dictionary.create_time),
        "updatedAt": format_time(dictionary.update_time),
    }


def dictionary_tree_items(dictionaries: list[AdminDictionary]) -> list[dict[str, Any]]:
    children_by_parent: dict[str | None, list[AdminDictionary]] = {}
    ids = {dictionary.dict_id for dictionary in dictionaries}
    for dictionary in dictionaries:
        parent_id = dictionary.parent_id if dictionary.parent_id in ids else None
        children_by_parent.setdefault(parent_id, []).append(dictionary)

    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.type, item.sort, item.create_time), reverse=False)

    def build(parent_id: str | None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for dictionary in children_by_parent.get(parent_id, []):
            item = dictionary_item(dictionary)
            item["children"] = build(dictionary.dict_id)
            item["childCount"] = len(item["children"])
            result.append(item)
        return result

    return build(None)


def get_dictionary_or_404(db: Session, dict_id: str) -> AdminDictionary:
    dictionary = db.query(AdminDictionary).filter(AdminDictionary.dict_id == dict_id).one_or_none()
    if dictionary is None:
        raise fail(status.HTTP_404_NOT_FOUND, "字典未找到")
    return dictionary


def validate_dictionary_parent(db: Session, parent_id: str | None, dictionary_type: str, self_id: str | None = None) -> None:
    if not parent_id:
        return
    if parent_id == self_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "上级字典不能选择自己")
    parent = get_dictionary_or_404(db, parent_id)
    if parent.type != dictionary_type:
        raise fail(status.HTTP_400_BAD_REQUEST, "上级字典类型必须和当前字典类型一致")
    cursor = parent
    while cursor.parent_id:
        if cursor.parent_id == self_id:
            raise fail(status.HTTP_400_BAD_REQUEST, "上级字典不能选择自己的下级")
        cursor = get_dictionary_or_404(db, cursor.parent_id)


def dictionary_scope_query(db: Session, dictionary_type: str, parent_id: str | None):
    query = db.query(AdminDictionary).filter(AdminDictionary.type == dictionary_type)
    if parent_id:
        return query.filter(AdminDictionary.parent_id == parent_id)
    return query.filter(AdminDictionary.parent_id.is_(None))


def validate_dictionary_unique(
    db: Session,
    dictionary_type: str,
    parent_id: str | None,
    label: str,
    value: str,
    self_id: str | None = None,
) -> None:
    query = dictionary_scope_query(db, dictionary_type, parent_id)
    if self_id:
        query = query.filter(AdminDictionary.dict_id != self_id)
    duplicates = query.all()
    if any(item.label == label for item in duplicates):
        raise fail(status.HTTP_400_BAD_REQUEST, "同一上级下字典标签已存在")
    if any(item.value == value for item in duplicates):
        raise fail(status.HTTP_400_BAD_REQUEST, "同一上级下字典键值已存在")


def system_message_item(message: AdminSystemMessage) -> dict[str, Any]:
    return {
        "messageId": message.message_id,
        "title": message.title,
        "content": message.content,
        "type": message.type,
        "target": message.target,
        "status": message.status,
        "isPinned": message.is_pinned,
        "createdAt": format_time(message.create_time),
        "updatedAt": format_time(message.update_time),
    }


def announcement_item(announcement: AdminAnnouncement) -> dict[str, Any]:
    return {
        "id": announcement.announcement_id,
        "title": announcement.title,
        "type": announcement.type,
        "content": announcement.content,
        "link": announcement.link or "",
        "pinned": announcement.pinned,
        "startTime": announcement.start_time or "",
        "endTime": announcement.end_time or "",
        "status": announcement.status,
        "createdAt": format_time(announcement.create_time),
        "updatedAt": format_time(announcement.update_time),
    }


def version_item(version: AdminVersion) -> dict[str, Any]:
    return {
        "id": version.version_id,
        "platform": version.platform,
        "version": version.version,
        "build": version.build,
        "forceUpdate": version.force_update,
        "status": version.status,
        "betaPct": version.beta_pct,
        "notes": version.notes,
        "notesType": version.notes_type,
        "downloadUrl": version.download_url or "",
        "releaseTime": version.release_time or format_time(version.create_time),
        "createdAt": format_time(version.create_time),
        "updatedAt": format_time(version.update_time),
    }


def account_item(account: AdminAccount) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "username": account.username,
        "nickname": account.nickname,
        "avatar": account.avatar or "",
        "role": account.role,
        "permissions": account.permissions or [],
        "status": account.status,
        "email": account.email or "",
        "phone": account.phone or "",
        "createTime": format_time(account.create_time),
        "lastLogin": account.last_login or format_time(account.last_time),
        "remark": account.remark or "",
    }


def menu_item(menu: AdminMenu) -> dict[str, Any]:
    return {
        "menuId": menu.menu_id,
        "parentId": menu.parent_id,
        "title": menu.title,
        "path": menu.path,
        "name": menu.name,
        "component": menu.component or "",
        "redirect": menu.redirect or "",
        "icon": menu.icon or "",
        "type": menu.type,
        "permission": menu.permission or "",
        "sort": menu.sort,
        "status": menu.status,
        "visible": menu.visible,
        "keepAlive": menu.keep_alive,
        "affix": menu.affix,
        "externalLink": menu.external_link or "",
        "remark": menu.remark or "",
        "meta": {
            "title": menu.title,
            "icon": menu.icon or "",
            "permission": menu.permission or "",
            "keepAlive": menu.keep_alive,
            "affix": menu.affix,
            "hidden": not menu.visible,
        },
        "createdAt": format_time(menu.create_time),
        "updatedAt": format_time(menu.update_time),
    }


def menu_tree_items(menus: list[AdminMenu]) -> list[dict[str, Any]]:
    ids = {menu.menu_id for menu in menus}
    children_by_parent: dict[str | None, list[AdminMenu]] = {}
    for menu in menus:
        parent_id = menu.parent_id if menu.parent_id in ids else None
        children_by_parent.setdefault(parent_id, []).append(menu)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.sort, item.create_time))

    def build(parent_id: str | None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for menu in children_by_parent.get(parent_id, []):
            item = menu_item(menu)
            item["children"] = build(menu.menu_id)
            item["childCount"] = len(item["children"])
            result.append(item)
        return result

    return build(None)


def permitted_menu_tree_items(menus: list[AdminMenu], account: AdminAccount) -> list[dict[str, Any]]:
    allowed_permissions = set(account.permissions or [])
    is_superadmin = account.role == "superadmin"

    def can_access(menu: AdminMenu) -> bool:
        return is_superadmin or not menu.permission or menu.permission in allowed_permissions

    all_tree = menu_tree_items([menu for menu in menus if menu.status == "enabled" and menu.type != "button"])

    def prune(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        menu_by_id = {menu.menu_id: menu for menu in menus}
        for node in nodes:
            children = prune(node.get("children", []))
            source = menu_by_id.get(node["menuId"])
            if source and (children or (source.type != "catalog" and can_access(source))):
                node["children"] = children
                node["childCount"] = len(children)
                result.append(node)
        return result

    return prune(all_tree)


def flatten_menu_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append({key: value for key, value in node.items() if key != "children"})
        result.extend(flatten_menu_tree(node.get("children", [])))
    return result


def notification_item(message: Message) -> dict[str, Any]:
    return {
        "messageId": message.message_id,
        "title": message.title or "",
        "content": message.content or "",
        "type": message.type,
        "isRead": message.is_read,
        "time": format_time(message.create_time),
        "createdAt": format_time(message.create_time),
        "updatedAt": format_time(message.update_time),
        "sourceId": message.post_id,
    }


def ensure_admin_notification(db: Session, admin_subject: str, message: AdminSystemMessage) -> None:
    admin_user_id = f"admin:{admin_subject}"
    exists = (
        db.query(Message)
        .filter(Message.user_id == admin_user_id, Message.type == "admin_system", Message.post_id == message.message_id)
        .one_or_none()
    )
    if exists is not None:
        exists.title = message.title
        exists.content = message.content
        exists.last_time = utc_now()
        return
    db.add(
        Message(
            message_id=new_business_id("ntf"),
            user_id=admin_user_id,
            sender_id=None,
            type="admin_system",
            title=message.title,
            content=message.content,
            post_id=message.message_id,
            is_read=False,
        )
    )


def publish_system_message_to_users(db: Session, message: AdminSystemMessage) -> int:
    query = db.query(User).filter(User.is_active.is_(True))
    if message.target == "new":
        query = query.order_by(User.create_time.desc()).limit(200)
    users = query.all()
    created = 0
    for user in users:
        exists = (
            db.query(Message)
            .filter(Message.user_id == user.user_id, Message.type == "system", Message.post_id == message.message_id)
            .one_or_none()
        )
        if exists is not None:
            exists.title = message.title
            exists.content = message.content
            exists.last_time = utc_now()
            continue
        db.add(
            Message(
                message_id=new_business_id("ntf"),
                user_id=user.user_id,
                sender_id=None,
                type="system",
                title=message.title,
                content=message.content,
                post_id=message.message_id,
                is_read=False,
            )
        )
        created += 1
    return created


def get_or_create_agreement(db: Session, agreement_type: str) -> AdminAgreement:
    agreement = db.query(AdminAgreement).filter(AdminAgreement.type == agreement_type).one_or_none()
    if agreement is not None:
        return agreement
    agreement = AdminAgreement(
        type=agreement_type,
        content=DEFAULT_AGREEMENTS[agreement_type],
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement


@router.post(
    "/auth/login",
    response_model=AdminResponse,
    summary="后台登录",
    description="后台管理系统登录接口。演示账号 admin，密码 123456。",
)
def admin_login(payload: AdminLoginRequest, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    seed_accounts_if_empty(db)
    account = db.query(AdminAccount).filter(AdminAccount.username == payload.username).one_or_none()
    if account is None or account.password != payload.password:
        raise fail(status.HTTP_400_BAD_REQUEST, "用户名或密码错误")
    if account.status != "active":
        raise fail(status.HTTP_403_FORBIDDEN, "账号已禁用，请联系管理员")
    account.last_login = format_time(utc_now())
    account.last_time = utc_now()
    db.commit()
    token = create_access_token(f"admin:{account.username}")
    return ok(
        {
            "token": token,
            "username": account.username,
            "nickname": account.nickname,
            "role": account.role,
            "permissions": account.permissions,
        },
        "登录成功",
    )


@router.get(
    "/dashboard/metrics",
    response_model=AdminResponse,
    summary="看板指标",
    description="获取后台首页数据看板指标，包括用户、内容、评论和点赞统计。",
)
def dashboard_metrics(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    post_query = db.query(Post).filter(Post.is_deleted.is_(False))
    total_posts = post_query.count()
    offline_posts = post_query.filter(Post.status == "offline").count()
    online_posts = total_posts - offline_posts
    total_comments = db.query(func.count(Comment.id)).filter(Comment.is_deleted.is_(False)).scalar() or 0
    total_likes = (
        db.query(func.coalesce(func.sum(Post.like_count), 0))
        .filter(Post.is_deleted.is_(False))
        .scalar()
        or 0
    )
    return ok(
        {
            "totalUsers": total_users,
            "activeUsers": active_users,
            "totalPosts": total_posts,
            "onlinePosts": online_posts,
            "offlinePosts": offline_posts,
            "totalComments": total_comments,
            "totalLikes": total_likes,
        }
    )


@router.get(
    "/notifications",
    response_model=AdminResponse,
    summary="后台通知下拉",
    description="PC 后台右上角消息通知下拉接口，返回未读数量和最近通知列表。",
)
def list_admin_notifications(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
    limit: Annotated[int, Query(ge=1, le=50, description="返回数量")] = 10,
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    recent_system_messages = db.query(AdminSystemMessage).order_by(AdminSystemMessage.create_time.desc()).limit(limit).all()
    for system_message in recent_system_messages:
        ensure_admin_notification(db, admin_subject, system_message)
    db.commit()

    query = db.query(Message).filter(Message.user_id == admin_user_id)
    unread_count = query.filter(Message.is_read.is_(False)).count()
    messages = query.order_by(Message.create_time.desc()).limit(limit).all()
    return ok({"unreadCount": unread_count, "list": [notification_item(message) for message in messages]})


@router.get(
    "/notifications/{messageId}",
    response_model=AdminResponse,
    summary="后台通知详情",
    description="PC 后台点击右上角通知时调用；按当前 admin 标记该条通知为已读并返回详情。",
)
def get_admin_notification_detail(
    messageId: Annotated[str, Path(description="通知消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    message = db.query(Message).filter(Message.user_id == admin_user_id, Message.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "通知未找到")
    message.is_read = True
    message.last_time = utc_now()
    db.commit()
    db.refresh(message)
    return ok(notification_item(message), "已读取通知详情")


@router.put(
    "/notifications/read-all",
    response_model=AdminResponse,
    summary="后台通知全部已读",
    description="PC 后台右上角消息通知下拉全部标记已读。",
)
def read_all_admin_notifications(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    db.query(Message).filter(Message.user_id == admin_user_id, Message.is_read.is_(False)).update(
        {Message.is_read: True, Message.last_time: utc_now()},
        synchronize_session=False,
    )
    db.commit()
    return ok(None, "已全部标记为已读")


@router.put(
    "/notifications/{messageId}/read",
    response_model=AdminResponse,
    summary="后台通知已读",
    description="PC 后台右上角消息通知下拉单条标记已读。",
)
def read_admin_notification(
    messageId: Annotated[str, Path(description="通知消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    admin_user_id = f"admin:{admin_subject}"
    message = db.query(Message).filter(Message.user_id == admin_user_id, Message.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "通知未找到")
    message.is_read = True
    message.last_time = utc_now()
    db.commit()
    return ok(notification_item(message), "已标记为已读")


@router.get(
    "/users",
    response_model=AdminResponse,
    summary="用户列表",
    description="后台用户管理列表，支持按用户 ID、昵称、手机号、账号状态筛选。",
)
def list_admin_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    userId: Annotated[str | None, Query(description="业务用户 ID，精确匹配")] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    nickname: Annotated[str | None, Query(description="用户昵称，模糊匹配")] = None,
    phone: Annotated[str | None, Query(description="手机号，模糊匹配")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="账号状态：normal 正常，banned 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    user_id = userId or user_id_legacy
    query = db.query(User)
    if user_id:
        query = query.filter(User.user_id == user_id)
    if nickname:
        query = query.filter(User.nickname.ilike(f"%{nickname}%"))
    if phone:
        query = query.filter(User.phone.ilike(f"%{phone}%"))
    if status_filter == "normal":
        query = query.filter(User.is_active.is_(True))
    elif status_filter == "banned":
        query = query.filter(User.is_active.is_(False))

    total = query.count()
    users = query.order_by(User.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [user_item(db, user) for user in users], "total": total})


@router.get(
    "/users/{userId}",
    response_model=AdminResponse,
    summary="用户详情",
    description="后台查看单个业务用户详情。",
)
def get_admin_user(
    userId: Annotated[str, Path(description="业务用户 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user_id = userId
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    return ok(user_item(db, user))


@router.put(
    "/users/{userId}",
    response_model=AdminResponse,
    summary="修改用户状态",
    description="后台禁用或解禁用户。禁用后该用户 token 将无法访问需要登录的用户端接口。",
)
def update_admin_user_status(
    userId: Annotated[str, Path(description="业务用户 ID")],
    payload: AdminUserStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    user_id = userId
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if user is None:
        raise fail(status.HTTP_404_NOT_FOUND, "用户未找到")
    user.is_active = payload.status == "normal"
    user.last_time = utc_now()
    db.commit()
    return ok(None, "操作成功")


@router.get(
    "/posts",
    response_model=AdminResponse,
    summary="内容列表",
    description="后台内容管理列表，支持按发布人、内容关键词和上架状态筛选。",
)
def list_admin_posts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    nickname: Annotated[str | None, Query(description="发布人昵称，模糊匹配")] = None,
    userId: Annotated[str | None, Query(description="发布人业务用户 ID，精确匹配")] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="内容状态：online 已上架，offline 已下架")] = None,
    content: Annotated[str | None, Query(description="内容正文关键词，模糊匹配")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 5,
) -> dict[str, Any]:
    user_id = userId or user_id_legacy
    query = db.query(Post).options(joinedload(Post.author)).filter(Post.is_deleted.is_(False))
    if user_id:
        query = query.filter(Post.user_id == user_id)
    if status_filter == "online":
        query = query.filter(Post.status != "offline")
    elif status_filter == "offline":
        query = query.filter(Post.status == "offline")
    if content:
        query = query.filter(Post.content.ilike(f"%{content}%"))
    if nickname:
        query = query.join(User, User.user_id == Post.user_id).filter(User.nickname.ilike(f"%{nickname}%"))

    total = query.count()
    posts = query.order_by(Post.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [post_item(post) for post in posts], "total": total})


@router.get(
    "/posts/{postId}",
    response_model=AdminResponse,
    summary="内容详情",
    description="后台查看单条内容详情；后台可查看已下架内容。",
)
def get_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
    post = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(Post.post_id == post_id, Post.is_deleted.is_(False))
        .one_or_none()
    )
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    return ok(post_item(post))


@router.put(
    "/posts/{postId}/offline",
    response_model=AdminResponse,
    summary="内容下架",
    description="后台将内容置为 offline。下架后用户端公开列表和详情不可见。",
)
def offline_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
    post = db.query(Post).filter(Post.post_id == post_id, Post.is_deleted.is_(False)).one_or_none()
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    post.status = "offline"
    post.last_time = utc_now()
    db.commit()
    return ok(None, "内容已成功下架")


@router.put(
    "/posts/{postId}/restore",
    response_model=AdminResponse,
    summary="恢复上架",
    description="后台将已下架内容恢复为 online，恢复后用户端可见。",
)
def restore_admin_post(
    postId: Annotated[str, Path(description="内容 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    post_id = postId
    post = db.query(Post).filter(Post.post_id == post_id, Post.is_deleted.is_(False)).one_or_none()
    if post is None:
        raise fail(status.HTTP_404_NOT_FOUND, "内容未找到")
    post.status = "online"
    post.last_time = utc_now()
    db.commit()
    return ok(None, "内容已恢复上架")


@router.get(
    "/comments",
    response_model=AdminResponse,
    summary="评论列表",
    description="后台评论管理列表，支持按内容 ID 或评论人用户 ID 筛选。",
)
def list_admin_comments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    postId: Annotated[str | None, Query(description="内容 ID，精确匹配")] = None,
    userId: Annotated[str | None, Query(description="评论人业务用户 ID，精确匹配")] = None,
    post_id_legacy: Annotated[str | None, Query(alias="post_id", description="兼容旧参数 post_id", include_in_schema=False)] = None,
    user_id_legacy: Annotated[str | None, Query(alias="user_id", description="兼容旧参数 user_id", include_in_schema=False)] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    post_id = postId or post_id_legacy
    user_id = userId or user_id_legacy
    query = db.query(Comment).filter(Comment.is_deleted.is_(False))
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    if user_id:
        query = query.filter(Comment.user_id == user_id)
    total = query.count()
    comments = query.order_by(Comment.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [comment_item(db, comment) for comment in comments], "total": total})


@router.delete(
    "/comments/{commentId}",
    response_model=AdminResponse,
    summary="删除评论",
    description="后台删除评论。当前为软删除，并同步扣减内容评论数。",
)
def delete_admin_comment(
    commentId: Annotated[str, Path(description="评论 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    comment_id = commentId
    comment = db.query(Comment).filter(Comment.comment_id == comment_id, Comment.is_deleted.is_(False)).one_or_none()
    if comment is None:
        raise fail(status.HTTP_404_NOT_FOUND, "评论未找到")
    post = db.query(Post).filter(Post.post_id == comment.post_id).one_or_none()
    comment.is_deleted = True
    comment.delete_time = utc_now()
    comment.last_time = comment.delete_time
    if post is not None:
        post.comment_count = max(0, post.comment_count - 1)
        post.last_time = utc_now()
    db.commit()
    return ok(None, "评论已成功删除")


@router.get(
    "/agreement/{agreementType}",
    response_model=AdminResponse,
    summary="获取协议",
    description="获取后台维护的协议内容。agreementType 支持 privacy 或 user。",
)
def get_admin_agreement(
    agreementType: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    agreement_type = agreementType
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    return ok(agreement.content)


@router.put(
    "/agreement/{agreementType}",
    response_model=AdminResponse,
    summary="更新协议",
    description="更新后台维护的协议内容。agreementType 支持 privacy 或 user。",
)
def update_admin_agreement(
    agreementType: Annotated[str, Path(description="协议类型：privacy 隐私协议，user 用户协议")],
    payload: AgreementUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    agreement_type = agreementType
    if agreement_type not in DEFAULT_AGREEMENTS:
        raise fail(status.HTTP_404_NOT_FOUND, "协议未找到")
    agreement = get_or_create_agreement(db, agreement_type)
    agreement.content = payload.content
    agreement.last_time = utc_now()
    db.commit()
    return ok(None, "协议更新成功")


def seed_announcements_if_empty(db: Session) -> None:
    if db.query(AdminAnnouncement).count():
        return
    db.add_all(
        [
            AdminAnnouncement(
                announcement_id=new_business_id("ann"),
                title="欢迎使用即闪后台",
                type="info",
                content="<p>即闪平台后台公告模块已启用。</p>",
                link="",
                pinned=True,
                start_time=format_time(utc_now()),
                end_time="",
                status="active",
            ),
            AdminAnnouncement(
                announcement_id=new_business_id("ann"),
                title="内容安全巡检提醒",
                type="warning",
                content="<p>请定期关注内容审核、评论举报和标签风险数据。</p>",
                link="",
                pinned=False,
                start_time=format_time(utc_now()),
                end_time="",
                status="active",
            ),
        ]
    )
    db.commit()


def seed_versions_if_empty(db: Session) -> None:
    now = format_time(utc_now())
    defaults = {
        "iOS": ("1.0.0", "100"),
        "Android": ("1.0.0", "100"),
        "HarmonyOS": ("1.0.0", "100"),
    }
    existing_platforms = {row[0] for row in db.query(AdminVersion.platform).filter(AdminVersion.status != "deprecated").distinct().all()}
    missing_versions = [
        AdminVersion(
            version_id=new_business_id("ver"),
            platform=platform,
            version=version,
            build=build,
            force_update=False,
            status="released",
            beta_pct=100,
            notes="首个稳定版本",
            notes_type="text",
            download_url="",
            release_time=now,
        )
        for platform, (version, build) in defaults.items()
        if platform not in existing_platforms
    ]
    if missing_versions:
        db.add_all(missing_versions)
        db.commit()


def seed_accounts_if_empty(db: Session) -> None:
    if db.query(AdminAccount).count():
        return
    all_permissions = ["dashboard", "user", "content", "comment", "simulator", "account", "announcement", "version", "tag", "region", "dict", "message", "agreement"]
    db.add(
        AdminAccount(
            account_id=new_business_id("acc"),
            username="admin",
            nickname="超级管理员",
            avatar="",
            role="superadmin",
            permissions=all_permissions,
            status="active",
            email="admin@example.com",
            phone="13800000000",
            remark="系统默认管理员",
            password="123456",
            last_login=format_time(utc_now()),
        )
    )
    db.commit()


def seed_menus_if_empty(db: Session) -> None:
    existing_ids = {row[0] for row in db.query(AdminMenu.menu_id).all()}
    new_menus = []
    for item in DEFAULT_ADMIN_MENUS:
        if item["menu_id"] in existing_ids:
            continue
        new_menus.append(
            AdminMenu(
                menu_id=item["menu_id"],
                parent_id=item.get("parent_id"),
                title=item["title"],
                path=item["path"],
                name=item["name"],
                component=item.get("component"),
                redirect=item.get("redirect"),
                icon=item.get("icon"),
                type=item.get("type", "menu"),
                permission=item.get("permission"),
                sort=item.get("sort", 0),
                status=item.get("status", "enabled"),
                visible=item.get("visible", True),
                keep_alive=item.get("keep_alive", False),
                affix=item.get("affix", False),
                external_link=item.get("external_link"),
                remark=item.get("remark"),
            )
        )
    if new_menus:
        db.add_all(new_menus)
        db.commit()


def get_announcement_or_404(db: Session, announcement_id: str) -> AdminAnnouncement:
    announcement = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id == announcement_id).one_or_none()
    if announcement is None:
        raise fail(status.HTTP_404_NOT_FOUND, "公告未找到")
    return announcement


def get_or_create_single_banner(db: Session) -> AdminAnnouncement:
    announcement = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id == SINGLE_BANNER_ANNOUNCEMENT_ID).one_or_none()
    if announcement is not None:
        return announcement
    announcement = AdminAnnouncement(
        announcement_id=SINGLE_BANNER_ANNOUNCEMENT_ID,
        title="【系统通知】即闪 App 服务升级公告",
        type="info",
        content="<p>请在后台维护 App 首页单公告内容。</p>",
        link="",
        pinned=True,
        start_time=format_time(utc_now()),
        end_time="",
        status="active",
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


def get_version_or_404(db: Session, version_id: str) -> AdminVersion:
    version = db.query(AdminVersion).filter(AdminVersion.version_id == version_id).one_or_none()
    if version is None:
        raise fail(status.HTTP_404_NOT_FOUND, "版本未找到")
    return version


def get_account_or_404(db: Session, account_id: str) -> AdminAccount:
    account = db.query(AdminAccount).filter(AdminAccount.account_id == account_id).one_or_none()
    if account is None:
        raise fail(status.HTTP_404_NOT_FOUND, "账号未找到")
    return account


def get_menu_or_404(db: Session, menu_id: str) -> AdminMenu:
    menu = db.query(AdminMenu).filter(AdminMenu.menu_id == menu_id).one_or_none()
    if menu is None:
        raise fail(status.HTTP_404_NOT_FOUND, "菜单未找到")
    return menu


def get_current_admin_account(db: Session, username: str) -> AdminAccount:
    seed_accounts_if_empty(db)
    account = db.query(AdminAccount).filter(AdminAccount.username == username).one_or_none()
    if account is None:
        raise fail(status.HTTP_401_UNAUTHORIZED, "登录账号不存在，请重新登录")
    if account.status != "active":
        raise fail(status.HTTP_403_FORBIDDEN, "账号已禁用，请联系管理员")
    return account


def validate_menu_parent(db: Session, parent_id: str | None, self_id: str | None = None) -> None:
    if not parent_id:
        return
    if parent_id == self_id:
        raise fail(status.HTTP_400_BAD_REQUEST, "上级菜单不能选择自己")
    parent = get_menu_or_404(db, parent_id)
    cursor = parent
    while cursor.parent_id:
        if cursor.parent_id == self_id:
            raise fail(status.HTTP_400_BAD_REQUEST, "上级菜单不能选择自己的下级")
        cursor = get_menu_or_404(db, cursor.parent_id)


def validate_menu_unique(db: Session, name: str, path: str, self_id: str | None = None) -> None:
    name_query = db.query(AdminMenu).filter(AdminMenu.name == name)
    path_query = db.query(AdminMenu).filter(AdminMenu.path == path)
    if self_id:
        name_query = name_query.filter(AdminMenu.menu_id != self_id)
        path_query = path_query.filter(AdminMenu.menu_id != self_id)
    if name_query.one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "路由名称已存在")
    if path_query.one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "路由路径已存在")


@router.get("/announcements", response_model=AdminResponse, summary="公告列表", description="公告管理列表，支持关键词、类型、状态筛选。")
def list_admin_announcements(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="标题或内容关键词")] = None,
    type: Annotated[str | None, Query(description="公告类型：info/warning/danger")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：active/inactive")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=10000, description="每页数量")] = 10,
) -> dict[str, Any]:
    seed_announcements_if_empty(db)
    query = db.query(AdminAnnouncement)
    if keyword:
        query = query.filter((AdminAnnouncement.title.ilike(f"%{keyword}%")) | (AdminAnnouncement.content.ilike(f"%{keyword}%")))
    if type:
        query = query.filter(AdminAnnouncement.type == type)
    if status_filter:
        query = query.filter(AdminAnnouncement.status == status_filter)
    total = query.count()
    items = query.order_by(AdminAnnouncement.pinned.desc(), AdminAnnouncement.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [announcement_item(item) for item in items], "total": total})


@router.post("/announcements", response_model=AdminResponse, summary="新增公告", description="新增后台公告。")
def create_admin_announcement(payload: AdminAnnouncementPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    if not payload.title or not payload.content:
        raise fail(status.HTTP_400_BAD_REQUEST, "公告标题和内容不能为空")
    announcement = AdminAnnouncement(
        announcement_id=new_business_id("ann"),
        title=payload.title,
        type=payload.type or "info",
        content=payload.content,
        link=payload.link or "",
        pinned=bool(payload.pinned),
        start_time=payload.startTime or format_time(utc_now()),
        end_time=payload.endTime or "",
        status=payload.status or "active",
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return ok(announcement_item(announcement), "公告创建成功")


@router.put("/announcements/batch-publish", response_model=AdminResponse, summary="批量发布公告", description="批量设置公告为发布状态。")
def batch_publish_announcements_first(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).update({"status": "active", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量发布成功")


@router.put("/announcements/batch-disable", response_model=AdminResponse, summary="批量停用公告", description="批量设置公告为停用状态。")
def batch_disable_announcements_first(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).update({"status": "inactive", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量停用成功")


@router.post("/announcements/batch-delete", response_model=AdminResponse, summary="批量删除公告", description="批量删除后台公告。")
def batch_delete_announcements_first(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量删除成功")


@router.get("/announcements/{announcementId}", response_model=AdminResponse, summary="公告详情", description="根据公告 ID 查询公告详情。SINGLE_BANNER 为 App 首页单公告。")
def get_admin_announcement(announcementId: Annotated[str, Path(description="公告 ID；SINGLE_BANNER 表示 App 首页单公告")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    if announcementId == SINGLE_BANNER_ANNOUNCEMENT_ID:
        announcement = get_or_create_single_banner(db)
    else:
        announcement = get_announcement_or_404(db, announcementId)
    return ok(announcement_item(announcement))


@router.put("/announcements/{announcementId}", response_model=AdminResponse, summary="修改公告", description="修改后台公告，支持局部字段更新。")
def update_admin_announcement(announcementId: Annotated[str, Path(description="公告 ID")], payload: AdminAnnouncementPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    if announcementId == SINGLE_BANNER_ANNOUNCEMENT_ID:
        announcement = get_or_create_single_banner(db)
    else:
        announcement = get_announcement_or_404(db, announcementId)
    if payload.title is not None:
        announcement.title = payload.title
    if payload.type is not None:
        announcement.type = payload.type
    if payload.content is not None:
        announcement.content = payload.content
    if payload.link is not None:
        announcement.link = payload.link
    if payload.pinned is not None:
        announcement.pinned = payload.pinned
    if payload.startTime is not None:
        announcement.start_time = payload.startTime
    if payload.endTime is not None:
        announcement.end_time = payload.endTime
    if payload.status is not None:
        announcement.status = payload.status
    announcement.last_time = utc_now()
    db.commit()
    db.refresh(announcement)
    return ok(announcement_item(announcement), "公告更新成功")


@router.delete("/announcements/{announcementId}", response_model=AdminResponse, summary="删除公告", description="删除后台公告。")
def delete_admin_announcement(announcementId: Annotated[str, Path(description="公告 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    announcement = get_announcement_or_404(db, announcementId)
    db.delete(announcement)
    db.commit()
    return ok(None, "公告删除成功")


@router.put("/announcements/batch-publish", response_model=AdminResponse, summary="批量发布公告", description="批量设置公告为发布状态。")
def batch_publish_announcements(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).update({"status": "active", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量发布成功")


@router.put("/announcements/batch-disable", response_model=AdminResponse, summary="批量停用公告", description="批量设置公告为停用状态。")
def batch_disable_announcements(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).update({"status": "inactive", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量停用成功")


@router.post("/announcements/batch-delete", response_model=AdminResponse, summary="批量删除公告", description="批量删除后台公告。")
def batch_delete_announcements(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminAnnouncement).filter(AdminAnnouncement.announcement_id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量删除成功")


@router.get("/versions", response_model=AdminResponse, summary="版本列表", description="版本管理列表，支持平台、状态、强制更新筛选。")
def list_admin_versions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    platform: Annotated[str | None, Query(description="平台：iOS/Android/HarmonyOS")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：released/beta/deprecated")] = None,
    forceUpdate: Annotated[bool | None, Query(description="是否强制更新")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=10000, description="每页数量")] = 10,
) -> dict[str, Any]:
    seed_versions_if_empty(db)
    query = db.query(AdminVersion)
    if platform:
        query = query.filter(AdminVersion.platform == platform)
    if status_filter:
        query = query.filter(AdminVersion.status == status_filter)
    if forceUpdate is not None:
        query = query.filter(AdminVersion.force_update == forceUpdate)
    total = query.count()
    items = query.order_by(AdminVersion.platform.asc(), AdminVersion.build.desc(), AdminVersion.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [version_item(item) for item in items], "total": total})


@router.post("/versions", response_model=AdminResponse, summary="新增版本", description="新增 App 版本记录。")
def create_admin_version(payload: AdminVersionPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    if not payload.platform or not payload.version or not payload.build:
        raise fail(status.HTTP_400_BAD_REQUEST, "平台、版本号和 Build 号不能为空")
    version = AdminVersion(
        version_id=new_business_id("ver"),
        platform=payload.platform,
        version=payload.version,
        build=payload.build,
        force_update=bool(payload.forceUpdate),
        status=payload.status or "released",
        beta_pct=payload.betaPct if payload.betaPct is not None else 0,
        notes=payload.notes or "",
        notes_type=payload.notesType or "text",
        download_url=payload.downloadUrl or "",
        release_time=format_time(utc_now()),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return ok(version_item(version), "版本创建成功")


@router.put("/versions/batch-deprecate", response_model=AdminResponse, summary="批量下线版本", description="批量设置 App 版本为已下线。")
def batch_deprecate_versions_first(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminVersion).filter(AdminVersion.version_id.in_(payload.ids)).update({"status": "deprecated", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量下线成功")


@router.post("/versions/batch-delete", response_model=AdminResponse, summary="批量删除版本", description="批量删除 App 版本记录。")
def batch_delete_versions_first(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminVersion).filter(AdminVersion.version_id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量删除成功")


@router.put("/versions/{versionId}", response_model=AdminResponse, summary="修改版本", description="修改 App 版本记录，支持局部字段更新。")
def update_admin_version(versionId: Annotated[str, Path(description="版本 ID")], payload: AdminVersionPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    version = get_version_or_404(db, versionId)
    if payload.platform is not None:
        version.platform = payload.platform
    if payload.version is not None:
        version.version = payload.version
    if payload.build is not None:
        version.build = payload.build
    if payload.forceUpdate is not None:
        version.force_update = payload.forceUpdate
    if payload.status is not None:
        version.status = payload.status
    if payload.betaPct is not None:
        version.beta_pct = payload.betaPct
    if payload.notes is not None:
        version.notes = payload.notes
    if payload.notesType is not None:
        version.notes_type = payload.notesType
    if payload.downloadUrl is not None:
        version.download_url = payload.downloadUrl
    version.last_time = utc_now()
    db.commit()
    db.refresh(version)
    return ok(version_item(version), "版本更新成功")


@router.delete("/versions/{versionId}", response_model=AdminResponse, summary="删除版本", description="删除 App 版本记录。")
def delete_admin_version(versionId: Annotated[str, Path(description="版本 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    version = get_version_or_404(db, versionId)
    db.delete(version)
    db.commit()
    return ok(None, "版本删除成功")


@router.put("/versions/{versionId}/deprecate", response_model=AdminResponse, summary="下线版本", description="将 App 版本状态设置为已下线。")
def deprecate_admin_version(versionId: Annotated[str, Path(description="版本 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    version = get_version_or_404(db, versionId)
    version.status = "deprecated"
    version.last_time = utc_now()
    db.commit()
    db.refresh(version)
    return ok(version_item(version), "版本已下线")


@router.put("/versions/batch-deprecate", response_model=AdminResponse, summary="批量下线版本", description="批量设置 App 版本为已下线。")
def batch_deprecate_versions(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminVersion).filter(AdminVersion.version_id.in_(payload.ids)).update({"status": "deprecated", "last_time": utc_now()}, synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量下线成功")


@router.post("/versions/batch-delete", response_model=AdminResponse, summary="批量删除版本", description="批量删除 App 版本记录。")
def batch_delete_versions(payload: BatchIdsPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    count = db.query(AdminVersion).filter(AdminVersion.version_id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return ok({"count": count}, "批量删除成功")


@router.get("/menus", response_model=AdminResponse, summary="菜单列表", description="后台动态菜单列表，默认返回树形结构。")
def list_admin_menus(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="菜单标题、路径或路由名称关键词")] = None,
    parentId: Annotated[str | None, Query(description="上级菜单 ID；传入后只查询直接下级")] = None,
    type: Annotated[str | None, Query(description="菜单类型：catalog/menu/button/link")] = None,
    permission: Annotated[str | None, Query(description="权限标识")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled/disabled")] = None,
    visible: Annotated[bool | None, Query(description="是否在菜单显示")] = None,
    tree: Annotated[bool, Query(description="是否返回树形 children")] = True,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=1000, description="每页数量")] = 1000,
) -> dict[str, Any]:
    seed_menus_if_empty(db)
    query = db.query(AdminMenu)
    if keyword:
        query = query.filter((AdminMenu.title.ilike(f"%{keyword}%")) | (AdminMenu.path.ilike(f"%{keyword}%")) | (AdminMenu.name.ilike(f"%{keyword}%")))
    if parentId is not None:
        query = query.filter(AdminMenu.parent_id == parentId)
    if type:
        query = query.filter(AdminMenu.type == type)
    if permission:
        query = query.filter(AdminMenu.permission == permission)
    if status_filter:
        query = query.filter(AdminMenu.status == status_filter)
    if visible is not None:
        query = query.filter(AdminMenu.visible == visible)
    total = query.count()
    menus = query.order_by(AdminMenu.sort.asc(), AdminMenu.create_time.asc()).offset((page - 1) * limit).limit(limit).all()
    if tree and parentId is None:
        return ok({"list": menu_tree_items(menus), "total": total})
    return ok({"list": [menu_item(menu) for menu in menus], "total": total})


@router.get("/menus/tree", response_model=AdminResponse, summary="当前账号菜单树", description="根据当前登录账号权限返回可显示的动态菜单树。")
def current_admin_menu_tree(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    seed_menus_if_empty(db)
    account = get_current_admin_account(db, admin_subject)
    menus = db.query(AdminMenu).order_by(AdminMenu.sort.asc(), AdminMenu.create_time.asc()).all()
    tree = permitted_menu_tree_items(menus, account)
    return ok({"list": tree, "total": len(flatten_menu_tree(tree)), "permissions": account.permissions or [], "role": account.role})


@router.get("/menus/routes", response_model=AdminResponse, summary="动态路由", description="根据当前登录账号权限返回前端动态路由和菜单树。")
def current_admin_menu_routes(
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    seed_menus_if_empty(db)
    account = get_current_admin_account(db, admin_subject)
    menus = db.query(AdminMenu).order_by(AdminMenu.sort.asc(), AdminMenu.create_time.asc()).all()
    tree = permitted_menu_tree_items(menus, account)
    flat_list = flatten_menu_tree(tree)
    return ok(
        {
            "list": tree,
            "routes": tree,
            "flatList": flat_list,
            "permissions": account.permissions or [],
            "role": account.role,
            "username": account.username,
        }
    )


@router.post("/menus", response_model=AdminResponse, summary="新增菜单", description="新增后台动态菜单或动态路由配置。")
def create_admin_menu(payload: AdminMenuPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    seed_menus_if_empty(db)
    validate_menu_parent(db, payload.parentId)
    validate_menu_unique(db, payload.name, payload.path)
    menu = AdminMenu(
        menu_id=new_business_id("menu"),
        parent_id=payload.parentId,
        title=payload.title,
        path=payload.path,
        name=payload.name,
        component=payload.component,
        redirect=payload.redirect,
        icon=payload.icon,
        type=payload.type,
        permission=payload.permission,
        sort=payload.sort,
        status=payload.status,
        visible=payload.visible,
        keep_alive=payload.keepAlive,
        affix=payload.affix,
        external_link=payload.externalLink,
        remark=payload.remark,
    )
    db.add(menu)
    db.commit()
    db.refresh(menu)
    return ok(menu_item(menu), "菜单创建成功")


@router.get("/menus/{menuId}", response_model=AdminResponse, summary="菜单详情", description="根据菜单 ID 查询菜单详情。")
def get_admin_menu(menuId: Annotated[str, Path(description="业务菜单 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    seed_menus_if_empty(db)
    return ok(menu_item(get_menu_or_404(db, menuId)))


@router.put("/menus/{menuId}", response_model=AdminResponse, summary="修改菜单", description="修改后台动态菜单或动态路由配置。")
def update_admin_menu(menuId: Annotated[str, Path(description="业务菜单 ID")], payload: AdminMenuPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    seed_menus_if_empty(db)
    menu = get_menu_or_404(db, menuId)
    validate_menu_parent(db, payload.parentId, self_id=menuId)
    validate_menu_unique(db, payload.name, payload.path, self_id=menuId)
    menu.parent_id = payload.parentId
    menu.title = payload.title
    menu.path = payload.path
    menu.name = payload.name
    menu.component = payload.component
    menu.redirect = payload.redirect
    menu.icon = payload.icon
    menu.type = payload.type
    menu.permission = payload.permission
    menu.sort = payload.sort
    menu.status = payload.status
    menu.visible = payload.visible
    menu.keep_alive = payload.keepAlive
    menu.affix = payload.affix
    menu.external_link = payload.externalLink
    menu.remark = payload.remark
    menu.last_time = utc_now()
    db.commit()
    db.refresh(menu)
    return ok(menu_item(menu), "菜单更新成功")


@router.delete("/menus/{menuId}", response_model=AdminResponse, summary="删除菜单", description="删除动态菜单；存在下级时不允许删除。")
def delete_admin_menu(menuId: Annotated[str, Path(description="业务菜单 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    seed_menus_if_empty(db)
    menu = get_menu_or_404(db, menuId)
    if db.query(AdminMenu).filter(AdminMenu.parent_id == menuId).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "存在下级菜单，不能删除")
    db.delete(menu)
    db.commit()
    return ok(None, "菜单删除成功")


@router.get("/accounts", response_model=AdminResponse, summary="后台账号列表", description="账号管理列表。")
def list_admin_accounts(db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    seed_accounts_if_empty(db)
    accounts = db.query(AdminAccount).order_by(AdminAccount.role.asc(), AdminAccount.create_time.desc()).all()
    return ok([account_item(account) for account in accounts])


@router.post("/accounts", response_model=AdminResponse, summary="新增后台账号", description="新增后台管理账号。")
def create_admin_account(payload: AdminAccountPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    if not payload.username or not payload.nickname:
        raise fail(status.HTTP_400_BAD_REQUEST, "账号和昵称不能为空")
    if db.query(AdminAccount).filter(AdminAccount.username == payload.username).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "账号已存在")
    account = AdminAccount(
        account_id=new_business_id("acc"),
        username=payload.username,
        nickname=payload.nickname,
        avatar=payload.avatar or "",
        role=payload.role or "admin",
        permissions=payload.permissions or [],
        status=payload.status or "active",
        email=payload.email or "",
        phone=payload.phone or "",
        remark=payload.remark or "",
        password="123456",
        last_login="",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return ok(account_item(account), "账号创建成功")


@router.put("/accounts/{accountId}", response_model=AdminResponse, summary="修改后台账号", description="修改后台账号信息。")
def update_admin_account(accountId: Annotated[str, Path(description="账号 ID")], payload: AdminAccountPayload, db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    account = get_account_or_404(db, accountId)
    if payload.username is not None and payload.username != account.username:
        if db.query(AdminAccount).filter(AdminAccount.username == payload.username).one_or_none():
            raise fail(status.HTTP_400_BAD_REQUEST, "账号已存在")
        account.username = payload.username
    if payload.nickname is not None:
        account.nickname = payload.nickname
    if payload.avatar is not None:
        account.avatar = payload.avatar
    if payload.role is not None:
        account.role = payload.role
    if payload.permissions is not None:
        account.permissions = payload.permissions
    if payload.status is not None:
        account.status = payload.status
    if payload.email is not None:
        account.email = payload.email
    if payload.phone is not None:
        account.phone = payload.phone
    if payload.remark is not None:
        account.remark = payload.remark
    account.last_time = utc_now()
    db.commit()
    db.refresh(account)
    return ok(account_item(account), "账号更新成功")


@router.delete("/accounts/{accountId}", response_model=AdminResponse, summary="删除后台账号", description="删除后台账号。")
def delete_admin_account(accountId: Annotated[str, Path(description="账号 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    account = get_account_or_404(db, accountId)
    db.delete(account)
    db.commit()
    return ok(None, "账号删除成功")


@router.post("/accounts/{accountId}/reset-password", response_model=AdminResponse, summary="重置后台账号密码", description="将后台账号密码重置为 123456。")
def reset_admin_account_password(accountId: Annotated[str, Path(description="账号 ID")], db: Annotated[Session, Depends(get_db)], _: Annotated[str, Depends(get_admin_subject)]) -> dict[str, Any]:
    account = get_account_or_404(db, accountId)
    account.password = "123456"
    account.last_time = utc_now()
    db.commit()
    return ok(None, "密码已重置为 123456")


@router.get(
    "/tags",
    response_model=AdminResponse,
    summary="标签列表",
    description="系统配置 - 标签管理列表，支持按标签名称和状态筛选。",
)
def list_admin_tags(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="标签名称关键词")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(AdminTag)
    if keyword:
        query = query.filter(AdminTag.name.ilike(f"%{keyword}%"))
    if status_filter:
        query = query.filter(AdminTag.status == status_filter)
    total = query.count()
    tags = query.order_by(AdminTag.sort.asc(), AdminTag.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [tag_item(db, tag) for tag in tags], "total": total})


@router.post(
    "/tags",
    response_model=AdminResponse,
    summary="新增标签",
    description="系统配置 - 新增标签。",
)
def create_admin_tag(
    payload: AdminTagPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if db.query(AdminTag).filter(AdminTag.name == payload.name).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "标签名称已存在")
    tag = AdminTag(
        tag_id=new_business_id("tag"),
        name=payload.name,
        color=payload.color,
        sort=payload.sort,
        status=payload.status,
        remark=payload.remark,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return ok(tag_item(db, tag), "标签创建成功")


@router.get(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="标签详情",
    description="系统配置 - 查看标签详情。",
)
def get_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    return ok(tag_item(db, tag))


@router.put(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="修改标签",
    description="系统配置 - 修改标签信息。",
)
def update_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    payload: AdminTagPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    duplicate = db.query(AdminTag).filter(AdminTag.name == payload.name, AdminTag.tag_id != tagId).one_or_none()
    if duplicate is not None:
        raise fail(status.HTTP_400_BAD_REQUEST, "标签名称已存在")
    tag.name = payload.name
    tag.color = payload.color
    tag.sort = payload.sort
    tag.status = payload.status
    tag.remark = payload.remark
    tag.last_time = utc_now()
    db.commit()
    db.refresh(tag)
    return ok(tag_item(db, tag), "标签更新成功")


@router.delete(
    "/tags/{tagId}",
    response_model=AdminResponse,
    summary="删除标签",
    description="系统配置 - 删除标签。",
)
def delete_admin_tag(
    tagId: Annotated[str, Path(description="业务标签 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    tag = db.query(AdminTag).filter(AdminTag.tag_id == tagId).one_or_none()
    if tag is None:
        raise fail(status.HTTP_404_NOT_FOUND, "标签未找到")
    db.delete(tag)
    db.commit()
    return ok(None, "标签删除成功")


@router.get(
    "/regions",
    response_model=AdminResponse,
    summary="地区列表",
    description="系统配置 - 地区管理列表，支持按名称、编码、上级地区和状态筛选。",
)
def list_admin_regions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="地区名称或编码关键词")] = None,
    parentId: Annotated[str | None, Query(description="上级地区 ID")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=200, description="每页数量")] = 50,
) -> dict[str, Any]:
    query = db.query(AdminRegion)
    if keyword:
        query = query.filter((AdminRegion.name.ilike(f"%{keyword}%")) | (AdminRegion.code.ilike(f"%{keyword}%")))
    if parentId:
        query = query.filter(AdminRegion.parent_id == parentId)
    if status_filter:
        query = query.filter(AdminRegion.status == status_filter)
    total = query.count()
    regions = query.order_by(AdminRegion.level.asc(), AdminRegion.sort.asc(), AdminRegion.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [region_item(region) for region in regions], "total": total})


@router.post(
    "/regions",
    response_model=AdminResponse,
    summary="新增地区",
    description="系统配置 - 新增地区。",
)
def create_admin_region(
    payload: AdminRegionPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    if db.query(AdminRegion).filter(AdminRegion.code == payload.code).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "地区编码已存在")
    region = AdminRegion(
        region_id=new_business_id("reg"),
        parent_id=payload.parentId,
        name=payload.name,
        code=payload.code,
        level=payload.level,
        sort=payload.sort,
        status=payload.status,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return ok(region_item(region), "地区创建成功")


@router.get(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="地区详情",
    description="系统配置 - 查看地区详情。",
)
def get_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    return ok(region_item(region))


@router.put(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="修改地区",
    description="系统配置 - 修改地区信息。",
)
def update_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    payload: AdminRegionPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    duplicate = db.query(AdminRegion).filter(AdminRegion.code == payload.code, AdminRegion.region_id != regionId).one_or_none()
    if duplicate is not None:
        raise fail(status.HTTP_400_BAD_REQUEST, "地区编码已存在")
    region.parent_id = payload.parentId
    region.name = payload.name
    region.code = payload.code
    region.level = payload.level
    region.sort = payload.sort
    region.status = payload.status
    region.last_time = utc_now()
    db.commit()
    db.refresh(region)
    return ok(region_item(region), "地区更新成功")


@router.delete(
    "/regions/{regionId}",
    response_model=AdminResponse,
    summary="删除地区",
    description="系统配置 - 删除地区；存在下级地区时不允许删除。",
)
def delete_admin_region(
    regionId: Annotated[str, Path(description="业务地区 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    region = db.query(AdminRegion).filter(AdminRegion.region_id == regionId).one_or_none()
    if region is None:
        raise fail(status.HTTP_404_NOT_FOUND, "地区未找到")
    if db.query(AdminRegion).filter(AdminRegion.parent_id == regionId).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "存在下级地区，不能删除")
    db.delete(region)
    db.commit()
    return ok(None, "地区删除成功")


@router.get(
    "/dictionaries",
    response_model=AdminResponse,
    summary="字典列表",
    description="系统配置 - 字典管理列表，支持按字典类型、标签和值筛选；默认返回带 children 的完整树。",
)
def list_admin_dictionaries(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    type: Annotated[str | None, Query(description="字典类型，精确匹配")] = None,
    keyword: Annotated[str | None, Query(description="字典标签或值关键词")] = None,
    parentId: Annotated[str | None, Query(description="上级字典 ID；传入后只查询该字典的直接下级")] = None,
    tree: Annotated[bool, Query(description="是否按父子层级返回 children")] = True,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：enabled 启用，disabled 禁用")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=1000, description="每页数量")] = 1000,
) -> dict[str, Any]:
    query = db.query(AdminDictionary)
    if type:
        query = query.filter(AdminDictionary.type == type)
    if keyword:
        query = query.filter((AdminDictionary.label.ilike(f"%{keyword}%")) | (AdminDictionary.value.ilike(f"%{keyword}%")))
    if parentId is not None:
        query = query.filter(AdminDictionary.parent_id == parentId)
    if status_filter:
        query = query.filter(AdminDictionary.status == status_filter)
    total = query.count()
    dictionaries = query.order_by(AdminDictionary.type.asc(), AdminDictionary.sort.asc(), AdminDictionary.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    if tree and parentId is None:
        return ok({"list": dictionary_tree_items(dictionaries), "total": total})
    return ok({"list": [dictionary_item(dictionary) for dictionary in dictionaries], "total": total})


@router.post(
    "/dictionaries",
    response_model=AdminResponse,
    summary="新增字典",
    description="系统配置 - 新增字典项。",
)
def create_admin_dictionary(
    payload: AdminDictionaryPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    validate_dictionary_parent(db, payload.parentId, payload.type)
    validate_dictionary_unique(db, payload.type, payload.parentId, payload.label, payload.value)
    dictionary = AdminDictionary(
        dict_id=new_business_id("dict"),
        parent_id=payload.parentId,
        type=payload.type,
        label=payload.label,
        value=payload.value,
        sort=payload.sort,
        status=payload.status,
        remark=payload.remark,
    )
    db.add(dictionary)
    db.commit()
    db.refresh(dictionary)
    return ok(dictionary_item(dictionary), "字典创建成功")


@router.get(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="字典详情",
    description="系统配置 - 查看字典项详情。",
)
def get_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = get_dictionary_or_404(db, dictId)
    return ok(dictionary_item(dictionary))


@router.get(
    "/dictionaries/{dictId}/children",
    response_model=AdminResponse,
    summary="字典下级列表",
    description="系统配置 - 点击加下级时传入当前字典 ID，查询该字典详情和直接下级字典项。",
)
def list_admin_dictionary_children(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    parent = get_dictionary_or_404(db, dictId)
    children = (
        db.query(AdminDictionary)
        .filter(AdminDictionary.parent_id == dictId)
        .order_by(AdminDictionary.sort.asc(), AdminDictionary.create_time.desc())
        .all()
    )
    return ok({"parent": dictionary_item(parent), "list": [dictionary_item(child) for child in children], "total": len(children)})


@router.put(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="修改字典",
    description="系统配置 - 修改字典项。",
)
def update_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    payload: AdminDictionaryPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = get_dictionary_or_404(db, dictId)
    validate_dictionary_parent(db, payload.parentId, payload.type, self_id=dictId)
    validate_dictionary_unique(db, payload.type, payload.parentId, payload.label, payload.value, self_id=dictId)
    dictionary.parent_id = payload.parentId
    dictionary.type = payload.type
    dictionary.label = payload.label
    dictionary.value = payload.value
    dictionary.sort = payload.sort
    dictionary.status = payload.status
    dictionary.remark = payload.remark
    dictionary.last_time = utc_now()
    db.commit()
    db.refresh(dictionary)
    return ok(dictionary_item(dictionary), "字典更新成功")


@router.delete(
    "/dictionaries/{dictId}",
    response_model=AdminResponse,
    summary="删除字典",
    description="系统配置 - 删除字典项。",
)
def delete_admin_dictionary(
    dictId: Annotated[str, Path(description="业务字典 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    dictionary = get_dictionary_or_404(db, dictId)
    if db.query(AdminDictionary).filter(AdminDictionary.parent_id == dictId).one_or_none():
        raise fail(status.HTTP_400_BAD_REQUEST, "存在下级字典，不能删除")
    db.delete(dictionary)
    db.commit()
    return ok(None, "字典删除成功")


@router.get(
    "/system-messages",
    response_model=AdminResponse,
    summary="系统消息列表",
    description="系统配置 - 系统消息列表，支持按标题、类型、发送范围和状态筛选。",
)
def list_admin_system_messages(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
    keyword: Annotated[str | None, Query(description="消息标题或内容关键词")] = None,
    type: Annotated[str | None, Query(description="消息类型")] = None,
    target: Annotated[str | None, Query(description="发送范围：all/admin/user")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="状态：draft/published/disabled")] = None,
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10,
) -> dict[str, Any]:
    query = db.query(AdminSystemMessage)
    if keyword:
        query = query.filter((AdminSystemMessage.title.ilike(f"%{keyword}%")) | (AdminSystemMessage.content.ilike(f"%{keyword}%")))
    if type:
        query = query.filter(AdminSystemMessage.type == type)
    if target:
        query = query.filter(AdminSystemMessage.target == target)
    if status_filter:
        query = query.filter(AdminSystemMessage.status == status_filter)
    total = query.count()
    messages = query.order_by(AdminSystemMessage.is_pinned.desc(), AdminSystemMessage.create_time.desc()).offset((page - 1) * limit).limit(limit).all()
    return ok({"list": [system_message_item(message) for message in messages], "total": total})


@router.post(
    "/system-messages",
    response_model=AdminResponse,
    summary="新增系统消息",
    description="系统配置 - 新增系统消息。",
)
def create_admin_system_message(
    payload: AdminSystemMessagePayload,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = AdminSystemMessage(
        message_id=new_business_id("msg"),
        title=payload.title,
        content=payload.content,
        type=payload.type,
        target=payload.target,
        status=payload.status,
        is_pinned=payload.isPinned,
    )
    db.add(message)
    db.flush()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = 0
    if message.status == "published":
        pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息创建成功")


@router.get(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="系统消息详情",
    description="系统配置 - 查看系统消息详情。",
)
def get_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    return ok(system_message_item(message))


@router.put(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="修改系统消息",
    description="系统配置 - 修改系统消息。",
)
def update_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    payload: AdminSystemMessagePayload,
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    old_status = message.status
    message.title = payload.title
    message.content = payload.content
    message.type = payload.type
    message.target = payload.target
    message.status = payload.status
    message.is_pinned = payload.isPinned
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = 0
    if message.status == "published" and old_status != "published":
        pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息更新成功")


@router.put(
    "/system-messages/{messageId}/push",
    response_model=AdminResponse,
    summary="推送系统消息",
    description="系统配置 - 将草稿系统消息发布，并同步生成用户端通知消息。",
)
def push_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    message.status = "published"
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    pushed_count = publish_system_message_to_users(db, message)
    db.commit()
    db.refresh(message)
    data = system_message_item(message)
    data["pushedCount"] = pushed_count
    return ok(data, "系统消息已推送")


@router.put(
    "/system-messages/{messageId}/retract",
    response_model=AdminResponse,
    summary="撤回系统消息",
    description="系统配置 - 将已发布系统消息撤回为草稿状态。",
)
def retract_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    admin_subject: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    message.status = "draft"
    message.last_time = utc_now()
    ensure_admin_notification(db, admin_subject, message)
    db.commit()
    db.refresh(message)
    return ok(system_message_item(message), "系统消息已撤回")


@router.delete(
    "/system-messages/{messageId}",
    response_model=AdminResponse,
    summary="删除系统消息",
    description="系统配置 - 删除系统消息。",
)
def delete_admin_system_message(
    messageId: Annotated[str, Path(description="业务系统消息 ID")],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[str, Depends(get_admin_subject)],
) -> dict[str, Any]:
    message = db.query(AdminSystemMessage).filter(AdminSystemMessage.message_id == messageId).one_or_none()
    if message is None:
        raise fail(status.HTTP_404_NOT_FOUND, "系统消息未找到")
    db.delete(message)
    db.commit()
    return ok(None, "系统消息删除成功")
