# -*- coding: utf-8 -*-
"""
Repository 包统一导出入口。

作用：
- 提供 Repository 与工厂类的单一导入路径。

覆盖范围：
- v2 数据访问层所有 Repository 类型与 RepositoryFactory。

关键依赖：
- ptcgp_auto_v2.db.engine.get_engine
- 各具体 Repository 模块与 factory 模块
"""

from ptcgp_auto_v2.db.engine import get_engine as get_engine
from .account_battle_progress_repository import (
    AccountBattleProgressRepository as AccountBattleProgressRepository,
)
from .account_card_repository import AccountCardRepository as AccountCardRepository
from .account_gift_pair_repository import AccountGiftPairRepository as AccountGiftPairRepository
from .account_gift_record_repository import AccountGiftRecordRepository as AccountGiftRecordRepository
from .account_pack_config_repository import AccountPackConfigRepository as AccountPackConfigRepository
from .account_pack_point_repository import AccountPackPointRepository as AccountPackPointRepository
from .account_repository import AccountRepository as AccountRepository
from .account_stat_repository import AccountStatRepository as AccountStatRepository
from .base import BaseRepository as BaseRepository
from .battle_task_config_repository import BattleTaskConfigRepository as BattleTaskConfigRepository
from .card_repository import CardRepository as CardRepository
from .exchange_card_request_repository import (
    ExchangeCardRequestRepository as ExchangeCardRequestRepository,
)
from .factory import RepositoryFactory as RepositoryFactory
from .friend_request_repository import FriendRequestRepository as FriendRequestRepository
from .friendship_repository import FriendshipRepository as FriendshipRepository
from .notification_config_repository import (
    NotificationConfigRepository as NotificationConfigRepository,
)
from .notification_repository import NotificationRepository as NotificationRepository
from .pack_record_repository import PackRecordRepository as PackRecordRepository
from .task_instance_repository import TaskInstanceRepository as TaskInstanceRepository
from .task_plan_repository import TaskPlanRepository as TaskPlanRepository
