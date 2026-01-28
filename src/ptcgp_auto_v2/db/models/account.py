# -*- coding: utf-8 -*-
"""
Account 模型

表示一个游戏账号，是任务状态的主体。
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .pack_record import PackRecord
    from .task_instance import TaskInstance
    from .task_plan import TaskPlan
    from .account_task_plan import AccountTaskPlan


class Account(SQLModel, table=True):
    """
    账号模型

    表示一个游戏账号，是任务状态的主体。

    字段说明：
    - game_id: 设备账号 ID（来自 XML deviceAccount 字段），唯一标识符
    - friend_id: 游戏内朋友 ID（格式 XXXX-XXXX-XXXX-XXXX），用户可见
    - nintendo_id: Nintendo 账号 ID（从 JWT 解析）
    - nickname: 用户昵称
    - country: 国家/地区代码（从 JWT 解析）
    - xml_content: 账号 XML 文件内容（用于账号切换）
    - session_token_iat: sessionToken 的 iat 字段（签发时间戳）
    """

    __tablename__ = "accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(unique=True, description="deviceAccount 字段，唯一标识")
    friend_id: Optional[str] = Field(
        default=None, description="朋友 ID，格式 XXXX-XXXX-XXXX-XXXX"
    )
    nintendo_id: Optional[str] = Field(default=None, description="Nintendo 账号 ID")
    nickname: Optional[str] = None
    level: Optional[int] = None
    exchange_points: Optional[int] = None
    country: Optional[str] = Field(default=None, description="国家/地区代码")
    xml_content: Optional[bytes] = Field(default=None, description="XML 文件内容")
    session_token_iat: Optional[int] = None
    remark: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 关系
    # 新的多对多关系（通过关联表）
    task_plan_associations: List["AccountTaskPlan"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "all, delete",
            "primaryjoin": "Account.id==AccountTaskPlan.account_id",
            "foreign_keys": "[AccountTaskPlan.account_id]",
        }
    )
    task_instances: List["TaskInstance"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={
            "primaryjoin": "Account.id==TaskInstance.account_id",
            "foreign_keys": "[TaskInstance.account_id]",
        },
    )
    pack_records: List["PackRecord"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={
            "primaryjoin": "Account.id==PackRecord.account_id",
            "foreign_keys": "[PackRecord.account_id]",
        },
    )

    @property
    def display_name(self) -> str:
        """获取显示名称（优先昵称 > 朋友ID > 游戏ID）"""
        return self.nickname or self.friend_id or self.game_id or f"Account#{self.id}"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "game_id": self.game_id,
            "friend_id": self.friend_id,
            "nintendo_id": self.nintendo_id,
            "nickname": self.nickname,
            "level": self.level,
            "exchange_points": self.exchange_points,
            "country": self.country,
            "remark": self.remark,
            "xml_content": self.xml_content.hex() if self.xml_content else None,
            "session_token_iat": self.session_token_iat,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
