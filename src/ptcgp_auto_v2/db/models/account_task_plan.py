# -*- coding: utf-8 -*-
"""
AccountTaskPlan 关联模型

实现 Account 和 TaskPlan 的多对多关系。
允许一个账号绑定多个任务计划。
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .task_plan import TaskPlan
    from .account import Account


class AccountTaskPlan(SQLModel, table=True):
    """
    账号-任务计划关联表
    """

    __tablename__ = "account_task_plans"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    task_plan_id: int = Field(foreign_key="task_plans.id", index=True)
    is_active: bool = Field(default=True, description="是否启用该计划")
    priority: int = Field(default=0, description="优先级（数字越大优先级越高）")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 关系
    task_plan: "TaskPlan" = Relationship()
    account: "Account" = Relationship(back_populates="task_plan_associations")
