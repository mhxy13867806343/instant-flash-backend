from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.messages import router as messages_router
from app.api.posts import router as posts_router
from app.api.users import router as users_router
from app.core.config import settings

openapi_tags = [
    {"name": "后台管理", "description": "后台管理系统接口：登录、看板、用户、内容、评论、协议"},
    {"name": "鉴权登录", "description": "用户端登录、微信登录、开发调试 Token"},
    {"name": "用户端内容", "description": "内容列表、详情、发布、编辑、点赞、评论、分享"},
    {"name": "用户端用户", "description": "当前登录用户资料和我的内容"},
    {"name": "用户端消息", "description": "当前登录用户消息中心"},
    {"name": "系统", "description": "健康检查等系统接口"},
]

app = FastAPI(
    title="即闪后端 API 服务",
    description="即闪用户端与后台管理系统共用的 FastAPI 后端接口文档。",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(users_router)
app.include_router(messages_router)


@app.get("/health", tags=["系统"], summary="健康检查", description="检查后端服务是否正常运行。")
def health() -> dict[str, str]:
    return {"status": "ok"}
