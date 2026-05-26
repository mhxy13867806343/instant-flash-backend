# Instant Flash Backend

Instant Flash Backend is a FastAPI service for a lightweight content community. It provides APIs for posts, feeds, post details, likes, comments, shares, user profiles, and messages.

[中文文档](./README.md)

## Stack

Python, FastAPI, PostgreSQL, SQLAlchemy ORM, Alembic, Pydantic, JWT, Uvicorn.

## Features

- Posts: create, update, delete, detail, and feed list
- User: profile, profile update, my posts, my likes, my comments, my shares
- Interactions: like/unlike, comments/replies, share records
- Messages: current user's message list
- Auth: `Authorization: Bearer <token>`, with the current user resolved on the backend

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The default `.env.example` uses the local PostgreSQL server:

```text
postgresql+psycopg://hooksvue@127.0.0.1:5432/instant_flash
```

If your local username or database settings differ, update `DATABASE_URL` in `.env`.

## Database Migration

```bash
alembic upgrade head
```

The migration creates these tables:

- `users`
- `posts`
- `comments`
- `post_likes`
- `post_shares`
- `messages`

## API Docs

After starting the service, open:

```text
http://127.0.0.1:8000/docs
```

## Auth

Authenticated endpoints require:

```text
Authorization: Bearer <token>
```

The token stores the business user id in `sub`. For local integration testing, call:

```text
POST /api/auth/dev-token
```

This helper creates or updates a test user and returns an access token.

## Tests

```bash
pytest -q
```

## License

[MIT](./LICENSE)
