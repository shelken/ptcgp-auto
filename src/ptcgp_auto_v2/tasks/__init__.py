# -*- coding: utf-8 -*-
"""
任务模块

包含所有可插拔的任务实现。
"""

# 自动导入所有任务模块以触发注册
from ptcgp_auto_v2.tasks import open_pack
from ptcgp_auto_v2.tasks import fetch_account_info
from ptcgp_auto_v2.tasks import claim_rewards
from ptcgp_auto_v2.tasks import claim_gifts
from ptcgp_auto_v2.tasks import init_account
from ptcgp_auto_v2.tasks import collect_account_cards
from ptcgp_auto_v2.tasks import wonder_pick

# 导出任务注册表
from ptcgp_auto_v2.core.task_base import TaskRegistry

__all__ = ["TaskRegistry"]
