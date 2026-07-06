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
from app.models.ai_model import AiModel, AiModelPlan, AiModelPromotion, AiModelUsageRecord, AiModelSubscription
from app.core.ai_model_points import (
    grant_daily_model_points,
    consume_model_points,
    expire_old_grants,
    calculate_plan_price,
)


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


def admin_headers(client: TestClient) -> dict[str, str]:
    # Mock admin login or dev token. Let's look up how admin token is generated
    response = client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "safe-password"},
    )
    # The default credentials in app might be admin / 123456
    if response.status_code != 200:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "123456"},
        )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_ai_model_points_logic() -> None:
    reset_database()
    db = SessionLocal()

    user = User(
        user_id="user_test_1",
        phone="13811112222",
        points=0,
        model_points=100,
        daily_model_points=0,
    )
    db.add(user)
    db.commit()

    # 1. 每日赠送模型积分
    grant = grant_daily_model_points(db, user, amount=50)
    assert grant is not None
    assert user.daily_model_points == 50
    assert grant.remaining == 50

    # 再次赠送应该返回 None
    grant2 = grant_daily_model_points(db, user, amount=50)
    assert grant2 is None
    assert user.daily_model_points == 50

    # 2. 积分消耗优先级：优先扣减每日赠送积分
    # 消耗 30 积分，剩余：赠送 20，充值 100
    info = consume_model_points(db, user, 30)
    assert info["dailyUsed"] == 30
    assert info["paidUsed"] == 0
    assert user.daily_model_points == 20
    assert user.model_points == 100

    # 3. 积分消耗跨越今日赠送和充值积分
    # 消耗 40 积分，剩余：赠送 0，充值 80
    info2 = consume_model_points(db, user, 40)
    assert info2["dailyUsed"] == 20
    assert info2["paidUsed"] == 20
    assert user.daily_model_points == 0
    assert user.model_points == 80

    # 4. 积分不足报错
    with pytest.raises(ValueError) as exc:
        consume_model_points(db, user, 100)
    assert "模型积分不足" in str(exc.value)

    db.close()


def test_plan_price_calculation() -> None:
    # 基础价格 100 分，原价 150 分
    # 促销活动打 7 折 (70)，并额外赠送 20% 积分
    promo = AiModelPromotion(
        promotion_id="promo_1",
        name="春节特惠",
        discount_rate=70,
        extra_points_pct=20,
        status="enabled",
    )
    prices = calculate_plan_price(100, 150, promo)
    assert prices["finalPrice"] == 70  # 100 * 70 // 100
    assert prices["originalPrice"] == 150
    assert prices["discountAmount"] == 80  # 150 - 70
    assert prices["extraPointsPct"] == 20


def test_mobile_ai_model_api_flow() -> None:
    reset_database()
    client = TestClient(app)

    # 1. 登录用户并进入 AI 模型页面
    headers, user_id = mobile_headers(client, "13855556666")
    resp = client.get("/api/ai-model/enter", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 200
    assert resp.json()["data"]["dailyModelPoints"] == 50
    assert resp.json()["data"]["modelPoints"] == 0

    # 2. 获取可用模型列表 (目前没有模型，返回空列表)
    resp = client.get("/api/ai-model/list", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0

    # 3. 后台管理员创建一个模型
    adm_headers = admin_headers(client)
    resp = client.post(
        "/api/admin/ai-models",
        headers=adm_headers,
        json={
            "name": "Seedance 2.0 Pro",
            "type": "video",
            "pointsPerUse": 10,
            "channel": "fast",
            "features": ["4K", "无水印"],
        },
    )
    assert resp.status_code == 200
    model_id = resp.json()["data"]["modelId"]

    # 4. 再次获取可用模型列表，应该有一条
    resp = client.get("/api/ai-model/list", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["modelId"] == model_id

    # 5. 用户调用模型进行视频生成
    resp = client.post(
        "/api/ai-model/use",
        headers=headers,
        json={"modelId": model_id, "prompt": "生成一个猫咪在草地上跑的视频"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["record"]["pointsConsumed"] == 10
    assert "mov_bbb.mp4" in resp.json()["data"]["record"]["result"]

    # 今日赠送积分应剩下 40
    resp = client.get("/api/ai-model/points", headers=headers)
    assert resp.json()["data"]["dailyModelPoints"] == 40
    assert resp.json()["data"]["modelPoints"] == 0

    # 6. 后台创建一个套餐
    resp = client.post(
        "/api/admin/ai-models/plans",
        headers=adm_headers,
        json={
            "name": "高级会员 (按月)",
            "tier": "premium",
            "periodType": "month",
            "durationDays": 30,
            "originalPrice": 19900,
            "currentPrice": 19900,
            "pointsMonthly": 1000,
            "features": ["高速通道", "无限生成"],
        },
    )
    assert resp.status_code == 200
    plan_id = resp.json()["data"]["planId"]

    # 7. 用户订阅套餐 (Mock 充值)
    resp = client.post(
        "/api/ai-model/subscribe",
        headers=headers,
        json={"planId": plan_id, "payMethod": "alipay"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["payStatus"] == "paid"
    assert resp.json()["data"]["pointsGranted"] == 1000

    # 检查积分余额
    resp = client.get("/api/ai-model/points", headers=headers)
    assert resp.json()["data"]["dailyModelPoints"] == 40
    assert resp.json()["data"]["modelPoints"] == 1000
    assert resp.json()["data"]["vipLevel"] == "premium"

    # 8. 检查历史记录
    resp = client.get("/api/ai-model/history", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1
    record_id = resp.json()["data"]["list"][0]["recordId"]

    # 删除历史记录
    resp = client.delete(f"/api/ai-model/history/{record_id}", headers=headers)
    assert resp.status_code == 200

    # 再次查询历史列表应为空
    resp = client.get("/api/ai-model/history", headers=headers)
    assert resp.json()["data"]["total"] == 0
