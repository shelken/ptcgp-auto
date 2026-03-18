# -*- coding: utf-8 -*-
import json
from typing import List, Optional

from sqlalchemy import String, cast, or_
from sqlmodel import col, func, select

from ptcgp_auto_v2.db.models import TaskPlan
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from .base import BaseRepository


class TaskPlanRepository(BaseRepository):
    """任务计划数据访问层"""

    def get_by_id(self, plan_id: int) -> Optional[TaskPlan]:
        """根据 ID 获取任务计划"""
        return self.session.get(TaskPlan, plan_id)

    def get_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划"""
        statement = select(TaskPlan).where(TaskPlan.name == name)
        return self.session.exec(statement).first()

    def get_all(self) -> List[TaskPlan]:
        """获取所有任务计划"""
        statement = select(TaskPlan).order_by(col(TaskPlan.id))
        return list(self.session.exec(statement).all())

    def list_page(
        self,
        *,
        q: str,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> tuple[list[TaskPlan], int]:
        """按筛选条件分页获取任务计划。"""
        statement = select(TaskPlan)
        count_statement = select(func.count()).select_from(TaskPlan)
        if q:
            like_value = f"%{q}%"
            condition = or_(
                cast(col(TaskPlan.id), String).ilike(like_value),
                col(TaskPlan.name).ilike(like_value),
                col(TaskPlan.description).ilike(like_value),
            )
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        order_column = col(TaskPlan.name) if sort_by == "name" else col(TaskPlan.id)
        statement = statement.order_by(order_column.desc() if sort_order == "desc" else order_column.asc())
        statement = statement.offset(page * page_size).limit(page_size)
        items = list(self.session.exec(statement).all())
        total = int(self.session.exec(count_statement).one() or 0)
        return items, total

    def list_unassigned_for_account(self, account_id: int) -> List[TaskPlan]:
        """获取账号尚未关联的计划列表。"""
        subquery = select(AccountTaskPlan.task_plan_id).where(
            AccountTaskPlan.account_id == account_id
        )
        statement = (
            select(TaskPlan)
            .where(col(TaskPlan.id).not_in(subquery))
            .order_by(col(TaskPlan.id))
        )
        return list(self.session.exec(statement).all())

    def create(self, plan: TaskPlan) -> TaskPlan:
        """创建任务计划"""
        plan.task_types = (
            json.dumps(plan.task_types, ensure_ascii=False)
            if isinstance(plan.task_types, list)
            else plan.task_types
        )
        self.session.add(plan)
        self._finish_write(plan)
        return plan

    def update(self, plan: TaskPlan) -> bool:
        """更新任务计划"""
        db_plan = self.session.get(TaskPlan, plan.id)
        if not db_plan:
            return False
        db_plan.name = plan.name
        db_plan.description = plan.description
        db_plan.task_types = (
            json.dumps(plan.task_types, ensure_ascii=False)
            if isinstance(plan.task_types, list)
            else plan.task_types
        )
        db_plan.configuration = (
            json.dumps(plan.configuration, ensure_ascii=False)
            if isinstance(plan.configuration, dict)
            else plan.configuration
        )
        self.session.add(db_plan)
        self._finish_write()
        return True

    def delete(self, plan_id: int) -> bool:
        """删除任务计划"""
        plan = self.session.get(TaskPlan, plan_id)
        if not plan:
            return False
        self.session.delete(plan)
        self._finish_write()
        return True
