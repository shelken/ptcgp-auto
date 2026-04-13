# -*- coding: utf-8 -*-
"""
Repository 工厂

统一按同一个 Session 组装 Repository，避免调用方手写一组构造逻辑。
"""

from sqlmodel import Session

from .account_battle_progress_repository import AccountBattleProgressRepository
from .account_card_repository import AccountCardRepository
from .account_gift_pair_repository import AccountGiftPairRepository
from .account_gift_record_repository import AccountGiftRecordRepository
from .account_pack_config_repository import AccountPackConfigRepository
from .account_pack_point_repository import AccountPackPointRepository
from .account_repository import AccountRepository
from .account_stat_repository import AccountStatRepository
from .battle_task_config_repository import BattleTaskConfigRepository
from .card_repository import CardRepository
from .exchange_card_request_repository import ExchangeCardRequestRepository
from .friend_request_repository import FriendRequestRepository
from .friendship_repository import FriendshipRepository
from .notification_repository import NotificationRepository
from .pack_record_repository import PackRecordRepository
from .task_instance_repository import TaskInstanceRepository
from .task_plan_repository import TaskPlanRepository


class RepositoryFactory:
    """统一按 Session 创建 Repository。"""

    def __init__(self, session: Session):
        """绑定当前高层动作使用的 Session。"""
        self.session = session

    def accounts(self) -> AccountRepository:
        return AccountRepository(self.session)

    def account_stats(self) -> AccountStatRepository:
        return AccountStatRepository(self.session)

    def account_cards(self) -> AccountCardRepository:
        return AccountCardRepository(self.session)

    def account_pack_configs(self) -> AccountPackConfigRepository:
        return AccountPackConfigRepository(self.session)

    def account_pack_points(self) -> AccountPackPointRepository:
        return AccountPackPointRepository(self.session)

    def account_gift_pairs(self) -> AccountGiftPairRepository:
        return AccountGiftPairRepository(self.session)

    def account_gift_records(self) -> AccountGiftRecordRepository:
        return AccountGiftRecordRepository(self.session)

    def account_battle_progress(self) -> AccountBattleProgressRepository:
        return AccountBattleProgressRepository(self.session)

    def battle_task_configs(self) -> BattleTaskConfigRepository:
        return BattleTaskConfigRepository(self.session)

    def cards(self) -> CardRepository:
        return CardRepository(self.session)

    def friend_requests(self) -> FriendRequestRepository:
        return FriendRequestRepository(self.session)

    def exchange_card_requests(self) -> ExchangeCardRequestRepository:
        return ExchangeCardRequestRepository(self.session)

    def friendships(self) -> FriendshipRepository:
        return FriendshipRepository(self.session)

    def notifications(self) -> NotificationRepository:
        return NotificationRepository(self.session)

    def pack_records(self) -> PackRecordRepository:
        return PackRecordRepository(self.session)

    def task_instances(self) -> TaskInstanceRepository:
        return TaskInstanceRepository(self.session)

    def task_plans(self) -> TaskPlanRepository:
        return TaskPlanRepository(self.session)
