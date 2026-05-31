from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    error_schema = {
        "properties": {
            "code": {"type": "integer", "title": "业务状态码", "description": "HTTP/业务错误状态码"},
            "message": {"type": "string", "title": "错误提示", "description": "错误原因说明"},
            "data": {"type": "object", "title": "错误数据", "description": "错误附加信息"},
        },
        "type": "object",
        "required": ["code", "message", "data"],
        "title": "统一错误响应",
    }
    openapi_schema.setdefault("components", {}).setdefault("schemas", {})["HTTPValidationError"] = error_schema

    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses", {})
            if "422" in responses:
                responses["422"] = {
                    "description": "请求参数校验失败",
                    "content": {"application/json": {"schema": error_schema}},
                }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


ERROR_MESSAGE_MAP = {
    "Not authenticated": "未登录，请先登录",
    "Invalid or expired token": "登录已过期或无效",
    "Post not found": "内容未找到",
    "Only author can edit": "仅发布者可以编辑",
    "Only author can delete": "仅发布者可以删除",
}


def error_response(exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        message = str(exc.detail.get("message") or exc.detail.get("detail") or "请求失败")
        data = exc.detail.get("data", {})
        code = int(exc.detail.get("code") or exc.status_code)
    else:
        message = ERROR_MESSAGE_MAP.get(str(exc.detail), str(exc.detail or "请求失败"))
        data = {}
        code = exc.status_code
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": message, "data": data},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return error_response(exc)


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数校验失败",
            "data": {"errors": exc.errors()},
        },
    )


@app.get("/health", tags=["系统"], summary="健康检查", description="检查后端服务是否正常运行。")
def health() -> dict[str, str]:
    return {"status": "ok"}
