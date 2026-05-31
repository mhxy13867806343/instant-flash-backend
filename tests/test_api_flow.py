from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

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

    users = client.get("/api/admin/users", headers=admin_headers)
    assert users.status_code == 200
    assert users.json()["data"]["total"] == 1
    assert users.json()["data"]["list"][0]["status"] == "normal"
    assert users.json()["data"]["list"][0]["userId"] == "usr_admin_target"
    assert "user_id" not in users.json()["data"]["list"][0]

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
    dict_list = client.get("/api/admin/dictionaries", params={"type": "post_status"}, headers=headers)
    assert dict_list.status_code == 200
    assert dict_list.json()["data"]["list"][0]["dictId"] == dict_id

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

    read_user = client.put(f"/api/messages/{user_message_id}/read", headers=user_headers)
    assert read_user.status_code == 200
    assert read_user.json()["data"]["isRead"] is True
    assert client.get("/api/messages/notifications", headers=user_headers).json()["data"]["unreadCount"] == 0

    read_admin = client.put(f"/api/admin/notifications/{admin_message_id}/read", headers=admin_headers)
    assert read_admin.status_code == 200
    assert read_admin.json()["data"]["isRead"] is True
    assert client.get("/api/admin/notifications", headers=admin_headers).json()["data"]["unreadCount"] == 0


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
