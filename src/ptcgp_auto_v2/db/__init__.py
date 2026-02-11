# -*- coding: utf-8 -*-
"""
数据库模块

包含 SQLModel 模型、数据库引擎和数据访问层。
"""

from ptcgp_auto_v2.db.engine import get_engine, get_session, session_scope
from ptcgp_auto_v2.db.models import (
    Account,
    AccountStat,
    AccountPackConfig,
    PackRecord,
    TaskInstance,
    TaskPlan,
)
from ptcgp_auto_v2.db.repositories import (
    AccountPackConfigRepository,
    AccountRepository,
    AccountStatRepository,
    PackRecordRepository,
    TaskInstanceRepository,
    TaskPlanRepository,
)

__all__ = [
    # 引擎和会话
    "get_engine",
    "get_session",
    "session_scope",
    # 模型
    "Account",
    "AccountStat",
    "AccountPackConfig",
    "PackRecord",
    "TaskInstance",
    "TaskPlan",
    # 仓库
    "AccountPackConfigRepository",
    "AccountRepository",
    "AccountStatRepository",
    "PackRecordRepository",
    "TaskInstanceRepository",
    "TaskPlanRepository",
]
