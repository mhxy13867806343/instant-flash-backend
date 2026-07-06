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
from app.models.message import Message
from app.models.post import Post
from app.models.chat import ChatGroup, ChatGroupMember
from app.models.ai_model import AiModel, AiModelUsageRecord
from app.core.link_parser import parse_links_in_text


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def mobile_headers(client: TestClient, phone: str, nickname: str) -> tuple[dict[str, str], str]:
    # 创建带特定昵称的账号进行 @ 测试
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


def test_link_parser_fallback() -> None:
    # 验证无效 URL 的安全回退解析，不引发异常且返回正确的域名作为标题
    text = "快来查看这个网站：https://nonexistent-url-domain.xyz/page/item"
    results = parse_links_in_text(text)
    assert len(results) == 1
    assert results[0]["url"] == "https://nonexistent-url-domain.xyz/page/item"
    assert results[0]["title"] == "nonexistent-url-domain.xyz"
    assert results[0]["description"] == "暂无描述"


def test_public_parse_link_endpoint() -> None:
    reset_database()
    client = TestClient(app)

    # 验证免登录公共工具接口
    resp = client.get("/api/utils/parse-link?url=https://www.google.com")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200
    assert resp.json()["data"]["url"] == "https://www.google.com"


def test_comments_and_chat_mentions_flow() -> None:
    reset_database()
    client = TestClient(app)

    # 1. 登录用户 A (昵称 Alice) 和用户 B (昵称 Bob)
    headers_a, user_a_id = mobile_headers(client, "13811110001", "Alice")
    headers_b, user_b_id = mobile_headers(client, "13811110002", "Bob")

    # -----------------------------------------------------------------------
    # 测试一：在帖子评论中 @Bob
    # -----------------------------------------------------------------------
    db = SessionLocal()
    # 为 Alice 创建一个帖子
    post = Post(
        post_id="post_test_1",
        user_id=user_a_id,
        content="今天天气真好",
        visibility="public",
        status="online",
    )
    db.add(post)
    db.commit()
    db.close()

    # Alice 对自己的帖子发评论，内容中 @Bob
    resp_cmt = client.post(
        "/api/posts/post_test_1/comments",
        headers=headers_a,
        json={"content": "哈哈，@Bob 你觉得呢？"},
    )
    assert resp_cmt.status_code == 201
    comment_id = resp_cmt.json()["commentId"]

    # 登录 Bob 账户查询其消息列表，看是否收到了 @ 消息
    resp_msg_b = client.get("/api/messages?unreadOnly=true", headers=headers_b)
    assert resp_msg_b.status_code == 200
    msgs = resp_msg_b.json()
    assert len(msgs) == 1
    assert msgs[0]["type"] == "mention"
    assert msgs[0]["title"] == "Alice @了你"
    assert msgs[0]["commentId"] == comment_id
    assert "你觉得呢" in msgs[0]["content"]

    # -----------------------------------------------------------------------
    # 测试二：在 AIGC 作品评论中 @Alice
    # -----------------------------------------------------------------------
    db = SessionLocal()
    # 为 Bob 创建一个 AIGC 作品
    work = AiModelUsageRecord(
        record_id="work_test_1",
        user_id=user_b_id,
        model_id="aim_test",
        model_name="生图模型",
        model_type="image",
        points_consumed=1,
        status="completed",
        is_deleted=False,
        visibility="public",
    )
    db.add(work)
    db.commit()
    db.close()

    # Bob 评论自己的作品，内容中 @Alice
    resp_aigc_cmt = client.post(
        "/api/ai-model/works/work_test_1/comments",
        headers=headers_b,
        json={"content": "这是我生成的，好看不 @Alice"},
    )
    assert resp_aigc_cmt.status_code == 200
    aigc_cmt_id = resp_aigc_cmt.json()["data"]["commentId"]

    # 登录 Alice 账户查询消息
    resp_msg_a = client.get("/api/messages?unreadOnly=true", headers=headers_a)
    assert resp_msg_a.status_code == 200
    msgs_a = resp_msg_a.json()
    assert len(msgs_a) == 1
    assert msgs_a[0]["type"] == "mention"
    assert msgs_a[0]["title"] == "Bob @了你"
    assert msgs_a[0]["commentId"] == aigc_cmt_id

    # -----------------------------------------------------------------------
    # 测试三：在群聊消息中 @Bob
    # -----------------------------------------------------------------------
    db = SessionLocal()
    # 创建一个活跃群聊，把 Alice 和 Bob 加入进去
    group = ChatGroup(
        group_id="group_test_1",
        name="测试群聊",
        status="active",
        owner_id=user_a_id,
    )
    member_a = ChatGroupMember(group_id="group_test_1", user_id=user_a_id, role="owner")
    member_b = ChatGroupMember(group_id="group_test_1", user_id=user_b_id, role="member")
    db.add(group)
    db.add(member_a)
    db.add(member_b)
    db.commit()
    db.close()

    # Alice 在群聊中发送消息，并 @Bob
    resp_grp_msg = client.post(
        "/api/chat/groups/group_test_1/messages",
        headers=headers_a,
        json={
            "content": "大家晚上好 @Bob",
            "msgType": "text",
            "atUserIds": [user_b_id],
        },
    )
    assert resp_grp_msg.status_code == 200

    # 登录 Bob 账户查询最新的未读消息列表（测试一中的已读/未读状态不变，应该多出一条）
    resp_msg_b2 = client.get("/api/messages?unreadOnly=true", headers=headers_b)
    assert resp_msg_b2.status_code == 200
    msgs_b2 = resp_msg_b2.json()
    # Alice 对 Bob 提到了两次：一次在帖子评论，一次在群聊
    assert len(msgs_b2) == 2
    # 过滤出群聊的那条 @ 消息
    chat_mentions = [m for m in msgs_b2 if "大家晚上好" in m["content"]]
    assert len(chat_mentions) == 1
    assert chat_mentions[0]["type"] == "mention"
    assert chat_mentions[0]["title"] == "Alice @了你"
