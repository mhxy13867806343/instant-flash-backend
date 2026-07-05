from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserCustomConfigCreate(BaseModel):
    """新增用户自定义配置请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    config_key: str = Field(
        alias="configKey",
        validation_alias=AliasChoices("configKey", "config_key", "key"),
        max_length=128,
        title="配置键名",
        description="配置键名，如 theme_color、page_decoration，同一用户下不重复",
    )
    config_value: Any = Field(
        default=None,
        alias="configValue",
        validation_alias=AliasChoices("configValue", "config_value", "value"),
        title="配置值",
        description="配置值，支持任意 JSON 类型（字符串、数字、对象、数组），默认为空",
    )
    label: str | None = Field(
        default=None,
        max_length=128,
        title="展示名称",
        description="可选：前端展示名称，如「主题色」",
    )
    remark: str | None = Field(
        default=None,
        title="备注",
        description="可选：备注说明",
    )


class UserCustomConfigUpdate(BaseModel):
    """修改用户自定义配置请求体，所有字段均为可选。"""

    model_config = ConfigDict(populate_by_name=True)

    config_value: Any = Field(
        default=None,
        alias="configValue",
        validation_alias=AliasChoices("configValue", "config_value", "value"),
        title="配置值",
        description="更新后的配置值，支持任意 JSON 类型",
    )
    label: str | None = Field(
        default=None,
        max_length=128,
        title="展示名称",
        description="可选：前端展示名称",
    )
    remark: str | None = Field(
        default=None,
        title="备注",
        description="可选：备注说明",
    )


class UserCustomConfigOut(BaseModel):
    """用户自定义配置响应体，使用驼峰命名。"""

    model_config = ConfigDict(from_attributes=True)

    configId: str = Field(title="配置 ID", description="业务唯一配置 ID")
    userId: str = Field(title="用户 ID", description="所属用户的业务 user_id")
    configKey: str = Field(title="配置键名", description="配置键名")
    configValue: Any = Field(default=None, title="配置值", description="配置值，任意 JSON 类型，默认为空")
    label: str | None = Field(default=None, title="展示名称", description="前端展示名称")
    remark: str | None = Field(default=None, title="备注", description="备注说明")
    createTime: datetime = Field(title="创建时间", description="配置创建时间")
    updateTime: datetime = Field(title="更新时间", description="配置最近更新时间")


class UserCustomConfigListResponse(BaseModel):
    """用户自定义配置列表响应体。"""

    items: list[UserCustomConfigOut] = Field(title="配置列表", description="当前用户所有自定义配置项")
    total: int = Field(title="总数", description="配置总条数")
