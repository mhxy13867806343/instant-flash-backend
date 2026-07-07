from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["REDIS_URL"] = "memory://"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.movie import MovieTicketOrder
from app.core.security import create_access_token


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def admin_headers() -> dict[str, str]:
    token = create_access_token("admin:super_admin")
    return {"Authorization": f"Bearer {token}"}


def user_headers(client: TestClient, phone: str, nickname: str) -> tuple[dict[str, str], str]:
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


def test_movie_ticketing_complete_flow() -> None:
    reset_database()
    client = TestClient(app)
    admin_hdr = admin_headers()

    # 用户登入
    headers_alice, user_alice = user_headers(client, "13800000001", "Alice")
    headers_bob, user_bob = user_headers(client, "13800000002", "Bob")

    # 1. 后台运营添加电影
    resp_mov = client.post(
        "/api/admin/movies",
        headers=admin_hdr,
        json={
            "title": "阿凡达：水之道",
            "director": "詹姆斯·卡梅隆",
            "actors": "萨姆·沃辛顿 / 佐伊·索尔达娜",
            "duration": 192,
            "movieType": "科幻/冒险",
            "releaseDate": "2022-12-16",
            "rating": 8.0,
            "introduction": "阿凡达续作描述潘多拉海洋部落的故事",
            "poster": "http://img.com/avatar2.jpg",
            "language": "英语",
            "status": "showing",
        },
    )
    assert resp_mov.status_code == 201
    movie = resp_mov.json()["data"]
    movie_id = movie["movieId"]

    # 2. 后台运营添加影院
    resp_cin = client.post(
        "/api/admin/movies/cinemas",
        headers=admin_hdr,
        json={
            "name": "万达影城（西湖店）",
            "logo": "http://img.com/wanda.png",
            "address": "杭州市西湖区延安路123号",
            "city": "杭州",
            "longitude": 120.15,
            "latitude": 30.25,
            "phone": "0571-88888888",
        },
    )
    assert resp_cin.status_code == 201
    cinema = resp_cin.json()["data"]
    cinema_id = cinema["cinemaId"]

    # 3. 后台运营添加影厅 (8排10列，禁用1-1和1-2)
    resp_hall = client.post(
        "/api/admin/movies/halls",
        headers=admin_hdr,
        json={
            "cinemaId": cinema_id,
            "name": "1号IMAX厅",
            "hallType": "IMAX",
            "seatLayout": {
                "rows": 8,
                "cols": 10,
                "broken": ["1-1", "1-2"],
            },
        },
    )
    assert resp_hall.status_code == 201
    hall = resp_hall.json()["data"]
    hall_id = hall["hallId"]

    # 4. 后台运营编排放映场次
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc + timedelta(hours=3)
    end_time = now_utc + timedelta(hours=6)

    resp_sht = client.post(
        "/api/admin/movies/showtimes",
        headers=admin_hdr,
        json={
            "movieId": movie_id,
            "cinemaId": cinema_id,
            "hallId": hall_id,
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "price": 5000,  # 50元
            "originalPrice": 8000,
            "languageVersion": "英语原版 3D",
        },
    )
    assert resp_sht.status_code == 201
    showtime = resp_sht.json()["data"]
    showtime_id = showtime["showtimeId"]

    # 4.1 测试排片时间冲突校验
    resp_conflict = client.post(
        "/api/admin/movies/showtimes",
        headers=admin_hdr,
        json={
            "movieId": movie_id,
            "cinemaId": cinema_id,
            "hallId": hall_id,
            # 与上一场时间部分交叉
            "startTime": (start_time + timedelta(hours=1)).isoformat(),
            "endTime": (end_time + timedelta(hours=1)).isoformat(),
            "price": 4000,
            "originalPrice": 6000,
            "languageVersion": "国语 3D",
        },
    )
    assert resp_conflict.status_code == 400
    assert "排片时间与该影厅的已有放映场次存在冲突" in resp_conflict.json()["message"]

    # 5. 用户端浏览上映电影与影院排片
    resp_movies = client.get("/api/movie/movies?status=showing")
    assert resp_movies.status_code == 200
    assert len(resp_movies.json()["data"]["list"]) >= 1

    resp_cinemas = client.get(f"/api/movie/cinemas?movieId={movie_id}&city=杭州")
    assert resp_cinemas.status_code == 200
    assert len(resp_cinemas.json()["data"]["list"]) >= 1

    resp_shows = client.get(f"/api/movie/cinemas/{cinema_id}/showtimes?movieId={movie_id}")
    assert resp_shows.status_code == 200
    assert len(resp_shows.json()["data"]) >= 1

    # 6. 用户端选座流程 - Alice 锁定 5排6座
    # 6.1 查看初始座位图，应全部可选
    resp_seats_init = client.get(f"/api/movie/showtimes/{showtime_id}/seats")
    assert resp_seats_init.status_code == 200
    seats_data = resp_seats_init.json()["data"]
    assert seats_data["rows"] == 8
    assert seats_data["cols"] == 10
    assert seats_data["brokenSeats"] == ["1-1", "1-2"]
    assert len(seats_data["occupiedSeats"]) == 0

    # 6.2 锁定座位下单
    resp_order_a = client.post(
        "/api/movie/orders",
        headers=headers_alice,
        json={
            "showtimeId": showtime_id,
            "seats": [{"row": 5, "col": 6, "name": "5排6座"}],
        },
    )
    assert resp_order_a.status_code == 201
    order_a = resp_order_a.json()["data"]
    assert order_a["payStatus"] == "pending_pay"
    assert order_a["pricePaid"] == 5000
    order_a_id = order_a["orderId"]

    # 6.3 Bob 尝试购买 5排6座，应当报错拦截
    resp_order_b = client.post(
        "/api/movie/orders",
        headers=headers_bob,
        json={
            "showtimeId": showtime_id,
            "seats": [{"row": 5, "col": 6, "name": "5排6座"}],
        },
    )
    assert resp_order_b.status_code == 400
    assert "已被其他用户选定" in resp_order_b.json()["message"]

    # 6.4 Bob 获取座位图，验证 5-6 已被占用
    resp_seats_bob = client.get(f"/api/movie/showtimes/{showtime_id}/seats")
    assert resp_seats_bob.status_code == 200
    assert "5-6" in resp_seats_bob.json()["data"]["occupiedSeats"]

    # 7. 模拟支付与出票票根
    resp_pay = client.post(f"/api/movie/orders/{order_a_id}/pay", headers=headers_alice)
    assert resp_pay.status_code == 200
    order_a_paid = resp_pay.json()["data"]
    assert order_a_paid["payStatus"] == "paid"
    assert order_a_paid["ticketCode"] is not None
    assert len(order_a_paid["ticketCode"]) == 12

    # 8. 用户查看“我的电影票根”
    resp_my = client.get("/api/movie/orders/my", headers=headers_alice)
    assert resp_my.status_code == 200
    assert resp_my.json()["data"]["total"] == 1
    assert resp_my.json()["data"]["list"][0]["payStatus"] == "paid"

    # 9. 超时自动释放测试
    # 9.1 Bob 抢占 4排4座
    resp_order_b2 = client.post(
        "/api/movie/orders",
        headers=headers_bob,
        json={
            "showtimeId": showtime_id,
            "seats": [{"row": 4, "col": 4, "name": "4排4座"}],
        },
    )
    assert resp_order_b2.status_code == 201
    order_b2_id = resp_order_b2.json()["data"]["orderId"]

    # 9.2 在数据库中将 Bob 的锁定时间修改为超时
    db = SessionLocal()
    o = db.query(MovieTicketOrder).filter(MovieTicketOrder.order_id == order_b2_id).first()
    o.expire_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    # 9.3 Alice 再次读取座位图（触发过期清理）
    resp_seats_alice = client.get(f"/api/movie/showtimes/{showtime_id}/seats")
    assert resp_seats_alice.status_code == 200
    occupied = resp_seats_alice.json()["data"]["occupiedSeats"]
    # 4-4 应当被释放出来，仅包含 5-6 (因为 5-6 已支付成功)
    assert "4-4" not in occupied
    assert "5-6" in occupied

    # 9.4 校验后台统计面板
    resp_stats = client.get("/api/admin/movies/stats", headers=admin_hdr)
    assert resp_stats.status_code == 200
    stats = resp_stats.json()["data"]
    # 累计总票房应该是 5000 (因为 Alice 的 5-6 支付成功)
    assert stats["totalBoxOffice"] == 5000
    assert stats["totalTicketsSold"] == 1
    # 包含 Alice(paid) + Bob 锁定后超时(cancelled) = 2 笔非物理删除的订单
    assert stats["totalOrders"] == 2
