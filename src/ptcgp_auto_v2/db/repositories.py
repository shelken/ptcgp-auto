# -*- coding: utf-8 -*-
"""
数据访问层（Repository）

使用 SQLModel 封装数据库 CRUD 操作，提供业务逻辑接口。
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, List, Optional, cast

from sqlmodel import Session, col, func, select
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import (
    Account,
    AccountPackConfig,
    AccountPackPoint,
    AccountTaskPlan,  # 新增
    PackRecord,
    TaskInstance,
    TaskPlan,
    Card,
    CardSet,
    CardPack,
    PackCard,
)
from ptcgp_auto_v2.utils.card_naming import parse_card_number_from_filename

logger = logging.getLogger(__name__)


class CardRepository:
    """卡牌数据访问层"""

    def get_set_by_code(self, code: str) -> Optional[CardSet]:
        """根据代码获取系列"""
        with Session(get_engine()) as session:
            return session.get(CardSet, code)

    def upsert_set(self, card_set: CardSet) -> CardSet:
        """更新或创建系列"""
        with Session(get_engine()) as session:
            existing = session.get(CardSet, card_set.code)
            if existing:
                existing.name = card_set.name
                existing.release_date = card_set.release_date
                existing.total_cards = card_set.total_cards
                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(card_set)
            session.commit()
            session.refresh(card_set)
            return card_set

    def get_card_by_set_and_number(self, set_code: str, number: int) -> Optional[Card]:
        """根据系列和编号获取卡牌"""
        with Session(get_engine()) as session:
            statement = select(Card).where(
                Card.set_code == set_code, Card.number == number
            )
            return session.exec(statement).first()

    def get_card_by_template_name(self, set_code: str, template_name: str) -> Optional[Card]:
        """
        根据模板名称获取卡牌

        Args:
            set_code: 系列代码 (如 A1)
            template_name: 模板名称 (如 "001_Bulbasaur" 或 "025")

        Returns:
            Card对象或None
        """
        # 尝试提取开头的数字部分
        number = parse_card_number_from_filename(template_name)
        if number is not None:
            return self.get_card_by_set_and_number(set_code, number)

        logger.warning(f"Failed to parse card number from template: {template_name}")
        return None

    def upsert_card(self, card: Card) -> Card:
        """更新或创建卡牌"""
        with Session(get_engine()) as session:
            statement = select(Card).where(
                Card.set_code == card.set_code, Card.number == card.number
            )
            existing = session.exec(statement).first()
            if existing:
                existing.name = card.name
                existing.rarity = card.rarity
                existing.image_url = card.image_url
                # local_image_path 不覆盖，除非显式传入了新值
                if card.local_image_path:
                    existing.local_image_path = card.local_image_path
                existing.data = card.data

                # 新增字段更新
                existing.element = card.element
                existing.type = card.type
                existing.stage = card.stage
                existing.health = card.health
                existing.weakness = card.weakness
                existing.retreat_cost = card.retreat_cost

                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(card)
            session.commit()
            session.refresh(card)
            return card

    def clear_card_packs(self, card_id: int):
        """清除卡牌的卡包关联"""
        with Session(get_engine()) as session:
            statement = select(CardPack).where(CardPack.card_id == card_id)
            results = session.exec(statement).all()
            for item in results:
                session.delete(item)
            session.commit()

    def add_card_pack(self, card_id: int, pack_name: str):
        """添加卡牌与卡包的关联"""
        with Session(get_engine()) as session:
            # 检查是否已存在
            statement = select(CardPack).where(
                CardPack.card_id == card_id, CardPack.pack_name == pack_name
            )
            if session.exec(statement).first():
                return

            pack = CardPack(card_id=card_id, pack_name=pack_name)
            session.add(pack)
            session.commit()

    def get_packs_by_set(self, set_code: str) -> dict:
        """
        获取指定系列的子包结构（用于生成兼容的 packs.json）
        Returns:
            {
                "set_code": {
                    "name": "SetName",
                    "boosters": ["Pack1", "Pack2"]
                }
            }
        """
        with Session(get_engine()) as session:
            # 获取系列信息
            card_set = session.get(CardSet, set_code)
            if not card_set:
                return {}

            # 获取该系列下所有卡牌关联的 pack_name
            # JOIN: CardSet -> Card -> CardPack
            statement = (
                select(CardPack.pack_name)
                .join(Card, col(CardPack.card_id) == col(Card.id))
                .where(Card.set_code == set_code)
                .distinct()
            )
            boosters = list(session.exec(statement).all())
            boosters.sort()

            return {
                set_code: {
                    "name": card_set.name,
                    "boosters": boosters,
                }
            }

    def get_all_sets(self) -> List[CardSet]:
        """获取所有系列"""
        with Session(get_engine()) as session:
            statement = select(CardSet).order_by(CardSet.code)
            return list(session.exec(statement).all())

    def get_cards_by_set(self, set_code: str) -> List[Card]:
        """获取系列下的所有卡牌"""
        with Session(get_engine()) as session:
            statement = (
                select(Card)
                .where(Card.set_code == set_code)
                .options(selectinload(cast(Any, Card.packs)))
            )
            return list(session.exec(statement).all())

    def get_cards_by_pack(self, pack_name: str, set_code: str) -> List[Card]:
        """获取指定子包下的所有卡牌"""
        with Session(get_engine()) as session:
            statement = (
                select(Card)
                .join(CardPack, col(Card.id) == col(CardPack.card_id))
                .where(Card.set_code == set_code, CardPack.pack_name == pack_name)
                .options(selectinload(cast(Any, Card.packs)))
            )
            return list(session.exec(statement).all())


class TaskPlanRepository:
    """任务计划数据访问层"""

    def get_by_id(self, plan_id: int) -> Optional[TaskPlan]:
        """根据 ID 获取任务计划"""
        with Session(get_engine()) as session:
            return session.get(TaskPlan, plan_id)

    def get_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划"""
        with Session(get_engine()) as session:
            statement = select(TaskPlan).where(TaskPlan.name == name)
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


