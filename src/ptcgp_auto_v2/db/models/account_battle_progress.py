# -*- coding: utf-8 -*-
"""
账号对战进度表

记录账号在特定系列+等级下的完成状态。
账号与进度为 1 对多关系。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account


class AccountBattleProgress(SQLModel, table=True):
    """
    账号对战进度表

    记录每个账号在各个系列+等级下的对战完成状态。
    唯一约束：一个账号在一个系列+等级下只有一条记录。
    """

    __tablename__ = "account_battle_progress"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)

    # 系列代码（A1, A2, B1 等）
    set_code: str = Field(description="系列代码，如 A1")

    # 难度等级（初級, 中級, 上級, 精英等）
    level: str = Field(description="难度等级，如初級/中級/上級/精英")

    # 完成状态
    status: str = Field(
        default="in_progress",
        description="状态: in_progress(进行中) / completed(已完成)"
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="最后更新时间"
    )

    # 关系定义
    account: Optional["Account"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "AccountBattleProgress.account_id==Account.id",
            "foreign_keys": "[AccountBattleProgress.account_id]",
        }
    )

    class Config:
        # 唯一约束：一个账号在一个系列+等级下只有一条记录
        unique_together = [("account_id", "set_code", "level")]
