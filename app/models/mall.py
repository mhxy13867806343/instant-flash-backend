from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class MallSetting(TimestampMixin, Base):
    """商城全局设置表（单行，id=1）。"""

    __tablename__ = "mall_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 积分开关：True = 仅积分支付，不允许价格支付
    points_switch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class MallProduct(TimestampMixin, Base):
    """商城商品表。"""

    __tablename__ = "mall_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 支持富文本 HTML
    # 商品图片列表，最多 9 张，JSON 数组存 URL
    images: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )
    cover_image: Mapped[str | None] = mapped_column(String(512), nullable=True)   # 封面图（可选）
    cover_video: Mapped[str | None] = mapped_column(String(512), nullable=True)   # 封面视频（可选，与封面图二选一）
    # 价格（单位：分）
    original_price: Mapped[int] = mapped_column(Integer, nullable=False)           # 原价（分），> 0
    current_price: Mapped[int] = mapped_column(Integer, nullable=False)            # 现价（分），> 0
    points_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # 积分兑换价，0=不支持积分
    points_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否仅积分购买
    stock: Mapped[int] = mapped_column(Integer, default=1, nullable=False)         # 库存 1~999
    sold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)    # 累计销量
    # 状态：on_sale 上架 / off_shelf 下架 / sold_out 售罄
    status: Mapped[str] = mapped_column(String(32), default="off_shelf", nullable=False, index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 扩展属性
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_top10: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_today: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    allow_multiple_purchase: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_time_slot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    time_slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_cloned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    clone_url: Mapped[str | None] = mapped_column(String(512), nullable=True)



class MallOrder(TimestampMixin, Base):
    """商城订单表。"""

    __tablename__ = "mall_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # 下单时的快照，防止商品修改后历史订单数据错乱
    product_title: Mapped[str] = mapped_column(String(128), nullable=False)
    product_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)    # 成交单价（分）
    total_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # 总价（分）
    points_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # 使用积分数
    pay_type: Mapped[str | None] = mapped_column(String(32), nullable=True)        # wechat/alipay/points 等
    pay_type_value: Mapped[str | None] = mapped_column(String(256), nullable=True) # 支付附加参数快照
    # 订单状态：pending_pay / paid / shipped / completed / cancelled
    status: Mapped[str] = mapped_column(String(32), default="pending_pay", nullable=False, index=True)
    paid_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shipped_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cancelled_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 扩展字段
    expire_at: Mapped[str | None] = mapped_column(String(32), nullable=True)       # 待支付超时时间（ISO字符串）
    user_remark: Mapped[str | None] = mapped_column(String(256), nullable=True)    # 用户下单留言
    receiver_name: Mapped[str | None] = mapped_column(String(64), nullable=True)   # 收件人姓名
    receiver_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 收件人手机号
    receiver_address: Mapped[str | None] = mapped_column(String(512), nullable=True) # 收件详细地址
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True) # 分享Token
    is_commented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # 是否已评价






class MallPaymentMethod(TimestampMixin, Base):
    """支付方式表，PC 端可自定义配置，默认预置微信和支付宝。"""

    __tablename__ = "mall_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    method_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)              # 展示名称，如"微信支付"
    logo: Mapped[str | None] = mapped_column(String(512), nullable=True)      # logo 图片 URL
    type: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # 唯一标识，前端传此值
    type_value: Mapped[str | None] = mapped_column(String(256), nullable=True) # 附加参数（商户号/AppID等）
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class MallProductComment(TimestampMixin, Base):
    """商品评价/评论表。"""

    __tablename__ = "mall_product_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)  # 限制一个订单评价一次
    product_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 评分 1-5 星
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 评价详情内容
    images: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )  # 晒图图片列表，JSON 数组
    status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False, index=True)  # approved 审核显示 / pending 待审核 / hidden 隐藏

    # 追加评价列表（按时间正序排列，支持多次追加评论）
    appends: Mapped[list[MallProductCommentAppend]] = relationship(
        "MallProductCommentAppend",
        back_populates="comment",
        cascade="all, delete-orphan",
        order_by="MallProductCommentAppend.create_time",
    )


class MallProductCommentAppend(TimestampMixin, Base):
    """商品追加评价表（支持多次追加）。"""

    __tablename__ = "mall_product_comment_appends"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    append_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    comment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("mall_product_comments.comment_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    images: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )  # 晒图
    status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False, index=True)

    comment: Mapped[MallProductComment] = relationship(
        "MallProductComment",
        back_populates="appends",
    )


class MallProductLike(TimestampMixin, Base):
    """商品点赞表。"""

    __tablename__ = "mall_product_likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mall_products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_mall_product_likes_user_product"),
    )


class MallProductFavorite(TimestampMixin, Base):
    """商品收藏表。"""

    __tablename__ = "mall_product_favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mall_products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_mall_product_favorites_user_product"),
    )


class MallProductShare(TimestampMixin, Base):
    """商品分享记录表。"""

    __tablename__ = "mall_product_shares"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=True
    )  # 允许未登录匿名分享
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mall_products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)  # wechat/alipay/moments等


class MallOrderLogisticsStep(TimestampMixin, Base):
    """订单物流轨迹表。"""

    __tablename__ = "mall_order_logistics_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    logistics_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mall_orders.order_id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_time: Mapped[str] = mapped_column(String(32), nullable=False)  # ISO 时间字符串，如 "2026-07-06T12:00:00Z"
    content: Mapped[str] = mapped_column(String(256), nullable=False)  # 轨迹内容描述，如 "您的订单已揽收"


class MallCustomerService(TimestampMixin, Base):
    """客服配置表（可动态配置多个客服）。"""

    __tablename__ = "mall_customer_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cs_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # 客服展示名称
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 客服头像 URL
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)  # active 启用 / inactive 停用
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MallChatSession(TimestampMixin, Base):
    """聊天会话表。"""

    __tablename__ = "mall_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False)
    cs_id: Mapped[str] = mapped_column(String(64), ForeignKey("mall_customer_services.cs_id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 带入的商品ID，进入对话时关联的商品
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MallChatMessage(TimestampMixin, Base):
    """聊天消息表。"""

    __tablename__ = "mall_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mall_chat_sessions.session_id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False)  # user / cs
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)  # text / bargain / image
    bargain_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)  # 关联还价记录


class MallProductBargain(TimestampMixin, Base):
    """商品还价申请表。"""

    __tablename__ = "mall_product_bargains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bargain_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("mall_products.product_id", ondelete="CASCADE"), index=True, nullable=False)
    original_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 原价(现价)，单位：分
    bargain_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 用户还价出价，单位：分
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)  # pending 待审核 / approved 同意还价 / rejected 拒绝 / used 已下单使用




