# -*- coding: utf-8 -*-
"""
数据库模块。

使用惰性导出，避免导入子模块时提前初始化所有 Repository。
"""

from importlib import import_module
from typing import Any

from ptcgp_auto_v2.db.engine import (
    get_engine as get_engine,
    get_session as get_session,
    session_scope as session_scope,
)

_EXPORT_MODULES = {
    "Account": "ptcgp_auto_v2.db.models",
    "AccountStat": "ptcgp_auto_v2.db.models",
    "AccountPackConfig": "ptcgp_auto_v2.db.models",
    "PackRecord": "ptcgp_auto_v2.db.models",
    "TaskInstance": "ptcgp_auto_v2.db.models",
    "TaskPlan": "ptcgp_auto_v2.db.models",
    "AccountPackConfigRepository": "ptcgp_auto_v2.db.repositories",
    "AccountRepository": "ptcgp_auto_v2.db.repositories",
    "AccountStatRepository": "ptcgp_auto_v2.db.repositories",
    "PackRecordRepository": "ptcgp_auto_v2.db.repositories",
    "TaskInstanceRepository": "ptcgp_auto_v2.db.repositories",
    "TaskPlanRepository": "ptcgp_auto_v2.db.repositories",
}


def __getattr__(name: str) -> Any:
    """按需导出数据库层常用符号。"""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)
