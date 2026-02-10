# -*- coding: utf-8 -*-
"""
任务状态定义

将 TaskStatus 独立出来，避免核心模块之间的循环依赖。
"""

from enum import Enum


class TaskStatus(Enum):
    """任务实例状态"""

    PENDING = "pending"  # 待执行
    BLOCKED = "blocked"  # 被阻塞（等待前置任务完成）
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过（不更新 last_completed_at，等待下次重置）
