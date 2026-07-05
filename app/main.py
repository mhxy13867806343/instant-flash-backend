from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.agreements import legacy_router as agreements_legacy_router
from app.api.agreements import router as agreements_router
from app.api.agreements import user_router as agreements_user_router
from app.api.address import router as address_router
from app.api.admin import router as admin_router
from app.api.admin_points import router as admin_points_router
from app.api.admin_mall import router as admin_mall_router
from app.api.admin_wallet import router as admin_wallet_router
from app.api.auth import router as auth_router
from app.api.feedback import router as feedback_router
from app.api.locations import router as locations_router
from app.api.mall import router as mall_router
from app.api.messages import router as messages_router
from app.api.points import router as points_router
from app.api.posts import router as posts_router
from app.api.topics import tags_router, topics_router
from app.api.uploads import router as uploads_router
from app.api.users import router as users_router
from app.api.wallet import router as wallet_router
from app.core.config import settings
from app.core.operation_log import record_operation_log, resolve_actor, should_skip_log
from app.core.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

openapi_tags = [
    {"name": "后台管理", "description": "后台管理系统接口：登录、看板、用户、内容、评论、协议"},
    {"name": "鉴权登录", "description": "用户端登录、微信登录、开发调试 Token"},
    {"name": "用户端商城", "description": "商品浏览、下单、支付、订单查询（移动端）"},
    {"name": "用户端内容", "description": "内容列表、详情、发布、编辑、点赞、评论、分享"},
    {"name": "用户端话题", "description": "用户端推荐话题和话题搜索"},
    {"name": "用户端位置", "description": "根据经纬度获取附近发布位置候选"},
    {"name": "用户端上传", "description": "用户端发布动态图片和视频上传"},
    {"name": "用户端反馈", "description": "用户端动态反馈表单和反馈提交"},
    {"name": "用户端协议", "description": "用户端隐私协议和用户协议"},
    {"name": "用户端用户", "description": "当前登录用户资料和我的内容"},
    {"name": "用户端积分", "description": "当前登录用户积分概览、明细、签到与邀请奖励"},
    {"name": "用户端消息", "description": "当前登录用户消息中心"},
    {"name": "公共地区", "description": "PC 后台和用户端共用的省市区三级地区数据"},
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

app.include_router(address_router)
app.include_router(admin_router)
app.include_router(admin_points_router)
app.include_router(admin_mall_router)
app.include_router(admin_wallet_router)
app.include_router(auth_router)
app.include_router(mall_router)
app.include_router(points_router)
app.include_router(wallet_router)
app.include_router(posts_router)
app.include_router(topics_router)
app.include_router(tags_router)
app.include_router(locations_router)
app.include_router(uploads_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(feedback_router)
app.include_router(agreements_router)
app.include_router(agreements_legacy_router)
app.include_router(agreements_user_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    result = check_rate_limit(request)
    if not result.allowed:
        status_code = 403 if result.rule_id else 429
        headers: dict[str, str] = {}
        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)
        if result.limit:
            headers["X-RateLimit-Limit"] = str(result.limit)
            headers["X-RateLimit-Remaining"] = str(max(0, result.limit - result.current))
        return JSONResponse(
            status_code=status_code,
            content={
                "code": status_code,
                "message": result.message,
                "data": {
                    "limit": result.limit,
                    "current": result.current,
                    "retryAfter": result.retry_after,
                    "ruleId": result.rule_id,
                },
            },
            headers=headers,
        )
    response = await call_next(request)
    if result.limit:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, result.limit - result.current))
    return response


@app.middleware("http")
async def operation_log_middleware(request: Request, call_next) -> Response:
    if should_skip_log(request.url.path):
        return await call_next(request)
    actor = resolve_actor(request)
    response = await call_next(request)
    if actor is not None:
        record_operation_log(request, response, actor)
    return response


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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": {}},
    )


