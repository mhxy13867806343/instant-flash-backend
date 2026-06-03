from __future__ import annotations

import os
import hashlib
import io
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = "memory://"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


def test_index_page() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "即闪后端 API 服务" in response.text
    assert "/docs" in response.text
    assert "Authorization: Bearer" in response.text


def test_address_tree() -> None:
    client = TestClient(app)

    response = client.get("/api/address/tree")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "success"
    assert body["data"][0]["code"] == "110000"
    assert body["data"][0]["value"] == "110000"
    assert body["data"][0]["label"] == "北京市"
    assert body["data"][0]["children"][0]["children"][0]["label"] == "东城区"


def test_rate_limit() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    original_enabled = settings.rate_limit_enabled
    original_limit = settings.rate_limit_max_requests
    original_mobile_limit = settings.mobile_rate_limit_max_requests
    original_window = settings.rate_limit_window_seconds
    settings.rate_limit_enabled = True
    settings.rate_limit_max_requests = 2
    settings.mobile_rate_limit_max_requests = 10000
    settings.rate_limit_window_seconds = 60
    headers = {"x-forwarded-for": "203.0.113.10"}
    try:
        mobile_response = client.get("/api/address/tree", headers=headers)
        assert mobile_response.status_code == 200
        assert mobile_response.headers["X-RateLimit-Limit"] == "10000"

        assert client.get("/api/admin/users", headers=headers).status_code == 401
        assert client.get("/api/admin/users", headers=headers).status_code == 401
        limited = client.get("/api/admin/users", headers=headers)
        assert limited.status_code == 429
        assert limited.json()["code"] == 429
        assert limited.json()["message"].startswith("访问过于频繁")
        assert limited.json()["data"]["limit"] == 2
    finally:
        settings.rate_limit_enabled = original_enabled
        settings.rate_limit_max_requests = original_limit
        settings.mobile_rate_limit_max_requests = original_mobile_limit
        settings.rate_limit_window_seconds = original_window


def test_content_flow() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_test", "nickname": "Tester"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/posts",
        json={"content": "hello", "images": ["https://example.com/a.png"]},
        headers=headers,
    )
    assert create_response.status_code == 201
    post_id = create_response.json()["postId"]

    public_detail = client.get(f"/api/posts/{post_id}")
    assert public_detail.status_code == 200
    assert public_detail.json()["isLiked"] is False
    assert public_detail.json()["isOwner"] is False

    liked = client.post(f"/api/posts/{post_id}/like", headers=headers)
    assert liked.status_code == 200
    assert liked.json()["isLiked"] is True
    assert liked.json()["likeCount"] == 1

    private_detail = client.get(f"/api/posts/{post_id}", headers=headers)
    assert private_detail.status_code == 200
    assert private_detail.json()["isLiked"] is True
    assert private_detail.json()["isOwner"] is True
    assert private_detail.json()["canEdit"] is True

    comment = client.post(
        f"/api/posts/{post_id}/comments",
        json={"content": "nice"},
        headers=headers,
    )
    assert comment.status_code == 201
    assert comment.json()["userId"] == "usr_test"

    mine = client.get("/api/user/posts", headers=headers)
    assert mine.status_code == 200
    assert mine.json()["total"] == 1

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json() == {"code": 200, "message": "退出成功", "data": {}}
    after_logout_profile = client.get("/api/user/profile", headers=headers)
    assert after_logout_profile.status_code == 401

    comments = client.get(f"/api/posts/{post_id}/comments?page=1&pageSize=10")
    assert comments.status_code == 200
    assert comments.json()[0]["commentId"] == comment.json()["commentId"]

    anonymous_share = client.post(f"/api/posts/{post_id}/share", json={"platform": "h5"})
    assert anonymous_share.status_code == 201
    assert anonymous_share.json()["userId"] == ""


