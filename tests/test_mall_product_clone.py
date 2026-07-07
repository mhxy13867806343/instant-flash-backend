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
from app.models.mall import MallProduct


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


from app.core.security import create_access_token


def admin_headers() -> dict[str, str]:
    token = create_access_token("admin:super_admin")
    return {"Authorization": f"Bearer {token}"}


def test_product_clone_flow() -> None:
    reset_database()
    client = TestClient(app)
    headers = admin_headers()

    # 1. 常规创建一个带克隆标志和链接的商品 A
    resp_create = client.post(
        "/api/admin/mall/products",
        headers=headers,
        json={
            "title": "母版商品 A",
            "description": "这是商品 A 描述",
            "originalPrice": 10000,
            "currentPrice": 8000,
            "stock": 50,
            "status": "on_sale",
            "isCloned": False,
        },
    )
    assert resp_create.status_code == 201
    prod_a = resp_create.json()["data"]
    assert prod_a["title"] == "母版商品 A"
    assert prod_a["isCloned"] is False
    assert prod_a["cloneUrl"] is None
    prod_a_id = prod_a["productId"]

    # 2. 一键克隆商品 A 生成克隆商品 B
    resp_clone = client.post(
        f"/api/admin/mall/products/{prod_a_id}/clone",
        headers=headers,
        json={
            "cloneUrl": "https://cloned.link/item_a",
            "title": "克隆新商品 B",
        },
    )
    assert resp_clone.status_code == 201
    prod_b = resp_clone.json()["data"]
    assert prod_b["title"] == "克隆新商品 B"
    assert prod_b["isCloned"] is True
    assert prod_b["cloneUrl"] == "https://cloned.link/item_a"
    assert prod_b["originalPrice"] == 10000
    assert prod_b["stock"] == 50
    prod_b_id = prod_b["productId"]

    # 3. 已经被克隆过的商品不能再次克隆了（即尝试克隆商品 B 应报错）
    resp_clone_again = client.post(
        f"/api/admin/mall/products/{prod_b_id}/clone",
        headers=headers,
        json={
            "cloneUrl": "https://cloned.link/item_b",
        },
    )
    assert resp_clone_again.status_code == 400
    assert "已经被克隆过的商品不能再次克隆了的" in resp_clone_again.json()["message"]

    # 4. 修改克隆商品 B 的克隆链接
    resp_update = client.put(
        f"/api/admin/mall/products/{prod_b_id}",
        headers=headers,
        json={
            "cloneUrl": "https://new.link/item_b_updated",
        },
    )
    assert resp_update.status_code == 200
    prod_b_updated = resp_update.json()["data"]
    assert prod_b_updated["cloneUrl"] == "https://new.link/item_b_updated"
    assert prod_b_updated["isCloned"] is True
