from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = "memory://"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.post import Post
from app.models.ai_model import AiModelUsageRecord


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def mobile_headers(client: TestClient, phone: str, nickname: str) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/auth/dev-token",
        json={"phone": phone, "code": "123456", "clientType": "android"},
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]
    user_id = response.json()["userId"]

    # 修改该用户的昵称
    db = SessionLocal()
    user = db.query(User).filter(User.user_id == user_id).first()
    user.nickname = nickname
    db.commit()
    db.close()

    return {"Authorization": f"Bearer {token}"}, user_id


def test_global_stats_visibility_flow() -> None:
    reset_database()
    client = TestClient(app)

    # 1. 登录用户 A (Alice) 和用户 B (Bob)
    headers_a, user_a_id = mobile_headers(client, "13811110001", "Alice")
    headers_b, user_b_id = mobile_headers(client, "13811110002", "Bob")

    # 2. 为 Alice 创建一个帖子和一个 AIGC 作品（包含初始统计数据）
    db = SessionLocal()
    post = Post(
        post_id="post_test_1",
        user_id=user_a_id,
        content="我的精彩生活动态",
        visibility="public",
        status="online",
        like_count=5,
        comment_count=8,
    )
    work = AiModelUsageRecord(
        record_id="work_test_1",
        user_id=user_a_id,
        model_id="aim_image",
        model_name="绘图模型",
        model_type="image",
        points_consumed=2,
        status="completed",
        is_deleted=False,
        visibility="public",
        like_count=12,
        comment_count=4,
        favorite_count=9,
        view_count=150,
    )
    db.add(post)
    db.add(work)
    db.commit()
    db.close()

    # 3. 默认情况下，Bob (其他用户) 可以看到真实的帖子和作品统计数据
    # AIGC 作品
    resp_work = client.get("/api/ai-model/history/work_test_1/public", headers=headers_b)
    assert resp_work.status_code == 200
    data_w = resp_work.json()["data"]
    assert data_w["likeCount"] == 12
    assert data_w["commentCount"] == 4
    assert data_w["favoriteCount"] == 9
    # 每次免登录打开会自增 1，所以 viewCount 为 151
    assert data_w["viewCount"] == 151

    # 帖子
    resp_post = client.get("/api/posts/post_test_1", headers=headers_b)
    assert resp_post.status_code == 200
    data_p = resp_post.json()
    assert data_p["likeCount"] == 5
    assert data_p["commentCount"] == 8

    # 4. Alice 更新个人设置，隐藏点赞量和评论量 (showLikes = False, showComments = False)
    resp_set = client.put(
        "/api/user/profile/settings",
        headers=headers_a,
        json={"showLikes": False, "showComments": False},
    )
    assert resp_set.status_code == 200
    profile = resp_set.json()
    assert profile["showLikes"] is False
    assert profile["showComments"] is False
    assert profile["showViews"] is True
    assert profile["showFavorites"] is True

    # 5. Bob (其他用户) 再次请求 Alice 的内容：点赞量和评论量返回 0，其余字段不变
    # AIGC 作品
    resp_work_b = client.get("/api/ai-model/history/work_test_1/public", headers=headers_b)
    assert resp_work_b.status_code == 200
    data_w_b = resp_work_b.json()["data"]
    assert data_w_b["likeCount"] == 0
    assert data_w_b["commentCount"] == 0
    assert data_w_b["favoriteCount"] == 9
    assert data_w_b["viewCount"] == 152  # 访问量继续自增

    # 帖子
    resp_post_b = client.get("/api/posts/post_test_1", headers=headers_b)
    assert resp_post_b.status_code == 200
    data_p_b = resp_post_b.json()
    assert data_p_b["likeCount"] == 0
    assert data_p_b["commentCount"] == 0

    # 6. Alice (作者本人) 访问自己的内容：依然能够看到真实的数据！
    resp_work_a = client.get("/api/ai-model/history/work_test_1/public", headers=headers_a)
    assert resp_work_a.status_code == 200
    data_w_a = resp_work_a.json()["data"]
    assert data_w_a["likeCount"] == 12
    assert data_w_a["commentCount"] == 4

    resp_post_a = client.get("/api/posts/post_test_1", headers=headers_a)
    assert resp_post_a.status_code == 200
    data_p_a = resp_post_a.json()
    assert data_p_a["likeCount"] == 5
    assert data_p_a["commentCount"] == 8

    # 7. Alice 使用一键隐藏开关 (toggleAll = False)
    resp_set2 = client.put(
        "/api/user/profile/settings",
        headers=headers_a,
        json={"toggleAll": False},
    )
    assert resp_set2.status_code == 200
    p2 = resp_set2.json()
    assert p2["showLikes"] is False
    assert p2["showViews"] is False
    assert p2["showComments"] is False
    assert p2["showFavorites"] is False

    # Bob 视角：所有统计数据全部为 0
    resp_work_b2 = client.get("/api/ai-model/history/work_test_1/public", headers=headers_b)
    assert resp_work_b2.status_code == 200
    d_b2 = resp_work_b2.json()["data"]
    assert d_b2["likeCount"] == 0
    assert d_b2["commentCount"] == 0
    assert d_b2["favoriteCount"] == 0
    assert d_b2["viewCount"] == 0

    # 8. Alice 使用一键开启开关 (toggleAll = True)
    resp_set3 = client.put(
        "/api/user/profile/settings",
        headers=headers_a,
        json={"toggleAll": True},
    )
    assert resp_set3.status_code == 200
    p3 = resp_set3.json()
    assert p3["showLikes"] is True
    assert p3["showViews"] is True
    assert p3["showComments"] is True
    assert p3["showFavorites"] is True

    # Bob 视角：所有真实数据重新显示
    resp_work_b3 = client.get("/api/ai-model/history/work_test_1/public", headers=headers_b)
    assert resp_work_b3.status_code == 200
    d_b3 = resp_work_b3.json()["data"]
    assert d_b3["likeCount"] == 12
    assert d_b3["commentCount"] == 4
    assert d_b3["favoriteCount"] == 9
    assert d_b3["viewCount"] == 155
