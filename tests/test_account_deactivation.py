from __future__ import annotations

import os
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = "memory://"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.account_deactivation import deactivation_is_due
from app.db.base import Base, utc_now
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def mobile_headers(client: TestClient, phone: str, client_type: str) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/auth/dev-token",
        json={"phone": phone, "code": "123456", "clientType": client_type},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}, response.json()["userId"]


@pytest.mark.parametrize("client_type", ["android", "ios", "harmonyos", "miniprogram", "h5"])
def test_mobile_client_types_can_apply_for_deactivation(client_type: str) -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, f"1380000000{len(client_type)}", client_type)

    response = client.post(
        "/api/user/deactivation",
        json={"reason": "我确认不再使用这个账号了"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["deactivationStatus"] == "pending"


def test_non_mobile_account_cannot_apply_for_deactivation() -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, "13800000100", "web")

    response = client.post(
        "/api/user/deactivation",
        json={"reason": "我确认不再使用这个账号了"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["message"] == "账号注销仅支持移动端操作"


@pytest.mark.parametrize("reason", [" 九个字不够用啊 ", "字" * 501])
def test_deactivation_reason_is_validated_after_trimming(reason: str) -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, "13800000101", "android")

    response = client.post(
        "/api/user/deactivation",
        json={"reason": reason},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["message"] == "请求参数校验失败"


@pytest.mark.parametrize("length", [10, 500])
def test_deactivation_reason_boundary_lengths_are_accepted(length: int) -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, "13800000110", "android")

    response = client.post(
        "/api/user/deactivation",
        json={"reason": "字" * length},
        headers=headers,
    )

    assert response.status_code == 200


def test_apply_for_deactivation_persists_trimmed_reason_and_sixty_day_deadline() -> None:
    reset_database()
    client = TestClient(app)
    headers, user_id = mobile_headers(client, "13800000102", "android")

    response = client.post(
        "/api/user/deactivation",
        json={"reason": "  我确认不再使用这个账号了  "},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "账号注销申请成功，可在60天内取消"
    assert body["data"]["deactivationStatus"] == "pending"
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        assert user.deactivation_status == "pending"
        assert user.deactivation_reason == "我确认不再使用这个账号了"
        assert user.deactivation_apply_time is not None
        assert user.deactivation_end_time is not None
        assert user.deactivation_end_time - user.deactivation_apply_time == timedelta(days=60)


def test_pending_account_cannot_apply_twice() -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, "13800000103", "ios")
    payload = {"reason": "我确认不再使用这个账号了"}

    first = client.post("/api/user/deactivation", json=payload, headers=headers)
    second = client.post("/api/user/deactivation", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["message"] == "账号已申请注销，请勿重复申请"


def test_pending_account_can_login_and_profile_exposes_deactivation() -> None:
    reset_database()
    client = TestClient(app)
    phone = "13800000104"
    headers, _ = mobile_headers(client, phone, "android")
    apply_response = client.post(
        "/api/user/deactivation",
        json={"reason": "我确认不再使用这个账号了"},
        headers=headers,
    )

    profile = client.get("/api/user/profile", headers=headers)
    relogin = client.post(
        "/api/auth/dev-token",
        json={"phone": phone, "code": "123456", "clientType": "android"},
    )

    assert apply_response.status_code == 200
    assert profile.status_code == 200
    assert profile.json()["deactivationStatus"] == "pending"
    assert profile.json()["deactivationReason"] == "我确认不再使用这个账号了"
    assert profile.json()["deactivationApplyTime"] is not None
    assert profile.json()["deactivationEndTime"] is not None
    assert relogin.status_code == 200


def test_pending_mobile_account_can_cancel_deactivation() -> None:
    reset_database()
    client = TestClient(app)
    headers, user_id = mobile_headers(client, "13800000105", "ios")
    client.post(
        "/api/user/deactivation",
        json={"reason": "我确认不再使用这个账号了"},
        headers=headers,
    )

    response = client.post("/api/user/deactivation/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "账号注销已取消"
    assert response.json()["data"]["deactivationStatus"] is None
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        assert user.is_active is True
        assert user.deactivation_status is None
        assert user.deactivation_reason is None
        assert user.deactivation_apply_time is None
        assert user.deactivation_end_time is None


def test_account_without_pending_application_cannot_cancel() -> None:
    reset_database()
    client = TestClient(app)
    headers, _ = mobile_headers(client, "13800000106", "h5")

    response = client.post("/api/user/deactivation/cancel", headers=headers)

    assert response.status_code == 400
    assert response.json()["message"] == "账号当前没有待取消的注销申请"


def test_non_mobile_account_cannot_cancel_deactivation() -> None:
    reset_database()
    client = TestClient(app)
    headers, user_id = mobile_headers(client, "13800000107", "web")
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        user.deactivation_status = "pending"
        user.deactivation_apply_time = utc_now()
        user.deactivation_end_time = utc_now() + timedelta(days=60)
        db.commit()

    response = client.post("/api/user/deactivation/cancel", headers=headers)

    assert response.status_code == 400
    assert response.json()["message"] == "账号注销仅支持移动端操作"


def test_deactivation_is_due_at_exact_deadline() -> None:
    deadline = utc_now()
    user = User(
        user_id="mp-boundary",
        deactivation_status="pending",
        deactivation_end_time=deadline,
    )

    assert deactivation_is_due(user, now=deadline) is True


def test_expired_pending_account_cannot_cancel_and_is_persisted() -> None:
    reset_database()
    client = TestClient(app)
    headers, user_id = mobile_headers(client, "13800000108", "android")
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        user.deactivation_status = "pending"
        user.deactivation_reason = "我确认不再使用这个账号了"
        user.deactivation_apply_time = utc_now() - timedelta(days=61)
        user.deactivation_end_time = utc_now() - timedelta(days=1)
        db.commit()

    response = client.post("/api/user/deactivation/cancel", headers=headers)

    assert response.status_code == 401
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        assert user.deactivation_status == "deactivated"
        assert user.is_active is False


def test_expired_pending_account_login_persists_permanent_deactivation() -> None:
    reset_database()
    client = TestClient(app)
    phone = "13800000109"
    _, user_id = mobile_headers(client, phone, "miniprogram")
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        user.deactivation_status = "pending"
        user.deactivation_reason = "我确认不再使用这个账号了"
        user.deactivation_apply_time = utc_now() - timedelta(days=61)
        user.deactivation_end_time = utc_now() - timedelta(days=1)
        db.commit()

    response = client.post(
        "/api/auth/dev-token",
        json={"phone": phone, "code": "123456", "clientType": "miniprogram"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "账号已永久注销"
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        assert user.deactivation_status == "deactivated"
        assert user.is_active is False
