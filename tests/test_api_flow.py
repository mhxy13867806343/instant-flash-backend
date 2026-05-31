from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


def test_content_flow() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    token_response = client.post(
        "/api/auth/dev-token",
        json={"user_id": "usr_test", "nickname": "Tester"},
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
        json={"user_id": "usr_admin_target", "nickname": "Target", "phone": "13812345678"},
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

    banned = client.put(
        "/api/admin/users/usr_admin_target",
        json={"status": "banned"},
        headers=admin_headers,
    )
    assert banned.status_code == 200
    assert client.get("/api/user/profile", headers=user_headers).status_code == 401

    offline = client.put(f"/api/admin/posts/{post_id}/offline", headers=admin_headers)
    assert offline.status_code == 200
    assert client.get(f"/api/posts/{post_id}").status_code == 404

    admin_post = client.get(f"/api/admin/posts/{post_id}", headers=admin_headers)
    assert admin_post.status_code == 200
    assert admin_post.json()["data"]["status"] == "offline"

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
