# -*- coding: utf-8 -*-
"""Repository 包导出。"""

from importlib import import_module
from typing import Any

from ptcgp_auto_v2.db.engine import get_engine

__all__ = [
    "get_engine",
    "BaseRepository",
    "AccountBattleProgressRepository",
    "BattleTaskConfigRepository",
    "AccountPackConfigRepository",
    "AccountPackPointRepository",
    "AccountCardRepository",
    "AccountStatRepository",
    "AccountGiftPairRepository",
    "AccountGiftRecordRepository",
    "AccountRepository",
    "CardRepository",
    "FriendRequestRepository",
    "ExchangeCardRequestRepository",
    "FriendshipRepository",
    "NotificationRepository",
    "NotificationConfigRepository",
    "PackRecordRepository",
    "TaskInstanceRepository",
    "TaskPlanRepository",
    "RepositoryFactory",
]

_EXPORT_MODULES = {
    "BaseRepository": "ptcgp_auto_v2.db.repositories.base",
    "AccountBattleProgressRepository": "ptcgp_auto_v2.db.repositories.account_battle_progress_repository",
    "BattleTaskConfigRepository": "ptcgp_auto_v2.db.repositories.battle_task_config_repository",
    "AccountPackConfigRepository": "ptcgp_auto_v2.db.repositories.account_pack_config_repository",
    "AccountPackPointRepository": "ptcgp_auto_v2.db.repositories.account_pack_point_repository",
    "AccountCardRepository": "ptcgp_auto_v2.db.repositories.account_card_repository",
    "AccountStatRepository": "ptcgp_auto_v2.db.repositories.account_stat_repository",
    "AccountGiftPairRepository": "ptcgp_auto_v2.db.repositories.account_gift_pair_repository",
    "AccountGiftRecordRepository": "ptcgp_auto_v2.db.repositories.account_gift_record_repository",
    "AccountRepository": "ptcgp_auto_v2.db.repositories.account_repository",
    "CardRepository": "ptcgp_auto_v2.db.repositories.card_repository",
    "FriendRequestRepository": "ptcgp_auto_v2.db.repositories.friend_request_repository",
    "ExchangeCardRequestRepository": "ptcgp_auto_v2.db.repositories.exchange_card_request_repository",
    "FriendshipRepository": "ptcgp_auto_v2.db.repositories.friendship_repository",
    "NotificationRepository": "ptcgp_auto_v2.db.repositories.notification_repository",
    "NotificationConfigRepository": "ptcgp_auto_v2.db.repositories.notification_config_repository",
    "PackRecordRepository": "ptcgp_auto_v2.db.repositories.pack_record_repository",
    "TaskInstanceRepository": "ptcgp_auto_v2.db.repositories.task_instance_repository",
    "TaskPlanRepository": "ptcgp_auto_v2.db.repositories.task_plan_repository",
    "RepositoryFactory": "ptcgp_auto_v2.db.repositories.factory",
}


def __getattr__(name: str) -> Any:
    """按需导出 Repository，避免包初始化时级联导入。"""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)
