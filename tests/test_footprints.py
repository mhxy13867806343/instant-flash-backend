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


def test_footprints_flow() -> None:
    reset_database()
    client = TestClient(app)

    # 1. 登录用户 Alice
    headers, user_id = mobile_headers(client, "13811110001", "Alice")

    # 2. 获取个人资料，此时足迹数量默认为 0
    resp_prof1 = client.get("/api/user/profile", headers=headers)
    assert resp_prof1.status_code == 200
    assert resp_prof1.json()["footprintCount"] == 0

    # 3. 创建足迹 A (泰山景区)
    resp_create_a = client.post(
        "/api/user/footprints",
        headers=headers,
        json={
            "title": "登顶泰山",
            "description": "风景很美",
            "latitude": 36.255,
            "longitude": 117.112,
            "locationName": "泰山景区",
            "images": ["https://foo.com/img1.jpg", "https://foo.com/img2.jpg"],
        },
    )
    assert resp_create_a.status_code == 201
    footprint_a = resp_create_a.json()["data"]
    assert footprint_a["title"] == "登顶泰山"
    assert footprint_a["locationName"] == "泰山景区"
    assert footprint_a["images"] == ["https://foo.com/img1.jpg", "https://foo.com/img2.jpg"]
    footprint_a_id = footprint_a["footprintId"]

    # 4. 获取资料，足迹数量应为 1
    resp_prof2 = client.get("/api/user/profile", headers=headers)
    assert resp_prof2.status_code == 200
    assert resp_prof2.json()["footprintCount"] == 1

    # 5. 创建足迹 B (西湖断桥)
    resp_create_b = client.post(
        "/api/user/footprints",
        headers=headers,
        json={
            "title": "西湖断桥",
            "latitude": 30.258,
            "longitude": 120.155,
            "locationName": "杭州西湖",
        },
    )
    assert resp_create_b.status_code == 201
    footprint_b = resp_create_b.json()["data"]
    assert footprint_b["title"] == "西湖断桥"
    assert footprint_b["description"] is None

    # 6. 获取资料，足迹数量应为 2
    resp_prof3 = client.get("/api/user/profile", headers=headers)
    assert resp_prof3.status_code == 200
    assert resp_prof3.json()["footprintCount"] == 2

    # 7. 获取足迹分页列表 (时间倒序)
    resp_list = client.get("/api/user/footprints/list?page=1&limit=10", headers=headers)
    assert resp_list.status_code == 200
    list_data = resp_list.json()["data"]
    assert list_data["total"] == 2
    assert len(list_data["list"]) == 2
    # 最新创建的在最前面，即 B (西湖) 在前面，A (泰山) 在后面
    assert list_data["list"][0]["title"] == "西湖断桥"
    assert list_data["list"][1]["title"] == "登顶泰山"

    # 8. 查看足迹 A 详情
    resp_detail = client.get(f"/api/user/footprints/{footprint_a_id}", headers=headers)
    assert resp_detail.status_code == 200
    assert resp_detail.json()["data"]["description"] == "风景很美"

    # 9. 编辑足迹 A 的标题与坐标
    resp_edit = client.put(
        f"/api/user/footprints/{footprint_a_id}",
        headers=headers,
        json={
            "title": "泰山主峰极顶",
            "latitude": 36.256,
            "description": "修改后的风景描述",
            "images": ["https://foo.com/img_updated.jpg"],
        },
    )
    assert resp_edit.status_code == 200
    assert resp_edit.json()["data"]["title"] == "泰山主峰极顶"
    assert resp_edit.json()["data"]["latitude"] == 36.256
    assert resp_edit.json()["data"]["description"] == "修改后的风景描述"
    assert resp_edit.json()["data"]["images"] == ["https://foo.com/img_updated.jpg"]
    # longitude 和 locationName 应该保持原样
    assert resp_edit.json()["data"]["longitude"] == 117.112
    assert resp_edit.json()["data"]["locationName"] == "泰山景区"

    # 10. 删除足迹 A (软删除)
    resp_del = client.delete(f"/api/user/footprints/{footprint_a_id}", headers=headers)
    assert resp_del.status_code == 200

    # 11. 获取个人资料，足迹数量应自减为 1
    resp_prof4 = client.get("/api/user/profile", headers=headers)
    assert resp_prof4.status_code == 200
    assert resp_prof4.json()["footprintCount"] == 1

    # 12. 查询详情，应当返回 404
    resp_detail_after = client.get(f"/api/user/footprints/{footprint_a_id}", headers=headers)
    assert resp_detail_after.status_code == 404

    # 13. 获取分页列表，应当只剩下 1 条记录
    resp_list_after = client.get("/api/user/footprints/list?page=1&limit=10", headers=headers)
    assert resp_list_after.status_code == 200
    list_data_after = resp_list_after.json()["data"]
    assert list_data_after["total"] == 1
    assert len(list_data_after["list"]) == 1
    assert list_data_after["list"][0]["title"] == "西湖断桥"