class AccountPackPointRepository:
    """开包点数数据访问层"""

    def upsert_points(self, account_id: int, series: str, points: int) -> bool:
        """更新或插入开包点数"""
        with Session(get_engine()) as session:
            statement = select(AccountPackPoint).where(
                AccountPackPoint.account_id == account_id,
                AccountPackPoint.series == series
            )
            record = session.exec(statement).first()

            if record:
                # 更新现有记录
                record.points = points
                record.updated_at = datetime.now()
                session.add(record)
            else:
                # 创建新记录
                record = AccountPackPoint(
                    account_id=account_id,
                    series=series,
                    points=points
                )
                session.add(record)

            session.commit()
            return True


class AccountRepository:
    """账号数据访问层"""

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where(Account.id == account_id)
                .options(
                    selectinload(cast(Any, Account.task_plan)),
                    selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                        cast(Any, AccountTaskPlan.task_plan)
                    ),
                )
            )
            return session.exec(statement).first()

    def get_by_game_id(self, game_id: str) -> Optional[Account]:
        """根据游戏 ID（deviceAccount）获取账号"""
        with Session(get_engine()) as session:
            statement = select(Account).where(Account.game_id == game_id)
            return session.exec(statement).first()

    def get_by_friend_id(self, friend_id: str) -> Optional[Account]:
        """根据朋友 ID 获取账号"""
        with Session(get_engine()) as session:
            statement = select(Account).where(Account.friend_id == friend_id)
            return session.exec(statement).first()

    def get_all(self) -> List[Account]:
        """获取所有账号"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .options(
                    selectinload(cast(Any, Account.task_plan)),
                    selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                        cast(Any, AccountTaskPlan.task_plan)
                    ),
                )
                .order_by(col(Account.id))
            )
            return list(session.exec(statement).all())

    def get_accounts_without_friend_id(self) -> List[Account]:
        """获取所有没有 friend_id 的账号（用于补全任务）"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where((col(Account.friend_id).is_(None)) | (Account.friend_id == ""))
                .order_by(col(Account.id))
            )
            return list(session.exec(statement).all())

    def get_accounts_with_plans(self) -> List[Account]:
        """获取所有有任务计划的账号（包括新旧关联）"""
        with Session(get_engine()) as session:
            # 查询有旧关联 OR 有新关联的账号
            # 这里简化处理：获取所有账号，然后由应用层判断（因为 eager load 了，性能损耗主要在 DB IO）
            # 或者使用 join 过滤。为保持代码简单且健壮，复用 get_all 的 eager load 逻辑
            # 但为了性能，还是加上 where
            statement = (
                select(Account)
                .options(
                    selectinload(cast(Any, Account.task_plan)),
                    selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                        cast(Any, AccountTaskPlan.task_plan)
                    ),
                )
                # .where((Account.task_plan_id.isnot(None)) | (Account.task_plan_associations.any()))
                # SQLModel 对 any() 的支持可能复杂，暂时获取所有，反正没计划的账号在 Scheduler 里会被过滤
                .order_by(col(Account.id))
            )
            accounts = list(session.exec(statement).all())
            return accounts

    def create(self, account: Account) -> Account:
        """创建账号"""
        with Session(get_engine()) as session:
            # 如果没有指定 task_plan，自动关联 "daily"
            if account.task_plan_id is None:
                daily_plan = self.get_plan_by_name(session, "daily")
                if daily_plan:
                    account.task_plan_id = daily_plan.id

            session.add(account)
            session.commit()
            session.refresh(account)
            return account

    def get_plan_by_name(self, session: Session, name: str) -> Optional[TaskPlan]:
        """在现有 session 中根据名称获取任务计划"""
        statement = select(TaskPlan).where(TaskPlan.name == name)
        return session.exec(statement).first()

    def update(self, account: Account) -> bool:
        """更新账号"""
        with Session(get_engine()) as session:
            db_account = session.get(Account, account.id)
            if not db_account:
                return False
            db_account.game_id = account.game_id
            db_account.friend_id = account.friend_id
            db_account.nintendo_id = account.nintendo_id
            db_account.nickname = account.nickname
            db_account.level = account.level
            db_account.country = account.country
            db_account.xml_content = account.xml_content
            db_account.session_token_iat = account.session_token_iat
            db_account.task_plan_id = account.task_plan_id
            db_account.remark = account.remark
            db_account.updated_at = datetime.now()
            session.add(db_account)
            session.commit()
            return True

    def update_friend_id(self, account_id: int, friend_id: str) -> bool:
        """更新账号的 friend_id"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if not account:
                return False
            account.friend_id = friend_id
            account.updated_at = datetime.now()
            session.add(account)
            session.commit()
            return True

    def delete(self, account_id: int) -> bool:
        """删除账号"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if account:
                session.delete(account)
                session.commit()
                return True
            return False

    def assign_task_plan(self, account_id: int, plan_id: int) -> bool:
        """为账号分配主任务计划（旧接口）"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if not account:
                return False
            account.task_plan_id = plan_id
            account.updated_at = datetime.now()
            session.add(account)
            session.commit()
            return True

    def add_secondary_plan(self, account_id: int, plan_id: int, priority: int = 0) -> bool:
        """
        为账号添加额外的任务计划（新接口）

        Args:
            account_id: 账号 ID
            plan_id: 计划 ID
            priority: 优先级

        Returns:
            True 表示成功
        """
        with Session(get_engine()) as session:
            # 检查是否已存在
            statement = select(AccountTaskPlan).where(
                AccountTaskPlan.account_id == account_id,
                AccountTaskPlan.task_plan_id == plan_id,
            )
            existing = session.exec(statement).first()
            if existing:
                existing.is_active = True
                existing.priority = priority
                existing.updated_at = datetime.now()
                session.add(existing)
            else:
                new_assoc = AccountTaskPlan(
                    account_id=account_id,
                    task_plan_id=plan_id,
                    priority=priority,
                )
                session.add(new_assoc)

            session.commit()
            return True

    def remove_secondary_plan(self, account_id: int, plan_id: int) -> bool:
        """移除账号的额外计划"""
        with Session(get_engine()) as session:
            statement = select(AccountTaskPlan).where(
                AccountTaskPlan.account_id == account_id,
                AccountTaskPlan.task_plan_id == plan_id,
            )
            existing = session.exec(statement).first()
            if existing:
                session.delete(existing)
                session.commit()
                return True
            return False


class TaskInstanceRepository:
    """任务实例数据访问层"""

    def get_by_id(self, instance_id: int) -> Optional[TaskInstance]:
        """根据 ID 获取任务实例"""
        with Session(get_engine()) as session:
            instance = session.get(TaskInstance, instance_id)
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_by_account_and_type(
        self,
        account_id: int,
        task_type: str,
    ) -> Optional[TaskInstance]:
        """根据账号和任务类型获取任务实例"""
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                TaskInstance.account_id == account_id,
                TaskInstance.task_type == task_type,
            )
            return session.exec(statement).first()

    def get_or_create(
        self,
        account_id: int,
        task_type: str,
        reset_type: str = "daily",
    ) -> TaskInstance:
        """获取或创建任务实例"""
        instance = self.get_by_account_and_type(account_id, task_type)
        if instance:
            return instance

        # 创建新实例
        instance = TaskInstance(
            account_id=account_id,
            task_type=task_type,
            status="pending",
            reset_type=reset_type,
        )
        return self.create(instance)

    def get_next_pending(self) -> Optional[TaskInstance]:
        """获取下一个待执行的任务实例"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(TaskInstance.status == "pending")
                .order_by(col(TaskInstance.created_at))
                .limit(1)
            )
            instance = session.exec(statement).first()
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_next_pending_excluding_busy_accounts(self) -> Optional[TaskInstance]:
        """获取下一个待执行的任务实例（排除正在执行任务的账号）

        用于防止同一账号被同时分配到多个设备。
        """
        with Session(get_engine()) as session:
            # 获取正在执行任务的账号 ID 列表
            busy_accounts_stmt = select(TaskInstance.account_id).where(
                TaskInstance.status == "running"
            )
            busy_account_ids = [row for row in session.exec(busy_accounts_stmt)]

            statement = (
                select(TaskInstance)
                .where(TaskInstance.status == "pending")
                .where(col(TaskInstance.account_id).notin_(busy_account_ids))
                .order_by(col(TaskInstance.created_at))
                .limit(1)
            )
            instance = session.exec(statement).first()
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_pending_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有待执行任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "pending",
                )
                .order_by(col(TaskInstance.created_at))
            )
            return list(session.exec(statement).all())

    def get_blocked_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有被阻塞任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "blocked",
                )
                .order_by(col(TaskInstance.created_at))
            )
            return list(session.exec(statement).all())

    def count_by_status(self, status: str) -> int:
        """统计指定状态的任务数量"""
        with Session(get_engine()) as session:
            statement = (
                select(func.count())
                .select_from(TaskInstance)
                .where(TaskInstance.status == status)
            )
            result = session.exec(statement).one()
            return result or 0

    def get_accounts_with_pending_tasks(self) -> List[int]:
        """获取所有有待执行任务的账号 ID 列表"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance.account_id)
                .where(TaskInstance.status == "pending")
                .distinct()
                .order_by(col(TaskInstance.account_id))
            )
            return list(session.exec(statement).all())

    def has_running_tasks(self, account_id: int) -> bool:
        """检查账号是否有正在执行的任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "running",
                )
                .limit(1)
            )
            return session.exec(statement).first() is not None

    def create(self, instance: TaskInstance) -> TaskInstance:
        """创建任务实例"""
        with Session(get_engine()) as session:
            session.add(instance)
            session.commit()
            session.refresh(instance)
            # 加载关联的账号
            _ = instance.account
            return instance

    def update(self, instance: TaskInstance) -> bool:
        """更新任务实例"""
        with Session(get_engine()) as session:
            db_instance = session.get(TaskInstance, instance.id)
            if not db_instance:
                return False
            db_instance.status = instance.status
            db_instance.error_message = instance.error_message
            db_instance.last_completed_at = instance.last_completed_at
            db_instance.updated_at = datetime.now()
            session.add(db_instance)
            session.commit()
            return True

    def reset_all_pending(self) -> int:
        """将所有异常状态的任务重置为待执行（用于程序重启后恢复）

        重置的状态包括：
        - running: 任务正在执行中被中断
        - blocked: 任务等待前置任务完成，但前置任务没有完成就退出了
        - skipped: 任务被跳过（12小时内已开包等），重启后重新检查
        - failed: 任务执行失败，重启后重试
        """
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                col(TaskInstance.status).in_(
                    ["running", "blocked", "skipped", "failed"]
                )
            )
            instances = session.exec(statement).all()
            count = 0
            for instance in instances:
                instance.status = "pending"
                instance.updated_at = datetime.now()
                session.add(instance)
                count += 1
            session.commit()
            return count

    def reset_stale_tasks(
        self, stale_timeout_seconds: int, skipped_timeout_seconds: int
    ) -> int:
        """重置超时的异常状态任务（用于 daemon 模式定期清理）

        Args:
            stale_timeout_seconds: running/blocked 状态的超时时间（秒）
            skipped_timeout_seconds: skipped 状态的超时时间（秒）

        Returns:
            重置的任务数量
        """
        with Session(get_engine()) as session:
            now = datetime.now()
            stale_threshold = datetime.fromtimestamp(
                now.timestamp() - stale_timeout_seconds
            )
            skipped_threshold = datetime.fromtimestamp(
                now.timestamp() - skipped_timeout_seconds
            )

            statement = select(TaskInstance).where(
                # running 超时
                (
                    (TaskInstance.status == "running")
                    & (TaskInstance.updated_at < stale_threshold)
                )
                # failed 直接重试
                | (TaskInstance.status == "failed")
                # blocked 超时
                | (
                    (TaskInstance.status == "blocked")
                    & (TaskInstance.updated_at < stale_threshold)
                )
                # skipped 超时后重新检查
                | (
                    (TaskInstance.status == "skipped")
                    & (TaskInstance.updated_at < skipped_threshold)
                )
            )
            instances = session.exec(statement).all()
            count = 0
            for instance in instances:
                instance.status = "pending"
                instance.updated_at = datetime.now()
                session.add(instance)
                count += 1
            session.commit()
            return count

    def delete(self, instance_id: int) -> bool:
        """删除任务实例"""
        with Session(get_engine()) as session:
            instance = session.get(TaskInstance, instance_id)
            if instance:
                session.delete(instance)
                session.commit()
                return True
            return False