def test_admin_flow() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_admin_target", "nickname": "Target", "phone": "13812345678"},
    )
    user_token = token_response.json()["accessToken"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    post_response = client.post("/api/posts", json={"content": "admin visible"}, headers=user_headers)
    post_id = post_response.json()["postId"]
    comment_response = client.post(
        f"/api/posts/{post_id}/comments",
        json={"content": "review me"},
        headers=user_headers,
    )

    login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    assert login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}

    traffic_trends = client.get("/api/admin/dashboard/trends", params={"type": "traffic_content", "period": "today"}, headers=admin_headers)
    assert traffic_trends.status_code == 200
    traffic_data = traffic_trends.json()["data"]
    assert traffic_data["type"] == "traffic_content"
    assert traffic_data["period"] == "today"
    assert traffic_data["series"][0]["key"] == "visits"
    assert traffic_data["series"][1]["key"] == "posts"
    assert traffic_data["summary"]["posts"] >= 1
    assert len(traffic_data["labels"]) == len(traffic_data["visits"]) == len(traffic_data["posts"])

    user_growth_trends = client.get("/api/admin/dashboard/trends", params={"type": "user_growth", "period": "week"}, headers=admin_headers)
    assert user_growth_trends.status_code == 200
    user_growth_data = user_growth_trends.json()["data"]
    assert user_growth_data["series"][0]["key"] == "activeUsers"
    assert user_growth_data["series"][1]["key"] == "newUsers"
    assert user_growth_data["summary"]["newUsers"] >= 1

    month_trends = client.get("/api/admin/dashboard/trends", params={"period": "month"}, headers=admin_headers)
    assert month_trends.status_code == 200
    assert month_trends.json()["data"]["labels"]

    users = client.get("/api/admin/users", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["data"]["total"] == 1
    assert users.json()["data"]["list"][0]["status"] == "normal"
    assert users.json()["data"]["list"][0]["userId"] == "usr_admin_target"
    assert "user_id" not in users.json()["data"]["list"][0]
    export_xls = client.get("/api/admin/users/export", params={"format": "xls"}, headers=admin_headers)
    assert export_xls.status_code == 200
    assert export_xls.headers["content-type"].startswith("application/vnd.ms-excel")
    assert export_xls.content.startswith(b"\xd0\xcf")
    export_xlsx = client.get("/api/admin/users/export", params={"format": "xlsx"}, headers=admin_headers)
    assert export_xlsx.status_code == 200
    assert export_xlsx.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert export_xlsx.content.startswith(b"PK")
    generic_export = client.get("/api/admin/export", headers=admin_headers)
    assert generic_export.status_code == 200
    assert generic_export.headers["content-type"].startswith("application/vnd.ms-excel")
    assert generic_export.content.startswith(b"\xd0\xcf")
    bad_import = client.post(
        "/api/admin/users/import",
        files={"file": ("users.txt", b"bad file", "text/plain")},
        headers=admin_headers,
    )
    assert bad_import.status_code == 400
    assert bad_import.json()["message"] == "导入文件格式不正确，仅支持 .xls 或 .xlsx"

    import xlwt

    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("用户导入")
    for column, header in enumerate(["用户ID", "昵称", "手机号", "账号状态", "省份", "城市"]):
        sheet.write(0, column, header)
    for column, value in enumerate(["usr_import_xls", "导入用户", "13900000000", "禁用", "浙江", "杭州"]):
        sheet.write(1, column, value)
    import_file = io.BytesIO()
    workbook.save(import_file)
    import_file.seek(0)
    import_xls = client.post(
        "/api/admin/users/import",
        files={"file": ("users.xls", import_file.read(), "application/vnd.ms-excel")},
        headers=admin_headers,
    )
    assert import_xls.status_code == 200
    assert import_xls.json()["data"]["created"] == 1
    imported_user = client.get("/api/admin/users/usr_import_xls", headers=admin_headers)
    assert imported_user.status_code == 200
    assert imported_user.json()["data"]["nickname"] == "导入用户"
    assert imported_user.json()["data"]["status"] == "banned"

    generic_workbook = xlwt.Workbook()
    generic_sheet = generic_workbook.add_sheet("用户导入")
    for column, header in enumerate(["用户ID", "昵称", "手机号", "账号状态"]):
        generic_sheet.write(0, column, header)
    for column, value in enumerate(["usr_import_generic", "通用导入用户", "13900000001", "正常"]):
        generic_sheet.write(1, column, value)
    generic_import_file = io.BytesIO()
    generic_workbook.save(generic_import_file)
    generic_import_file.seek(0)
    generic_import = client.post(
        "/api/admin/import",
        files={"file": ("users.xls", generic_import_file.read(), "application/vnd.ms-excel")},
        headers=admin_headers,
    )
    assert generic_import.status_code == 200
    assert generic_import.json()["data"]["created"] == 1

    user_export = client.get("/api/user/export", headers=user_headers)
    assert user_export.status_code == 200
    assert user_export.headers["content-type"].startswith("application/vnd.ms-excel")
    assert user_export.content.startswith(b"\xd0\xcf")
    profile_workbook = xlwt.Workbook()
    profile_sheet = profile_workbook.add_sheet("资料导入")
    for column, header in enumerate(["昵称", "手机号", "个性签名", "省份", "城市"]):
        profile_sheet.write(0, column, header)
    for column, value in enumerate(["用户端导入名", "13812345679", "导入签名", "浙江", "宁波"]):
        profile_sheet.write(1, column, value)
    profile_file = io.BytesIO()
    profile_workbook.save(profile_file)
    profile_file.seek(0)
    profile_import = client.post(
        "/api/user/import",
        files={"file": ("profile.xls", profile_file.read(), "application/vnd.ms-excel")},
        headers=user_headers,
    )
    assert profile_import.status_code == 200
    assert profile_import.json()["data"]["nickname"] == "用户端导入名"
    assert profile_import.json()["data"]["bio"] == "导入签名"
    assert profile_import.json()["data"]["signature"] == "导入签名"
    profile_update = client.put(
        "/api/user/profile",
        json={"nickname": "编辑资料用户", "gender": "保密", "signature": "记录生活灵感"},
        headers=user_headers,
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["bio"] == "记录生活灵感"
    assert profile_update.json()["signature"] == "记录生活灵感"
    avatar_upload = client.post(
        "/api/user/profile/avatar",
        files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\navatar", "image/png")},
        headers=user_headers,
    )
    assert avatar_upload.status_code == 200
    assert avatar_upload.json()["data"]["avatar"].startswith("/static/uploads/avatars/usr_admin_target/")
    assert avatar_upload.json()["data"]["profile"]["avatar"] == avatar_upload.json()["data"]["avatar"]

    banned = client.put(
        "/api/admin/users/usr_admin_target",
        json={"status": "banned"},
        headers=admin_headers,
    )
    assert banned.status_code == 200
    expired_profile = client.get("/api/user/profile", headers=user_headers)
    assert expired_profile.status_code == 401
    assert expired_profile.json() == {"code": 401, "message": "登录已过期或无效", "data": {}}

    offline = client.put(f"/api/admin/posts/{post_id}/offline", headers=admin_headers)
    assert offline.status_code == 200
    missing = client.get(f"/api/posts/{post_id}")
    assert missing.status_code == 404
    assert missing.json() == {"code": 404, "message": "内容未找到", "data": {}}

    admin_post = client.get(f"/api/admin/posts/{post_id}", headers=admin_headers)
    assert admin_post.status_code == 200
    assert admin_post.json()["data"]["status"] == "offline"
    assert admin_post.json()["data"]["postId"] == post_id
    assert "post_id" not in admin_post.json()["data"]

    admin_operation_logs = client.get("/api/admin/logs", params={"category": "admin_operation"}, headers=admin_headers)
    assert admin_operation_logs.status_code == 200
    assert admin_operation_logs.json()["data"]["total"] >= 1
    assert any("后台" in item["content"] for item in admin_operation_logs.json()["data"]["list"])
    user_operation_logs = client.get("/api/admin/logs", params={"category": "user_operation"}, headers=admin_headers)
    assert user_operation_logs.status_code == 200
    assert user_operation_logs.json()["data"]["total"] >= 1
    assert any(item["username"] == "Target" for item in user_operation_logs.json()["data"]["list"])

    deleted_comment = client.delete(
        f"/api/admin/comments/{comment_response.json()['commentId']}",
        headers=admin_headers,
    )
    assert deleted_comment.status_code == 200

    agreement = client.put(
        "/api/admin/agreement/privacy",
        json={"content": "<p>privacy</p>"},
        headers=admin_headers,
    )
    assert agreement.status_code == 200
    assert client.get("/api/admin/agreement/privacy", headers=admin_headers).json()["data"] == "<p>privacy</p>"

    filtered = client.get("/api/admin/posts", params={"userId": "usr_admin_target"}, headers=admin_headers)
    assert filtered.status_code == 200
    assert filtered.json()["data"]["list"][0]["userId"] == "usr_admin_target"


def test_post_feed_tabs_search_and_location() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_feed", "nickname": "杭州用户"},
    )
    headers = {"Authorization": f"Bearer {token_response.json()['accessToken']}"}

    popular = client.post(
        "/api/posts",
        json={
            "content": "推荐内容",
            "images": [],
            "location": "杭州·西湖",
            "province": "浙江省",
            "city": "杭州市",
            "district": "西湖区",
        },
        headers=headers,
    )
    latest = client.post(
        "/api/posts",
        json={"content": "最新内容", "images": [], "location": "上海·静安寺", "city": "上海市"},
        headers=headers,
    )
    assert popular.status_code == 201
    assert latest.status_code == 201

    assert client.post(f"/api/posts/{popular.json()['postId']}/like", headers=headers).status_code == 200

    latest_list = client.get("/api/posts", params={"tab": "latest", "limit": 2})
    assert latest_list.status_code == 200
    assert latest_list.json()["items"][0]["postId"] == latest.json()["postId"]

    recommend_list = client.get("/api/posts", params={"tab": "recommend", "limit": 2})
    assert recommend_list.status_code == 200
    assert recommend_list.json()["items"][0]["postId"] == popular.json()["postId"]

    search_list = client.get("/api/posts", params={"keyword": "西湖", "tab": "recommend"})
    assert search_list.status_code == 200
    assert search_list.json()["total"] == 1
    assert search_list.json()["items"][0]["location"] == "杭州·西湖"


def test_admin_like_share_lists_and_routes() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_like_share", "nickname": "互动用户"},
    )
    user_headers = {"Authorization": f"Bearer {token_response.json()['accessToken']}"}
    post_response = client.post("/api/posts", json={"content": "互动验证内容", "images": []}, headers=user_headers)
    post_id = post_response.json()["postId"]
    assert client.post(f"/api/posts/{post_id}/like", headers=user_headers).status_code == 200
    assert client.post(f"/api/posts/{post_id}/share", json={"scene": "timeline", "platform": "wechat"}, headers=user_headers).status_code == 201

    admin_login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['token']}"}

    routes = client.get("/api/admin/menus/routes", headers=admin_headers)
    route_names = {item["name"] for item in routes.json()["data"]["flatList"]}
    assert {"LikeList", "ShareList"} <= route_names
    assert "like" in routes.json()["data"]["permissions"]
    assert "share" in routes.json()["data"]["permissions"]

    likes = client.get("/api/admin/likes", params={"postId": post_id, "keyword": "互动"}, headers=admin_headers)
    assert likes.status_code == 200
    assert likes.json()["data"]["total"] == 1
    assert likes.json()["data"]["list"][0]["userId"] == "usr_like_share"

    shares = client.get("/api/admin/shares", params={"postId": post_id, "platform": "wechat"}, headers=admin_headers)
    assert shares.status_code == 200
    assert shares.json()["data"]["total"] == 1
    assert shares.json()["data"]["list"][0]["scene"] == "timeline"


