"""@好友提到我提醒系统核心逻辑。

解析文本中携带的 @用户名（@昵称），结合外部传入的被@用户ID，
自动在 messages 表中向被@的用户推送通知，通知类型为 "mention"。
"""

from __future__ import annotations

import re
from sqlalchemy.orm import Session

from app.api.utils import new_business_id
from app.models.message import Message
from app.models.user import User

# 正则匹配 @昵称，支持中英文、数字、下划线
MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_\u4e00-\u9fa5]{2,64})")


def extract_mentioned_nicknames(text: str) -> list[str]:
    """从文本中提取被 @ 的昵称列表。"""
    if not text:
        return []
    return MENTION_PATTERN.findall(text)


def notify_mentions(
    db: Session,
    sender_id: str,
    text: str,
    extra_user_ids: list[str] | None = None,
    source_type: str = "post",  # post / comment / aigc_comment / chat / group_chat
    source_id: str | None = None,  # post_id / comment_id / session_id / group_id
) -> list[str]:
    """处理 @ 提到用户通知。

    1. 解析文本中的 @昵称，查找对应的用户ID。
    2. 结合 extra_user_ids。
    3. 去重（且过滤掉发件人自己）。
    4. 创建一条类型为 "mention" 的 Message 记录存入数据库。
    返回成功发送通知的用户ID列表。
    """
    sender = db.query(User).filter(User.user_id == sender_id).first()
    sender_name = sender.nickname if sender else "某人"

    # 1. 解析 @昵称
    nicknames = extract_mentioned_nicknames(text)
    user_ids = []
    if nicknames:
        matched_users = db.query(User.user_id).filter(
            User.nickname.in_(nicknames),
            User.is_active.is_(True),
        ).all()
        user_ids.extend([u.user_id for u in matched_users])

    # 2. 结合显式传入的 ID
    if extra_user_ids:
        user_ids.extend(extra_user_ids)

    # 3. 去重并过滤自己
    target_ids = list(set([uid for uid in user_ids if uid and uid != sender_id]))
    if not target_ids:
        return []

    # 验证这些用户是否真实存在且激活
    valid_users = db.query(User.user_id).filter(
        User.user_id.in_(target_ids),
        User.is_active.is_(True)
    ).all()
    valid_ids = [u.user_id for u in valid_users]

    # 4. 创建消息并存入数据库
    title = f"{sender_name} @了你"

    # 截取文本内容作为通知预览，最大 200 字
    summary = text[:200] + "..." if len(text) > 200 else text

    post_id = None
    comment_id = None

    if source_type in ("post", "comment", "aigc_comment"):
        if source_type == "post":
            post_id = source_id
        else:
            comment_id = source_id

    for uid in valid_ids:
        msg = Message(
            message_id=new_business_id("ntf"),
            user_id=uid,
            sender_id=sender_id,
            type="mention",
            title=title,
            content=summary,
            post_id=post_id,
            comment_id=comment_id,
            is_read=False,
        )
        db.add(msg)

    db.flush()
    return valid_ids
