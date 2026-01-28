# -*- coding: utf-8 -*-
import json
from typing import List, Optional

from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import TaskPlan


class TaskPlanRepository:
    """任务计划数据访问层"""

    def get_by_id(self, plan_id: int) -> Optional[TaskPlan]:
        """根据 ID 获取任务计划"""
        with Session(get_engine()) as session:
            return session.get(TaskPlan, plan_id)

    def get_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划"""
        with Session(get_engine()) as session:
            statement = select(TaskPlan).where(TaskPlan
.name == name)
            return session.exec(statement).first()

    def get_all(self) -> List[TaskPlan]:
        """获取所有任务计划"""
        with Session(get_engine()) as session:
            statement = select(TaskPlan).order_by(col(TaskPlan.id))
            return list(session.exec(statement).all())

    def create(self, plan: TaskPlan) -> TaskPlan:
        """创建任务计划"""
        with Session(get_engine()) as session:
            # 如果 task_types 是列表，转换为 JSON 字符串
            if isinstance(plan.task_types, list):
                plan.task_types = json.dumps(plan.task_types, ensure_ascii=False)
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return plan

    def update(self, plan: TaskPlan) -> bool:
        """更新任务计划"""
        with Session(get_engine()) as session:
            db_plan = session.get(TaskPlan, plan.id)
            if not db_plan:
                return False
            db_plan.name = plan.name
            db_plan.description = plan.description
            # 如果 task_types 是列表，转换为 JSON 字符串
            if isinstance(plan.task_types, list):
                db_plan.task_types = json.dumps(plan.task_types, ensure_ascii=False)
            else:
                db_plan.task_types = plan.task_types

            # 如果 configuration 是字典，转换为 JSON 字符串（修复 configuration 不更新的 bug）
            if isinstance(plan.configuration, dict):
                db_plan.configuration = json.dumps(
                    plan.configuration, ensure_ascii=False
                )
            else:
                db_plan.configuration = plan.configuration

            session.add(db_plan)
            session.commit()
            return True

    def delete(self, plan_id: int) -> bool:
        """删除任务计划"""
        with Session(get_engine()) as session:
            plan = session.get(TaskPlan, plan_id)
            if plan:
                session.delete(plan)
                session.commit()
                return True
            return False