def test_auth_errors_are_unified() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    user_missing = client.get("/api/user/profile")
    assert user_missing.status_code == 401
    assert user_missing.json() == {"code": 401, "message": "未登录，请先登录", "data": {}}
    assert "detail" not in user_missing.json()

    admin_missing = client.get("/api/admin/users")
    assert admin_missing.status_code == 401
    assert admin_missing.json() == {"code": 401, "message": "未登录，请先登录", "data": {}}
    assert "detail" not in admin_missing.json()

    invalid_token = client.get("/api/user/profile", headers={"Authorization": "Bearer wrong"})
    assert invalid_token.status_code == 401
    assert invalid_token.json() == {"code": 401, "message": "登录已过期或无效", "data": {}}


def test_admin_system_config_flow() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    logout_login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    logout_headers = {"Authorization": f"Bearer {logout_login.json()['data']['token']}"}
    assert client.post("/api/admin/auth/logout", headers=logout_headers).json() == {"code": 200, "message": "退出成功", "data": {}}
    after_logout_admin = client.get("/api/admin/accounts", headers=logout_headers)
    assert after_logout_admin.status_code == 401

    menu_tree = client.get("/api/admin/menus", headers=headers)
    assert menu_tree.status_code == 200
    assert menu_tree.json()["data"]["total"] >= 18
    assert menu_tree.json()["data"]["list"][0]["menuId"] == "menu_dashboard"
    menu_routes = client.get("/api/admin/menus/routes", headers=headers)
    assert menu_routes.status_code == 200
    assert any(item["name"] == "Dashboard" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "MenuList" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "AccountProfile" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "AccountSettings" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "LogList" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "VersionPackageUpload" for item in menu_routes.json()["data"]["flatList"])
    assert any(item["name"] == "AccessRuleList" for item in menu_routes.json()["data"]["flatList"])
    assert next(item for item in menu_routes.json()["data"]["flatList"] if item["name"] == "LogList")["path"] == "log/list"

    security_overview = client.get("/api/admin/security/overview", headers=headers)
    assert security_overview.status_code == 200
    assert security_overview.json()["data"]["levelKey"] in {"low", "medium", "high"}
    assert security_overview.json()["data"]["recentLoginLogs"]
    security_settings = client.put(
        "/api/admin/security/settings",
        json={"mfaEnabled": True, "passwordPolicyEnabled": True, "remark": "测试安全设置"},
        headers=headers,
    )
    assert security_settings.status_code == 200
    assert security_settings.json()["data"]["mfaEnabled"] is True
    profile = client.get("/api/admin/account/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["data"]["username"] == "admin"
    profile_update = client.put(
        "/api/admin/account/profile",
        json={"nickname": "超级管理员测试", "email": "admin-test@example.com", "phone": "13800000000"},
        headers=headers,
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["data"]["nickname"] == "超级管理员测试"
    failed_login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "bad-password"})
    assert failed_login.status_code == 400
    login_logs = client.get("/api/admin/security/login-logs", headers=headers)
    assert login_logs.status_code == 200
    assert login_logs.json()["data"]["total"] >= 1
    access_rule_empty = client.get("/api/admin/access-rules", headers=headers)
    assert access_rule_empty.status_code == 200
    access_rule_create = client.post(
        "/api/admin/access-rules",
        json={
            "type": "whitelist",
            "ip": "127.0.0.1",
            "method": "GET",
            "path": "/api/admin/security/*",
            "status": "enabled",
            "remark": "测试白名单",
        },
        headers=headers,
    )
    assert access_rule_create.status_code == 200
    access_rule_id = access_rule_create.json()["data"]["ruleId"]
    assert access_rule_create.json()["data"]["typeText"] == "白名单"
    assert client.get(f"/api/admin/access-rules/{access_rule_id}", headers=headers).json()["data"]["ip"] == "127.0.0.1"
    access_rule_update = client.put(
        f"/api/admin/access-rules/{access_rule_id}",
        json={
            "type": "blacklist",
            "ip": "192.168.*",
            "method": "ALL",
            "path": "/api/posts/*",
            "status": "disabled",
            "remark": "测试黑名单",
        },
        headers=headers,
    )
    assert access_rule_update.status_code == 200
    assert access_rule_update.json()["data"]["type"] == "blacklist"
    assert access_rule_update.json()["data"]["status"] == "disabled"
    access_rule_list = client.get("/api/admin/access-rules", params={"keyword": "192.168", "type": "blacklist"}, headers=headers)
    assert access_rule_list.status_code == 200
    assert access_rule_list.json()["data"]["total"] == 1
    assert client.delete(f"/api/admin/access-rules/{access_rule_id}", headers=headers).status_code == 200
    warning_logs = client.get("/api/admin/logs", params={"category": "login", "status": "warning"}, headers=headers)
    assert warning_logs.status_code == 200
    assert warning_logs.json()["data"]["total"] >= 1
    warning_log_id = warning_logs.json()["data"]["list"][0]["logId"]
    log_detail = client.get(f"/api/admin/logs/{warning_log_id}", headers=headers)
    assert log_detail.status_code == 200
    assert log_detail.json()["data"]["status"] == "warning"
    assert client.delete(f"/api/admin/logs/{warning_log_id}", headers=headers).status_code == 200

    viewer = client.post(
        "/api/admin/accounts",
        json={
            "username": "viewer_menu",
            "nickname": "菜单观察员",
            "avatar": "",
            "role": "viewer",
            "permissions": ["dashboard"],
            "status": "active",
            "email": "viewer-menu@example.com",
            "phone": "13800000002",
            "remark": "只看数据看板",
        },
        headers=headers,
    )
    viewer_token = client.post("/api/admin/auth/login", json={"username": "viewer_menu", "password": "123456"}).json()["data"]["token"]
    viewer_routes = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {viewer_token}"})
    viewer_names = [item["name"] for item in viewer_routes.json()["data"]["flatList"]]
    assert viewer_names == ["Dashboard"]
    assert client.delete(f"/api/admin/accounts/{viewer.json()['data']['account_id']}", headers=headers).status_code == 200
    route_admin = client.post(
        "/api/admin/accounts",
        json={
            "username": "route_admin",
            "nickname": "路由管理员",
            "avatar": "",
            "role": "admin",
            "permissions": ["dashboard", "account", "log"],
            "status": "active",
            "email": "route-admin@example.com",
            "phone": "13800000005",
            "remark": "验证管理员动态路由",
        },
        headers=headers,
    )
    route_admin_token = client.post("/api/admin/auth/login", json={"username": "route_admin", "password": "123456"}).json()["data"]["token"]
    route_admin_routes = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {route_admin_token}"})
    route_admin_names = [item["name"] for item in route_admin_routes.json()["data"]["flatList"]]
    assert {"Dashboard", "AccountProfile", "AccountSettings", "LogList"} <= set(route_admin_names)
    assert client.delete(f"/api/admin/accounts/{route_admin.json()['data']['account_id']}", headers=headers).status_code == 200
    route_operator = client.post(
        "/api/admin/accounts",
        json={
            "username": "route_operator",
            "nickname": "路由运营员",
            "avatar": "",
            "role": "operator",
            "permissions": ["dashboard", "log"],
            "status": "active",
            "email": "route-operator@example.com",
            "phone": "13800000006",
            "remark": "验证运营员不能拿管理员路由",
        },
        headers=headers,
    )
    route_operator_token = client.post("/api/admin/auth/login", json={"username": "route_operator", "password": "123456"}).json()["data"]["token"]
    route_operator_routes = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {route_operator_token}"})
    route_operator_names = [item["name"] for item in route_operator_routes.json()["data"]["flatList"]]
    assert "LogList" not in route_operator_names
    assert "AccountSettings" not in route_operator_names
    assert client.delete(f"/api/admin/accounts/{route_operator.json()['data']['account_id']}", headers=headers).status_code == 200
    agreement_viewer = client.post(
        "/api/admin/accounts",
        json={
            "username": "agreement_viewer",
            "nickname": "协议观察员",
            "avatar": "",
            "role": "viewer",
            "permissions": ["dashboard", "agreement"],
            "status": "active",
            "email": "agreement-viewer@example.com",
            "phone": "13800000003",
            "remark": "看数据看板和协议",
        },
        headers=headers,
    )
    agreement_token = client.post("/api/admin/auth/login", json={"username": "agreement_viewer", "password": "123456"}).json()["data"]["token"]
    agreement_routes = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {agreement_token}"})
    agreement_names = [item["name"] for item in agreement_routes.json()["data"]["flatList"]]
    assert agreement_names == ["Dashboard", "SystemConfig", "PrivacyAgreement", "UserAgreement"]
    assert "Announcement" not in agreement_names
    assert client.delete(f"/api/admin/accounts/{agreement_viewer.json()['data']['account_id']}", headers=headers).status_code == 200
    menu = client.post(
        "/api/admin/menus",
        json={
            "parentId": "menu_system",
            "title": "测试菜单",
            "path": "/test-menu",
            "name": "TestMenu",
            "component": "views/test/Menu",
            "icon": "Memo",
            "type": "menu",
            "permission": "dashboard",
            "sort": 99,
            "status": "enabled",
            "visible": True,
            "keepAlive": False,
            "affix": False,
        },
        headers=headers,
    )
    assert menu.status_code == 200
    menu_id = menu.json()["data"]["menuId"]
    assert client.get(f"/api/admin/menus/{menu_id}", headers=headers).json()["data"]["name"] == "TestMenu"
    assert client.put(
        f"/api/admin/menus/{menu_id}",
        json={**menu.json()["data"], "title": "测试菜单2"},
        headers=headers,
    ).json()["data"]["title"] == "测试菜单2"
    assert client.delete(f"/api/admin/menus/{menu_id}", headers=headers).status_code == 200

    permission_list = client.get("/api/admin/permissions", params={"onlyActive": True}, headers=headers)
    assert permission_list.status_code == 200
    assert permission_list.json()["data"]["total"] >= 15
    assert {item["permissionKey"] for item in permission_list.json()["data"]["list"]} >= {"dashboard", "system", "agreement"}
    default_dashboard_permission = next(item for item in permission_list.json()["data"]["list"] if item["permissionKey"] == "dashboard")
    default_permission_delete = client.delete(f"/api/admin/permissions/{default_dashboard_permission['permissionId']}", headers=headers)
    assert default_permission_delete.status_code == 400
    assert default_permission_delete.json()["message"] == "系统默认权限不能删除"
    custom_permission = client.post(
        "/api/admin/permissions",
        json={
            "permissionKey": "audit_panel",
            "label": "审计面板",
            "description": "测试动态权限",
            "sort": 300,
            "status": "enabled",
            "remark": "测试权限",
        },
        headers=headers,
    )
    assert custom_permission.status_code == 200
    custom_permission_id = custom_permission.json()["data"]["permissionId"]
    assert client.get(f"/api/admin/permissions/{custom_permission_id}", headers=headers).json()["data"]["permissionKey"] == "audit_panel"
    assert client.put(
        f"/api/admin/permissions/{custom_permission_id}",
        json={
            "permissionKey": "audit_panel",
            "label": "审计面板2",
            "description": "测试动态权限更新",
            "sort": 301,
            "status": "enabled",
            "remark": "测试权限更新",
        },
        headers=headers,
    ).json()["data"]["label"] == "审计面板2"
    audit_menu = client.post(
        "/api/admin/menus",
        json={
            "title": "审计面板",
            "path": "/audit-panel",
            "name": "AuditPanel",
            "component": "views/audit/Panel",
            "icon": "View",
            "type": "menu",
            "permission": "audit_panel",
            "sort": 300,
            "status": "enabled",
            "visible": True,
            "keepAlive": False,
            "affix": False,
        },
        headers=headers,
    )
    assert audit_menu.status_code == 200
    audit_menu_id = audit_menu.json()["data"]["menuId"]
    audit_account = client.post(
        "/api/admin/accounts",
        json={
            "username": "audit_panel_user",
            "nickname": "审计面板用户",
            "avatar": "",
            "role": "viewer",
            "permissions": ["dashboard", "audit_panel"],
            "status": "active",
            "email": "audit-panel@example.com",
            "phone": "13800000005",
            "remark": "测试权限显示隐藏",
        },
        headers=headers,
    )
    audit_token = client.post("/api/admin/auth/login", json={"username": "audit_panel_user", "password": "123456"}).json()["data"]["token"]
    audit_routes = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {audit_token}"})
    assert any(item["name"] == "AuditPanel" for item in audit_routes.json()["data"]["flatList"])
    assert client.put(f"/api/admin/accounts/{audit_account.json()['data']['accountId']}", json={"permissions": ["dashboard"]}, headers=headers).status_code == 200
    audit_routes_after = client.get("/api/admin/menus/routes", headers={"Authorization": f"Bearer {audit_token}"})
    assert all(item["name"] != "AuditPanel" for item in audit_routes_after.json()["data"]["flatList"])
    assert client.delete(f"/api/admin/accounts/{audit_account.json()['data']['accountId']}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/menus/{audit_menu_id}", headers=headers).status_code == 200

    roles = client.get("/api/admin/roles", headers=headers)
    assert roles.status_code == 200
    assert roles.json()["data"]["total"] >= 4
    assert {item["roleKey"] for item in roles.json()["data"]["list"]} >= {"superadmin", "admin", "operator", "viewer"}
    assert [item["roleKey"] for item in roles.json()["data"]["list"][:4]] == ["superadmin", "admin", "operator", "viewer"]
    assert all(item["isDefault"] is True for item in roles.json()["data"]["list"][:4])
    default_viewer = next(item for item in roles.json()["data"]["list"] if item["roleKey"] == "viewer")
    default_delete = client.delete(f"/api/admin/roles/{default_viewer['roleId']}", headers=headers)
    assert default_delete.status_code == 400
    assert default_delete.json()["message"] == "系统默认角色不能删除"
    custom_role = client.post(
        "/api/admin/roles",
        json={
            "roleKey": "auditor_test",
            "label": "审计员",
            "icon": "View",
            "permissions": ["dashboard"],
            "sort": 50,
            "status": "enabled",
            "remark": "测试角色",
        },
        headers=headers,
    )
    assert custom_role.status_code == 200
    custom_role_id = custom_role.json()["data"]["roleId"]
    role_detail = client.get(f"/api/admin/roles/{custom_role_id}", headers=headers)
    assert role_detail.status_code == 200
    assert role_detail.json()["data"]["roleKey"] == "auditor_test"
    role_update = client.put(
        f"/api/admin/roles/{custom_role_id}",
        json={
            "roleKey": "auditor_test",
            "label": "审计员2",
            "icon": "View",
            "permissions": ["dashboard", "agreement"],
            "sort": 51,
            "status": "enabled",
            "remark": "测试角色更新",
        },
        headers=headers,
    )
    assert role_update.status_code == 200
    assert role_update.json()["data"]["label"] == "审计员2"
    role_limit_2 = client.post(
        "/api/admin/roles",
        json={
            "roleKey": "custom_role_2",
            "label": "自定义角色2",
            "icon": "User",
            "permissions": ["dashboard"],
            "sort": 52,
            "status": "enabled",
            "remark": "测试角色上限",
        },
        headers=headers,
    )
    assert role_limit_2.status_code == 200
    role_limit_3 = client.post(
        "/api/admin/roles",
        json={
            "roleKey": "custom_role_3",
            "label": "自定义角色3",
            "icon": "User",
            "permissions": ["dashboard"],
            "sort": 53,
            "status": "enabled",
            "remark": "测试角色上限",
        },
        headers=headers,
    )
    assert role_limit_3.status_code == 200
    role_limit_4 = client.post(
        "/api/admin/roles",
        json={
            "roleKey": "custom_role_4",
            "label": "自定义角色4",
            "icon": "User",
            "permissions": ["dashboard"],
            "sort": 54,
            "status": "enabled",
            "remark": "测试角色上限",
        },
        headers=headers,
    )
    assert role_limit_4.status_code == 400
    assert role_limit_4.json()["message"] == "自定义角色最多只能新增 3 个"

    tag = client.post(
        "/api/admin/tags",
        json={"name": "推荐", "color": "#1677ff", "sort": 1, "status": "enabled", "remark": "首页推荐"},
        headers=headers,
    )
    assert tag.status_code == 200
    tag_id = tag.json()["data"]["tagId"]
    assert "tag_id" not in tag.json()["data"]
    assert client.get("/api/admin/tags", headers=headers).json()["data"]["total"] == 1
    tag_update = client.put(
        f"/api/admin/tags/{tag_id}",
        json={"name": "热门", "color": "#ff4d4f", "sort": 2, "status": "enabled", "remark": "热门内容"},
        headers=headers,
    )
    assert tag_update.status_code == 200
    assert tag_update.json()["data"]["name"] == "热门"
    user_token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_tag_stats", "nickname": "Tag Stats"},
    )
    user_headers = {"Authorization": f"Bearer {user_token_response.json()['accessToken']}"}
    post_with_tag = client.post(
        "/api/posts",
        json={"content": "#热门 这里有诈骗套路提醒", "images": []},
        headers=user_headers,
    )
    assert post_with_tag.status_code == 201
    tag_list = client.get("/api/admin/tags", headers=headers)
    assert tag_list.json()["data"]["list"][0]["postCount"] == 1
    assert tag_list.json()["data"]["list"][0]["associatedPostCount"] == 1
    assert tag_list.json()["data"]["list"][0]["scamCount"] == 1
    assert tag_list.json()["data"]["list"][0]["searchCount"] >= 1200
    tag_detail = client.get(f"/api/admin/tags/{tag_id}", headers=headers)
    assert tag_detail.json()["data"]["linkedPostCount"] == 1

    announcements_empty = client.get("/api/admin/announcements", params={"keyword": "", "page": 1, "limit": 9999}, headers=headers)
    assert announcements_empty.status_code == 200
    assert announcements_empty.json()["data"]["total"] >= 1
    announcement = client.post(
        "/api/admin/announcements",
        json={
            "title": "测试公告",
            "type": "info",
            "content": "<p>公告内容</p>",
            "link": "",
            "pinned": False,
            "startTime": "2026-06-01 10:00:00",
            "endTime": "",
            "status": "inactive",
        },
        headers=headers,
    )
    assert announcement.status_code == 200
    announcement_id = announcement.json()["data"]["id"]
    assert client.put("/api/admin/announcements/batch-publish", json={"ids": [announcement_id]}, headers=headers).status_code == 200
    assert client.put(f"/api/admin/announcements/{announcement_id}", json={"status": "inactive"}, headers=headers).json()["data"]["status"] == "inactive"
    single_banner = client.get("/api/admin/announcements/SINGLE_BANNER", headers=headers)
    assert single_banner.status_code == 200
    assert single_banner.json()["data"]["id"] == "SINGLE_BANNER"
    single_banner_update = client.put(
        "/api/admin/announcements/SINGLE_BANNER",
        json={"title": "首页单公告", "content": "<p>首页公告内容</p>", "pinned": True, "status": "active"},
        headers=headers,
    )
    assert single_banner_update.status_code == 200
    assert single_banner_update.json()["data"]["title"] == "首页单公告"

    versions_empty = client.get("/api/admin/versions", params={"page": 1, "limit": 9999}, headers=headers)
    assert versions_empty.status_code == 200
    assert versions_empty.json()["data"]["total"] >= 1
    packages_empty = client.get("/api/admin/packages", headers=headers)
    assert packages_empty.status_code == 200
    assert packages_empty.json()["data"]["platform"] == "Android"
    assert packages_empty.json()["data"]["total"] == 0
    package_bytes = b"instant flash android package"
    package_upload = client.post(
        "/api/admin/packages/upload",
        data={"platform": "Android", "version": "2.0.0", "build": "200", "displayName": "即闪 Android 安装包.apk", "remark": "测试包"},
        files={"file": ("instant-flash.apk", package_bytes, "application/vnd.android.package-archive")},
        headers=headers,
    )
    assert package_upload.status_code == 200
    package_data = package_upload.json()["data"]
    package_id = package_data["packageId"]
    assert package_data["md5"] == hashlib.md5(package_bytes).hexdigest()
    assert package_data["sizeBytes"] == len(package_bytes)
    assert package_data["fileName"] == "instant-flash.apk"
    assert package_data["displayName"] == "即闪 Android 安装包.apk"
    assert package_data["downloadUrl"].startswith("/static/uploads/packages/android/")
    package_list = client.get("/api/admin/packages", params={"platform": "Android"}, headers=headers)
    assert package_list.json()["data"]["total"] == 1
    assert package_list.json()["data"]["latest"]["packageId"] == package_id
    assert package_list.json()["data"]["versions"][0]["version"] == "2.0.0"
    package_history = client.get("/api/admin/packages/history", params={"platform": "Android", "version": "2.0.0"}, headers=headers)
    assert package_history.status_code == 200
    assert package_history.json()["data"]["total"] == 1
    package_detail = client.get(f"/api/admin/packages/{package_id}", headers=headers)
    assert package_detail.json()["data"]["packageId"] == package_id
    package_update = client.put(
        f"/api/admin/packages/{package_id}",
        json={"displayName": "改名后的安卓包.apk", "version": "2.0.1", "build": "201", "status": "active", "remark": "已改名"},
        headers=headers,
    )
    assert package_update.status_code == 200
    assert package_update.json()["data"]["displayName"] == "改名后的安卓包.apk"
    assert package_update.json()["data"]["version"] == "2.0.1"
    Path(package_data["filePath"]).unlink(missing_ok=True)
    version = client.post(
        "/api/admin/versions",
        json={
            "platform": "iOS",
            "version": "1.2.3",
            "build": "123",
            "forceUpdate": False,
            "status": "beta",
            "betaPct": 20,
            "notes": "测试版本",
            "notesType": "text",
            "downloadUrl": "",
        },
        headers=headers,
    )
    assert version.status_code == 200
    version_id = version.json()["data"]["id"]
    assert client.put(f"/api/admin/versions/{version_id}/deprecate", headers=headers).json()["data"]["status"] == "deprecated"
    assert client.put("/api/admin/versions/batch-deprecate", json={"ids": [version_id]}, headers=headers).status_code == 200

    accounts = client.get("/api/admin/accounts", headers=headers)
    assert accounts.status_code == 200
    assert isinstance(accounts.json()["data"], list)
    account = client.post(
        "/api/admin/accounts",
        json={
            "username": "operator_test",
            "nickname": "运营测试",
            "avatar": "",
            "role": "operator",
            "permissions": ["dashboard", "content"],
            "status": "active",
            "email": "operator@example.com",
            "phone": "13800000001",
            "remark": "测试账号",
        },
        headers=headers,
    )
    assert account.status_code == 200
    account_id = account.json()["data"]["account_id"]
    assert account.json()["data"]["accountId"] == account_id
    account_detail = client.get(f"/api/admin/accounts/{account_id}", headers=headers)
    assert account_detail.status_code == 200
    assert account_detail.json()["data"]["accountId"] == account_id
    account_keyword_empty = client.get("/api/admin/accounts", params={"keyword": "1111"}, headers=headers)
    assert account_keyword_empty.status_code == 200
    assert account_keyword_empty.json()["data"] == []
    account_keyword_match = client.get("/api/admin/accounts", params={"keyword": "operator"}, headers=headers)
    assert account_keyword_match.status_code == 200
    assert account_keyword_match.json()["data"][0]["accountId"] == account_id
    account_role_match = client.get("/api/admin/accounts", params={"role": "operator", "status": "active"}, headers=headers)
    assert account_role_match.status_code == 200
    assert any(item["accountId"] == account_id for item in account_role_match.json()["data"])
    custom_account = client.post(
        "/api/admin/accounts",
        json={
            "username": "auditor_account",
            "nickname": "审计账号",
            "avatar": "",
            "role": "auditor_test",
            "permissions": ["dashboard"],
            "status": "active",
            "email": "auditor@example.com",
            "phone": "13800000004",
            "remark": "使用自定义角色",
        },
        headers=headers,
    )
    assert custom_account.status_code == 200
    custom_account_id = custom_account.json()["data"]["accountId"]
    in_use_delete = client.delete(f"/api/admin/roles/{custom_role_id}", headers=headers)
    assert in_use_delete.status_code == 400
    assert in_use_delete.json()["message"] == "存在账号正在使用该角色，不能删除"
    assert client.delete(f"/api/admin/accounts/{custom_account_id}", headers=headers).status_code == 200
    account_login = client.post("/api/admin/auth/login", json={"username": "operator_test", "password": "123456"})
    assert account_login.status_code == 200
    assert account_login.json()["data"]["username"] == "operator_test"
    assert client.put(f"/api/admin/accounts/{account_id}", json={"status": "disabled"}, headers=headers).json()["data"]["status"] == "disabled"
    disabled_login = client.post("/api/admin/auth/login", json={"username": "operator_test", "password": "123456"})
    assert disabled_login.status_code == 403
    assert client.post(f"/api/admin/accounts/{account_id}/reset-password", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/accounts/{account_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/roles/{custom_role_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/roles/{role_limit_2.json()['data']['roleId']}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/roles/{role_limit_3.json()['data']['roleId']}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/permissions/{custom_permission_id}", headers=headers).status_code == 200
    assert client.post("/api/admin/versions/batch-delete", json={"ids": [version_id]}, headers=headers).status_code == 200
    assert client.post("/api/admin/announcements/batch-delete", json={"ids": [announcement_id]}, headers=headers).status_code == 200

    region = client.post(
        "/api/admin/regions",
        json={"name": "广东省", "code": "440000", "level": 1, "sort": 1, "status": "enabled"},
        headers=headers,
    )
    assert region.status_code == 200
    region_id = region.json()["data"]["regionId"]
    assert client.get(f"/api/admin/regions/{region_id}", headers=headers).json()["data"]["code"] == "440000"

    dictionary = client.post(
        "/api/admin/dictionaries",
        json={"type": "post_status", "label": "已上架", "value": "online", "sort": 1, "status": "enabled"},
        headers=headers,
    )
    assert dictionary.status_code == 200
    dict_id = dictionary.json()["data"]["dictId"]
    child_dictionary = client.post(
        "/api/admin/dictionaries",
        json={
            "type": "post_status",
            "parentId": dict_id,
            "label": "精选动态",
            "value": "online_featured",
            "sort": 1,
            "status": "enabled",
        },
        headers=headers,
    )
    assert child_dictionary.status_code == 200
    child_dict_id = child_dictionary.json()["data"]["dictId"]
    assert child_dictionary.json()["data"]["parentId"] == dict_id
    duplicate_child_label = client.post(
        "/api/admin/dictionaries",
        json={
            "type": "post_status",
            "parentId": dict_id,
            "label": "精选动态",
            "value": "online_hot",
            "sort": 2,
            "status": "enabled",
        },
        headers=headers,
    )
    assert duplicate_child_label.status_code == 400
    assert duplicate_child_label.json()["message"] == "同一上级下字典标签已存在"
    duplicate_child_value = client.post(
        "/api/admin/dictionaries",
        json={
            "type": "post_status",
            "parentId": dict_id,
            "label": "推荐动态",
            "value": "online_featured",
            "sort": 3,
            "status": "enabled",
        },
        headers=headers,
    )
    assert duplicate_child_value.status_code == 400
    assert duplicate_child_value.json()["message"] == "同一上级下字典键值已存在"
    dict_list = client.get("/api/admin/dictionaries", params={"type": "post_status"}, headers=headers)
    assert dict_list.status_code == 200
    assert dict_list.json()["data"]["list"][0]["dictId"] == dict_id
    assert dict_list.json()["data"]["list"][0]["children"][0]["dictId"] == child_dict_id
    dict_children = client.get(f"/api/admin/dictionaries/{dict_id}/children", headers=headers)
    assert dict_children.status_code == 200
    assert dict_children.json()["data"]["parent"]["dictId"] == dict_id
    assert dict_children.json()["data"]["list"][0]["parentId"] == dict_id

    system_message = client.post(
        "/api/admin/system-messages",
        json={
            "title": "系统维护",
            "content": "今晚 23:00 维护",
            "type": "notice",
            "target": "all",
            "status": "published",
            "isPinned": True,
        },
        headers=headers,
    )
    assert system_message.status_code == 200
    message_id = system_message.json()["data"]["messageId"]
    assert system_message.json()["data"]["isPinned"] is True
    assert "message_id" not in system_message.json()["data"]
    message_list = client.get("/api/admin/system-messages", params={"status": "published"}, headers=headers)
    assert message_list.status_code == 200
    assert message_list.json()["data"]["list"][0]["messageId"] == message_id

    assert client.delete(f"/api/admin/tags/{tag_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/regions/{region_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/dictionaries/{dict_id}", headers=headers).status_code == 400
    assert client.delete(f"/api/admin/dictionaries/{child_dict_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/dictionaries/{dict_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/system-messages/{message_id}", headers=headers).status_code == 200


def test_notification_dropdowns_for_admin_and_user() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    user_token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_notify", "nickname": "Notify User"},
    )
    user_headers = {"Authorization": f"Bearer {user_token_response.json()['accessToken']}"}
    admin_login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['token']}"}

    system_message = client.post(
        "/api/admin/system-messages",
        json={
            "title": "我的家",
            "content": "这是一条要展示在 PC 和用户端通知下拉里的系统消息",
            "type": "notification",
            "target": "all",
            "status": "published",
            "isPinned": False,
        },
        headers=admin_headers,
    )
    assert system_message.status_code == 200
    assert system_message.json()["data"]["pushedCount"] == 1

    admin_notifications = client.get("/api/admin/notifications", headers=admin_headers)
    assert admin_notifications.status_code == 200
    assert admin_notifications.json()["data"]["unreadCount"] == 1
    admin_message_id = admin_notifications.json()["data"]["list"][0]["messageId"]
    assert admin_notifications.json()["data"]["list"][0]["title"] == "我的家"

    user_notifications = client.get("/api/messages/notifications", headers=user_headers)
    assert user_notifications.status_code == 200
    assert user_notifications.json()["data"]["unreadCount"] == 1
    user_message_id = user_notifications.json()["data"]["list"][0]["messageId"]
    assert user_notifications.json()["data"]["list"][0]["title"] == "我的家"

    read_user = client.get(f"/api/messages/notifications/{user_message_id}", headers=user_headers)
    assert read_user.status_code == 200
    assert read_user.json()["data"]["isRead"] is True
    assert client.get("/api/messages/notifications", headers=user_headers).json()["data"]["unreadCount"] == 0

    read_admin = client.get(f"/api/admin/notifications/{admin_message_id}", headers=admin_headers)
    assert read_admin.status_code == 200
    assert read_admin.json()["data"]["isRead"] is True
    assert client.get("/api/admin/notifications", headers=admin_headers).json()["data"]["unreadCount"] == 0

    second_user_token_response = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_notify_other", "nickname": "Other User"},
    )
    second_user_headers = {"Authorization": f"Bearer {second_user_token_response.json()['accessToken']}"}
    second_message = client.post(
        "/api/admin/system-messages",
        json={
            "title": "第二条通知",
            "content": "用于验证谁点击谁已读，其他用户不受影响",
            "type": "notification",
            "target": "all",
            "status": "published",
            "isPinned": False,
        },
        headers=admin_headers,
    )
    assert second_message.status_code == 200
    first_user_list = client.get("/api/messages/notifications", headers=user_headers).json()["data"]
    second_user_list = client.get("/api/messages/notifications", headers=second_user_headers).json()["data"]
    assert first_user_list["unreadCount"] == 1
    assert second_user_list["unreadCount"] == 1
    client.get(f"/api/messages/notifications/{first_user_list['list'][0]['messageId']}", headers=user_headers)
    assert client.get("/api/messages/notifications", headers=user_headers).json()["data"]["unreadCount"] == 0
    assert client.get("/api/messages/notifications", headers=second_user_headers).json()["data"]["unreadCount"] == 1


