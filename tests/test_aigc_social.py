from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = "memory://"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.ai_model import AiModel, AiModelUsageRecord


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def mobile_headers(client: TestClient, phone: str, client_type: str = "android") -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/auth/dev-token",
        json={"phone": phone, "code": "123456", "clientType": client_type},
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]
    user_id = response.json()["userId"]
    return {"Authorization": f"Bearer {token}"}, user_id


def test_aigc_works_social_system_flow() -> None:
    reset_database()
    client = TestClient(app)

    # 1. 登录两个用户 (User A 和 User B)
    headers_a, user_a_id = mobile_headers(client, "13811112222")
    headers_b, user_b_id = mobile_headers(client, "13833334444")

    # 2. 为 User A 生成一条使用历史记录
    # 模拟先向数据库中添加基础模型数据以供生成
    db = SessionLocal()
    m = AiModel(
        model_id="aim_image_test",
        name="测试生图模型",
        type="image",
        points_per_use=1,
        status="enabled",
    )
    db.add(m)
    db.commit()

    # User A 进入页面，获取模型积分，调用生图
    client.get("/api/ai-model/enter", headers=headers_a)
    resp_use = client.post(
        "/api/ai-model/use",
        headers=headers_a,
        json={"modelId": "aim_image_test", "prompt": "一幅漂亮的油画"},
    )
    assert resp_use.status_code == 200
    record_id = resp_use.json()["data"]["record"]["recordId"]

    # 3. 编辑该作品：修改标题、描述，并将其公开可见性设为 public
    resp_edit = client.put(
        f"/api/ai-model/history/{record_id}",
        headers=headers_a,
        json={
            "title": "春天的森林",
            "description": "阳光穿过树梢，洒在草地上。",
            "visibility": "public",
        },
    )
    assert resp_edit.status_code == 200
    assert resp_edit.json()["data"]["title"] == "春天的森林"
    assert resp_edit.json()["data"]["visibility"] == "public"

    # 4. 公开查看详情（免登录）
    # 用匿名客户端直接访问
    resp_pub = client.get(f"/api/ai-model/history/{record_id}/public")

    assert resp_pub.status_code == 200
    assert resp_pub.json()["data"]["title"] == "春天的森林"
    assert resp_pub.json()["data"]["viewCount"] == 1  # 验证浏览量自增了

    # 5. 发现画廊 (Discover feed) 校验
    # 免登录查看发现画廊
    resp_disc = client.get("/api/ai-model/discover?sortBy=latest")
    assert resp_disc.status_code == 200
    assert len(resp_disc.json()["data"]["list"]) == 1
    assert resp_disc.json()["data"]["list"][0]["recordId"] == record_id

    # 6. 点赞互动
    # User B 对该作品进行点赞
    resp_like = client.post(f"/api/ai-model/works/{record_id}/like", headers=headers_b)
    assert resp_like.status_code == 200
    assert resp_like.json()["data"]["liked"] is True
    assert resp_like.json()["data"]["likeCount"] == 1

    # 再次请求，即取消点赞
    resp_unlike = client.post(f"/api/ai-model/works/{record_id}/like", headers=headers_b)
    assert resp_unlike.status_code == 200
    assert resp_unlike.json()["data"]["liked"] is False
    assert resp_unlike.json()["data"]["likeCount"] == 0

    # 重新点赞以供后续测试
    client.post(f"/api/ai-model/works/{record_id}/like", headers=headers_b)

    # 7. 收藏互动
    # User B 对该作品进行收藏
    resp_fav = client.post(f"/api/ai-model/works/{record_id}/favorite", headers=headers_b)
    assert resp_fav.status_code == 200
    assert resp_fav.json()["data"]["favorited"] is True
    assert resp_fav.json()["data"]["favoriteCount"] == 1

    # 8. 评论互动
    # User B 发表评论
    resp_comm = client.post(
        f"/api/ai-model/works/{record_id}/comments",
        headers=headers_b,
        json={"content": "太逼真了，颜色非常棒！"},
    )
    assert resp_comm.status_code == 200
    comment_id = resp_comm.json()["data"]["commentId"]
    assert resp_comm.json()["data"]["content"] == "太逼真了，颜色非常棒！"

    # User A 针对 User B 的评论进行回复 (parentId)
    resp_reply = client.post(
        f"/api/ai-model/works/{record_id}/comments",
        headers=headers_a,
        json={"content": "谢谢夸奖！", "parentId": comment_id},
    )
    assert resp_reply.status_code == 200
    assert resp_reply.json()["data"]["parentId"] == comment_id

    # 9. 拉取评论列表
    resp_comm_list = client.get(f"/api/ai-model/works/{record_id}/comments")
    assert resp_comm_list.status_code == 200
    # 评论总数应当是 2（1个主评论，1个回复）
    assert resp_comm_list.json()["data"]["total"] == 2

    # 10. 删除评论
    # User B 删除其评论，应该被标记为 isDeleted == True
    resp_del = client.delete(f"/api/ai-model/works/comments/{comment_id}", headers=headers_b)
    assert resp_del.status_code == 200

    # 再次查询评论列表，查看状态
    resp_comm_list2 = client.get(f"/api/ai-model/works/{record_id}/comments")
    # 总条数没有变 (is_deleted软删除仍保留在树上以便查看子节点，或者直接过滤。在此处我们的列表按原查询展示，commentCount会自减)
    # 验证 commentCount 减少了 1
    resp_detail = client.get(f"/api/ai-model/history/{record_id}/public", headers=headers_b)
    assert resp_detail.json()["data"]["commentCount"] == 1
    assert resp_detail.json()["data"]["isLiked"] is True
    assert resp_detail.json()["data"]["isFavorited"] is True
    assert resp_detail.json()["data"]["isOwner"] is False

    db.close()

