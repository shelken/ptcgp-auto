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
    - pack_code: 数据库存储字段，表示系列代码（如 A1, A1a）
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

    @property
    def set_code(self) -> str:
        """业务语义中的系列代码。"""
        return self.pack_code

    @set_code.setter
    def set_code(self, value: str) -> None:
        """将业务语义 set_code 映射回数据库字段。"""
        self.pack_code = value

    @classmethod
    def create_daily(cls, account_id: int, set_code: str, booster_name: str) -> "AccountPackConfig":
        """按业务语义构建每日开包配置。"""
        return cls(
            account_id=account_id,
            type="daily",
            pack_code=set_code,
            booster_name=booster_name,
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "type": self.type,
            "set_code": self.set_code,
            "booster_name": self.booster_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