class AccountPackConfigRepository:
    """账号开包配置数据访问层"""

    def get_by_account_and_type(
        self, account_id: int, config_type: str
    ) -> Optional[AccountPackConfig]:
        """根据账号和类型获取开包配置"""
        with Session(get_engine()) as session:
            statement = select(AccountPackConfig).where(
                AccountPackConfig.account_id == account_id,
                AccountPackConfig.type == config_type,
            )
            return session.exec(statement).first()

    def get_by_account(self, account_id: int) -> List[AccountPackConfig]:
        """获取账号的所有开包配置"""
        with Session(get_engine()) as session:
            statement = (
                select(AccountPackConfig)
                .where(AccountPackConfig.account_id == account_id)
                .order_by(AccountPackConfig.type)
            )
            return list(session.exec(statement).all())

    def create(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建开包配置"""
        with Session(get_engine()) as session:
            session.add(config)
            session.commit()
            session.refresh(config)
            return config

    def update(self, config: AccountPackConfig) -> bool:
        """更新开包配置"""
        with Session(get_engine()) as session:
            db_config = session.get(AccountPackConfig, config.id)
            if not db_config:
                return False
            db_config.type = config.type
            db_config.pack_code = config.pack_code
            db_config.booster_name = config.booster_name
            db_config.updated_at = datetime.now()
            session.add(db_config)
            session.commit()
            return True

    def upsert(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建或更新开包配置"""
        existing = self.get_by_account_and_type(config.account_id, config.type)
        if existing:
            config.id = existing.id
            self.update(config)
            return config
        return self.create(config)

    def delete(self, config_id: int) -> bool:
        """删除开包配置"""
        with Session(get_engine()) as session:
            config = session.get(AccountPackConfig, config_id)
            if config:
                session.delete(config)
                session.commit()
                return True
            return False


class PackRecordRepository:
    """开包记录数据访问层"""

    def get_by_account(self, account_id: int) -> List[PackRecord]:
        """获取账号的所有开包记录"""
        with Session(get_engine()) as session:
            statement = (
                select(PackRecord)
                .where(PackRecord.account_id == account_id)
                .order_by(col(PackRecord.opened_at).desc())
            )
            return list(session.exec(statement).all())

    def get_today(self, account_id: int) -> Optional[PackRecord]:
        """获取账号今日的开包记录"""
        with Session(get_engine()) as session:
            today = datetime.now().date()
            statement = (
                select(PackRecord)
                .where(
                    PackRecord.account_id == account_id,
                    func.date(PackRecord.opened_at) == today,
                )
                .order_by(col(PackRecord.opened_at).desc())
                .limit(1)
            )
            return session.exec(statement).first()

    def has_opened_today(self, account_id: int) -> bool:
        """检查账号今日是否已开包"""
        return self.get_today(account_id) is not None

    def has_opened_within_hours(self, account_id: int, hours: int = 12) -> bool:
        """检查账号在指定小时内是否已开包"""
        with Session(get_engine()) as session:
            threshold = datetime.fromtimestamp(
                datetime.now().timestamp() - hours * 3600
            )
            statement = (
                select(PackRecord)
                .where(
                    PackRecord.account_id == account_id,
                    PackRecord.opened_at >= threshold,
                )
                .limit(1)
            )
            return session.exec(statement).first() is not None

    def create(self, record: PackRecord) -> PackRecord:
        """创建开包记录"""
        with Session(get_engine()) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def create_for_account(
        self,
        account_id: int,
        pack_type: str = "",
        cards: List[dict] = None,  # type: ignore
        pack_code: Optional[str] = None,
        pack_name: Optional[str] = None,
    ) -> PackRecord:
        """
        为账号创建开包记录

        Args:
            account_id: 账号ID
            pack_type: 卡包类型（来源，如 daily_free）
            cards: 包含卡牌信息的字典列表
            pack_code: 系列代码 (A1)
            pack_name: 卡包名称 (Charizard)
        """
        with Session(get_engine()) as session:
            # 1. 创建 PackRecord
            record = PackRecord(
                account_id=account_id,
                pack_type=pack_type,
                pack_code=pack_code,
                pack_name=pack_name,
            )
            session.add(record)
            # 使用 flush 而不是 commit，确保在同一个事务中
            session.flush()

            # 2. 如果有卡牌明细，创建 PackCard
            if cards:
                if record.id is None:
                     # 理论上 flush 后不应该为 None，但为了类型安全
                    session.refresh(record)

                if record.id:
                    for card_data in cards:
                        pack_card = PackCard(
                            pack_record_id=record.id,
                            card_id=card_data.get("card_id"),
                            card_name=card_data.get("card_name", "Unknown"),
                            rarity=card_data.get("rarity"),
                            is_new=card_data.get("is_new", False),
                            position=card_data.get("position", 0),
                            confidence=card_data.get("confidence", 0.0),
                        )
                        session.add(pack_card)

            # 3. 统一提交
            session.commit()
            session.refresh(record)

            return record

    def migrate_legacy_data(self):
        """迁移旧数据：将 pack_type 拆分为 pack_code 和 pack_name，原 pack_type 设为 daily_free"""
        with Session(get_engine()) as session:
            # 查找所有 pack_code 为空的记录（且 pack_type 不为空）
            statement = select(PackRecord).where(
                (col(PackRecord.pack_code).is_(None)) & (PackRecord.pack_type != "")
            )
            records = session.exec(statement).all()
            count = 0
            for record in records:
                # 旧格式假设为 "A1/Charizard"
                if "/" in record.pack_type:
                    try:
                        parts = record.pack_type.split("/", 1)
                        record.pack_code = parts[0]
                        record.pack_name = parts[1]
                        record.pack_type = "daily_free"
                        session.add(record)
                        count += 1
                    except Exception as e:
                        logger.warning(f"迁移记录 {record.id} 失败: {e}")
            if count > 0:
                session.commit()
                logger.info(f"已迁移 {count} 条旧开包记录")

    def count_by_account(self, account_id: int) -> int:
        """统计账号的开包总数"""
        with Session(get_engine()) as session:
            statement = (
                select(func.count())
                .select_from(PackRecord)
                .where(PackRecord.account_id == account_id)
            )
            result = session.exec(statement).one()
            return result or 0

    def delete(self, record_id: int) -> bool:
        """删除开包记录"""
        with Session(get_engine()) as session:
            record = session.get(PackRecord, record_id)
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