@app.get("/", tags=["系统"], summary="API 服务首页", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>即闪后端 API 服务</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --primary: #2563eb;
      --primary-dark: #1e40af;
      --text: #172033;
      --muted: #64748b;
      --border: #dbe3ef;
      --soft: #eef5ff;
      --code: #0f172a;
      --ok: #0f9f6e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.7;
    }
    .hero {
      background: linear-gradient(135deg, #163b7a 0%, #2563eb 52%, #15a3a3 100%);
      color: #fff;
      padding: 56px 24px 42px;
    }
    .wrap {
      width: min(1120px, calc(100% - 40px));
      margin: 0 auto;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border: 1px solid rgba(255,255,255,.35);
      border-radius: 999px;
      background: rgba(255,255,255,.12);
      font-size: 14px;
    }
    h1 {
      margin: 18px 0 12px;
      font-size: clamp(32px, 5vw, 56px);
      line-height: 1.1;
      letter-spacing: 0;
    }
    .hero p {
      max-width: 760px;
      margin: 0;
      color: rgba(255,255,255,.88);
      font-size: 18px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 28px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 9px 16px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,.45);
      color: #fff;
      text-decoration: none;
      font-weight: 700;
      background: rgba(255,255,255,.12);
    }
    .btn.primary {
      border-color: #fff;
      background: #fff;
      color: var(--primary-dark);
    }
    main {
      padding: 30px 0 52px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: -54px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 14px 34px rgba(15, 23, 42, .08);
    }
    .card h2, .section h2 {
      margin: 0 0 10px;
      font-size: 20px;
      letter-spacing: 0;
    }
    .card p, .section p, li {
      color: var(--muted);
    }
    .section {
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 24px;
    }
    .routes {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .route {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      background: #fbfdff;
    }
    code {
      display: inline-block;
      color: var(--code);
      background: #eef2f7;
      border-radius: 6px;
      padding: 2px 7px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: .92em;
    }
    pre {
      overflow: auto;
      margin: 12px 0 0;
      padding: 14px;
      border-radius: 8px;
      color: #dbeafe;
      background: #0f172a;
      line-height: 1.55;
    }
    pre code {
      display: block;
      padding: 0;
      color: inherit;
      background: transparent;
    }
    .status {
      color: var(--ok);
      font-weight: 700;
    }
    .footer {
      margin-top: 22px;
      color: var(--muted);
      font-size: 14px;
      text-align: center;
    }
    @media (max-width: 820px) {
      .grid, .routes { grid-template-columns: 1fr; }
      .hero { padding-top: 40px; }
      .grid { margin-top: -28px; }
      .wrap { width: min(100% - 24px, 1120px); }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <span class="badge">服务状态 <strong>运行中</strong></span>
      <h1>即闪后端 API 服务</h1>
      <p>这是即闪用户端和后台管理系统共用的接口服务，提供内容发布、首页列表、点赞评论分享、消息中心、个人资料、后台审核与协议维护等能力。</p>
      <div class="actions">
        <a class="btn primary" href="/docs">打开 Swagger 文档</a>
        <a class="btn" href="/redoc">查看 ReDoc</a>
        <a class="btn" href="/health">健康检查</a>
        <a class="btn" href="/openapi.json">OpenAPI JSON</a>
      </div>
    </div>
  </header>

  <main class="wrap">
    <section class="grid" aria-label="服务概览">
      <article class="card">
        <h2>技术栈</h2>
        <p>Python、FastAPI、PostgreSQL、SQLAlchemy ORM、Alembic、Pydantic、JWT、Uvicorn。</p>
      </article>
      <article class="card">
        <h2>数据约定</h2>
        <p>前端请求和响应字段统一使用驼峰命名，例如 <code>postId</code>、<code>userId</code>、<code>pageSize</code>。</p>
      </article>
      <article class="card">
        <h2>响应格式</h2>
        <p>错误响应统一为 <code>{"code":401,"message":"未登录，请先登录","data":{}}</code>，不直接暴露 FastAPI 默认 <code>detail</code>。</p>
      </article>
    </section>

    <section class="section">
      <h2>怎么使用</h2>
      <p>公开接口可以直接访问；需要登录的接口在请求头中传入 JWT。</p>
      <pre><code>Authorization: Bearer &lt;token&gt;</code></pre>
      <p>用户端调试可先调用 <code>POST /api/auth/dev-token</code> 获取 token；正式微信登录调用 <code>POST /api/auth/wx-login</code>。后台登录调用 <code>POST /api/admin/auth/login</code>，演示账号为 <code>admin / 123456</code>。</p>
    </section>

    <section class="section">
      <h2>主要接口</h2>
      <div class="routes">
        <div class="route"><strong>内容列表</strong><br><code>GET /api/posts</code><br>首页内容流，登录后会返回是否点赞、是否本人发布等状态。</div>
        <div class="route"><strong>内容详情</strong><br><code>GET /api/posts/{postId}</code><br>查看单条内容，支持可选 token 识别当前用户。</div>
        <div class="route"><strong>发布内容</strong><br><code>POST /api/posts</code><br>登录用户发布图文内容，发布人从 token 获取。</div>
        <div class="route"><strong>点赞与评论</strong><br><code>POST /api/posts/{postId}/like</code><br><code>POST /api/posts/{postId}/comments</code></div>
        <div class="route"><strong>我的资料</strong><br><code>GET /api/user/profile</code><br><code>PUT /api/user/profile</code></div>
        <div class="route"><strong>消息中心</strong><br><code>GET /api/messages</code><br>查看当前登录用户收到的点赞、评论、回复等消息。</div>
        <div class="route"><strong>后台看板</strong><br><code>GET /api/admin/dashboard/metrics</code><br>统计用户、内容、评论和点赞数据。</div>
        <div class="route"><strong>后台管理</strong><br><code>/api/admin/users</code>、<code>/api/admin/posts</code>、<code>/api/admin/comments</code>、<code>/api/admin/agreement/{agreementType}</code></div>
        <div class="route"><strong>三级地区</strong><br><code>GET /api/address/tree</code><br>PC 后台和用户端共用，返回省市区三级树。</div>
        <div class="route"><strong>系统配置</strong><br><code>/api/admin/tags</code>、<code>/api/admin/regions</code><br>标签管理和地区管理。</div>
        <div class="route"><strong>字典与消息</strong><br><code>/api/admin/dictionaries</code>、<code>/api/admin/system-messages</code><br>字典管理和系统消息管理。</div>
      </div>
    </section>

    <section class="section">
      <h2>快速自检</h2>
      <p>当前服务首页已正常响应；可访问 <a href="/health">/health</a> 查看健康状态，返回 <code>{"status":"ok"}</code> 表示服务可用。</p>
      <p class="status">PostgreSQL + SQLAlchemy ORM 是当前后端数据访问方案。</p>
    </section>

    <p class="footer">即闪后端 API 服务 · 本地地址 http://localhost:8000</p>
  </main>
</body>
</html>
"""


@app.head("/", include_in_schema=False)
def index_head() -> Response:
    return Response(status_code=200, media_type="text/html")


@app.get("/health", tags=["系统"], summary="健康检查", description="检查后端服务是否正常运行。")
def health() -> dict[str, str]:
    return {"status": "ok"}
