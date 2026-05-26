# 即闪后端 API 服务

即闪后端是基于 FastAPI 的内容社区接口服务，覆盖内容发布、首页列表、详情、点赞、评论、分享、个人资料和消息列表等用户端能力。

[English](./README.en.md)

## 技术栈

Python、FastAPI、PostgreSQL、SQLAlchemy ORM、Alembic、Pydantic、JWT、Uvicorn。

## 功能

- 内容：发布、编辑、删除、详情、首页列表
- 用户：我的资料、编辑资料、我的发布、我的点赞、我的评论、我的分享
- 互动：点赞/取消点赞、评论/回复、分享记录
- 消息：当前登录用户的消息列表
- 鉴权：`Authorization: Bearer <token>`，后端从 token 识别当前用户

## 快速启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

默认 `.env.example` 使用本机 PostgreSQL：

```text
postgresql+psycopg://hooksvue@127.0.0.1:5432/instant_flash
```

如果本机用户名或数据库配置不同，请修改 `.env` 中的 `DATABASE_URL`。

## 数据库迁移

```bash
alembic upgrade head
```

迁移会创建以下数据表：

- `users`
- `posts`
- `comments`
- `post_likes`
- `post_shares`
- `messages`

## 接口文档

启动服务后访问：

```text
http://127.0.0.1:8000/docs
```

## 鉴权说明

需要登录的接口必须携带：

```text
Authorization: Bearer <token>
```

token 的 `sub` 保存业务用户 ID。开发联调时可以调用：

```text
POST /api/auth/dev-token
```

该接口会创建或更新测试用户，并返回可用于联调的访问 token。

## 测试

```bash
pytest -q
```

## License

[MIT](./LICENSE)
