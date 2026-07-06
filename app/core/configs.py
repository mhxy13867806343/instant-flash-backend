"""共用常量集中定义。

集中管理散落在各处的"魔法值"，便于统一维护。
本模块不依赖任何 app 内部模块，可被任意层安全导入（无循环依赖风险）。
"""

from __future__ import annotations

# ==================== 扫码登录（PC）====================

# 二维码有效期（秒）
QR_TTL_SECONDS = 120

# 二维码状态常量
STATUS_PENDING = "pending"      # 已生成，等待扫码
STATUS_SCANNED = "scanned"      # 已被 App 扫码，等待确认
STATUS_CONFIRMED = "confirmed"  # 已确认登录
STATUS_CANCELLED = "cancelled"  # 已取消
STATUS_EXPIRED = "expired"      # 已过期（Redis key 消失时的兜底返回值）

# 二维码内容协议前缀，前端据此渲染二维码图片
QR_CONTENT_SCHEME = "ifqr://login"

# 扫码登录会话在 Redis 中的 key 模板
# 使用方式：QR_REDIS_KEY_TEMPLATE.format(prefix=<业务前缀>, qr_id=<二维码 ID>)
QR_REDIS_KEY_TEMPLATE = "{prefix}:auth:qrlogin:{qr_id}"

# ==================== 令牌 ====================

# JWT 令牌类型，作为各登录接口响应 tokenType 的固定值
TOKEN_TYPE_BEARER = "Bearer"

# ==================== 统一响应 ====================

# 业务成功码，统一响应结构 {"code", "message", "data"} 中 code 的成功值
CODE_SUCCESS = 200

# 统一响应默认成功提示
MESSAGE_SUCCESS = "success"

# ==================== 客户端类型 ====================

CLIENT_TYPE_PC = "pc"                    # PC / 网页端
CLIENT_TYPE_H5 = "h5"                    # 移动端 H5
CLIENT_TYPE_MINIPROGRAM = "miniprogram"  # 小程序

# ==================== 位置服务（天地图）====================

# 天地图 POI 搜索接口
TIANDITU_SEARCH_URL = "https://api.tianditu.gov.cn/v2/search"
# 天地图逆地理编码接口
TIANDITU_GEOCODER_URL = "https://api.tianditu.gov.cn/geocoder"
# 附近地点默认检索关键词
DEFAULT_LOCATION_KEYWORDS = ("商场", "广场", "购物", "大厦", "公园", "地铁")
