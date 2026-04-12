# -*- coding: utf-8 -*-
"""
任务模块

包含所有可插拔的任务实现。
"""

# 自动导入所有任务模块以触发注册
from ptcgp_auto_v2.tasks import open_pack as open_pack
from ptcgp_auto_v2.tasks import fetch_account_info as fetch_account_info
from ptcgp_auto_v2.tasks import claim_rewards as claim_rewards
from ptcgp_auto_v2.tasks import claim_gifts as claim_gifts
from ptcgp_auto_v2.tasks import init_account as init_account
from ptcgp_auto_v2.tasks import collect_account_cards as collect_account_cards
from ptcgp_auto_v2.tasks import wonder_pick as wonder_pick
from ptcgp_auto_v2.tasks import manage_friendship as manage_friendship
from ptcgp_auto_v2.tasks import send_card_daily as send_card_daily
from ptcgp_auto_v2.tasks import exchange_cards as exchange_cards
from ptcgp_auto_v2.tasks import battle as battle

# 导出任务注册表
from ptcgp_auto_v2.core.task_base import TaskRegistry as TaskRegistry
