# -*- coding: utf-8 -*-
"""
AccountPackConfig 模型

记录账号在不同类型任务下的目标卡包设置。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AccountPackConfig(SQLModel, table=True):
    """
    账号开包配置模型

    记录账号在不同类型任务下的目标卡包设置。

    字段说明：
    - type: 配置类型（如 daily）
    - pack_code: 卡包系列编码（如 A1, A1a）
    - booster_name: 子包名称（用于模板目录）
    """

    __tablename__ = "account_pack_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    type: str
    pack_code: str
    booster_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "type": self.type,
            "pack_code": self.pack_code,
            "booster_name": self.booster_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