def test_dev_token_unique_identity_conflict_returns_message() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    created = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_a", "openid": "openid_same", "phone": "13800000000"},
    )
    assert created.status_code == 200

    conflict = client.post(
        "/api/auth/dev-token",
        json={"userId": "usr_b", "openid": "openid_same"},
    )
    assert conflict.status_code == 400
    assert conflict.json() == {
        "code": 400,
        "message": "该 openid/unionid/phone 已绑定其他 userId",
        "data": {},
    }


def test_wx_login() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    response = client.post(
        "/api/auth/wx-login",
        json={"code": "demo-code", "nickname": "微信用户"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accessToken"]
    assert body["token"] == body["accessToken"]
    assert body["user"]["nickname"] == "微信用户"


def test_mobile_phone_login_uses_mp_user_id_and_client_type() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    response = client.post(
        "/api/auth/dev-token",
        json={
            "userId": "h5-18072783978",
            "nickname": "移动端用户",
            "clientType": "安卓",
        },
    )
    assert response.status_code == 200
    assert response.json()["userId"] == "mp-18072783978"

    profile = client.get("/api/user/profile", headers={"Authorization": f"Bearer {response.json()['accessToken']}"})
    assert profile.status_code == 200
    assert profile.json()["phone"] == "18072783978"
    assert profile.json()["clientType"] == "android"

    admin_login = client.post("/api/admin/auth/login", json={"username": "admin", "password": "123456"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['token']}"}
    detail = client.get("/api/admin/users/mp-18072783978", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["phone"] == "18072783978"
    assert detail.json()["data"]["clientType"] == "android"


def test_wx_login_with_phone_records_mobile_type() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    response = client.post(
        "/api/auth/wx-login",
        json={
            "code": "mobile-code",
            "phone": "180 7278 3979",
            "nickname": "小程序用户",
            "clientType": "miniprogram",
            "clientSubtype": "weixin",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["userId"] == "mp-18072783979"
    assert body["user"]["phone"] == "18072783979"
    assert body["user"]["clientType"] == "miniprogram"
    assert body["user"]["clientSubtype"] == "wechat"
