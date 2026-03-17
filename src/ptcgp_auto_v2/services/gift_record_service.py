# -*- coding: utf-8 -*-
"""
送卡记录服务。

负责送卡流水状态维护与 account_cards 数量同步。
"""

import re
from typing import Optional

from ptcgp_auto_v2.db.models import AccountGiftRecord
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    AccountGiftRecordRepository,
    TaskInstanceRepository,
)
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str


COUNT_TRANSITION_PATTERN = re.compile(r"(\d+)\s*>\s*(\d+)")


class GiftRecordService:
    """送卡记录服务。"""

    @staticmethod
    def today_local_date() -> str:
        """返回游戏业务日期（YYYY-MM-DD，按 UTC06:00 换算本地切日）。"""
        return get_game_biz_date_str()

    @staticmethod
    def parse_count_transition(text: str) -> tuple[Optional[int], Optional[int]]:
        """解析持有数量文本（如 1>0）。"""
        match = COUNT_TRANSITION_PATTERN.search(text)
        if not match:
            return None, None
        return int(match.group(1)), int(match.group(2))

    @classmethod
    def ensure_daily_record(
        cls,
        account_id: int,
        target_friend_id: str,
        target_account_id: Optional[int],
        card_set_code: Optional[str],
        card_number: Optional[int],
    ) -> AccountGiftRecord:
        """创建或读取当天送卡记录。"""
        return AccountGiftRecordRepository().create_or_get_daily(
            account_id=account_id,
            target_friend_id=target_friend_id,
            target_account_id=target_account_id,
            card_set_code=card_set_code,
            card_number=card_number,
            biz_date_local=cls.today_local_date(),
        )

    @classmethod
    def is_daily_success(
        cls,
        account_id: int,
        target_friend_id: str,
    ) -> bool:
        """判断当日是否已成功送卡。"""
        success = AccountGiftRecordRepository().get_daily_success_record(
            account_id=account_id,
            target_friend_id=target_friend_id,
            biz_date_local=cls.today_local_date(),
        )
        return success is not None

    @classmethod
    def is_daily_scan_no_card(
        cls,
        account_id: int,
        target_friend_id: str,
    ) -> bool:
        """判断当日是否因扫描未找到目标卡而收敛。"""
        record = AccountGiftRecordRepository().get_daily_record(
            account_id=account_id,
            target_friend_id=target_friend_id,
            biz_date_local=cls.today_local_date(),
        )
        if record is None:
            return False
        return record.error_code == "CARD_NOT_FOUND_BY_SCAN"

    @classmethod
    def has_daily_attempt(
        cls,
        account_id: int,
        target_friend_id: str,
    ) -> bool:
        """判断当日是否已执行过一次送卡尝试（不含 init）。"""
        record = AccountGiftRecordRepository().get_daily_record(
            account_id=account_id,
            target_friend_id=target_friend_id,
            biz_date_local=cls.today_local_date(),
        )
        if record is None:
            return False
        return record.status != "init"

    @staticmethod
    def ensure_send_card_daily_pending(account_id: int) -> bool:
        """确保目标账号的 send_card_daily 任务处于 pending。"""
        repo = TaskInstanceRepository()
        instance = repo.get_by_account_and_type(account_id, "send_card_daily")

        if instance is None:
            instance = repo.get_or_create(
                account_id=account_id,
                task_type="send_card_daily",
                reset_type="interval",
            )

        should_save = False
        if instance.status != TaskStatus.PENDING.value:
            instance.status = TaskStatus.PENDING.value
            should_save = True
        if getattr(instance, "next_run_at", None) is not None:
            instance.next_run_at = None
            should_save = True

        if should_save:
            instance.save()

        return True

    @staticmethod
    def ensure_claim_gifts_pending(account_id: int) -> bool:
        """确保目标账号的 claim_gifts 任务处于 pending。"""
        repo = TaskInstanceRepository()
        instance = repo.get_by_account_and_type(account_id, "claim_gifts")

        if instance is None:
            instance = repo.get_or_create(
                account_id=account_id,
                task_type="claim_gifts",
                reset_type="daily",
            )

        should_save = False
        if instance.status != TaskStatus.PENDING.value:
            instance.status = TaskStatus.PENDING.value
            should_save = True
        if getattr(instance, "next_run_at", None) is not None:
            instance.next_run_at = None
            should_save = True

        if should_save:
            instance.save()

        return True

    @staticmethod
    def update_status(
        record: AccountGiftRecord,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AccountGiftRecord:
        """更新记录状态与错误信息。"""
        record.status = status
        record.error_code = error_code
        record.error_message = error_message
        return AccountGiftRecordRepository().update(record)

    @staticmethod
    def mark_success_and_sync_count(
        record: AccountGiftRecord,
        card_id: Optional[int],
        before_count: Optional[int],
        after_count: Optional[int],
    ) -> AccountGiftRecord:
        """标记成功并同步 account_cards 的剩余数量。"""
        resolved_after_count = after_count
        count_source = "ui"

        account_card_repo = AccountCardRepository()
        db_row = None
        if card_id is not None:
            db_row = account_card_repo.get(record.account_id, card_id)

        if resolved_after_count is None:
            if before_count is not None:
                resolved_after_count = max(before_count - 1, 0)
                count_source = "fallback"
            elif db_row is not None:
                resolved_after_count = max(int(db_row.count) - 1, 0)
                count_source = "db"

        record.card_id = card_id
        record.before_count = before_count
        record.after_count = resolved_after_count
        record.count_source = count_source if resolved_after_count is not None else None
        record.status = "success"
        record.error_code = None
        record.error_message = None
        updated = AccountGiftRecordRepository().update(record)

        if card_id is not None and resolved_after_count is not None:
            account_card_repo.upsert(
                account_id=record.account_id,
                card_id=card_id,
                count=resolved_after_count,
                yolo_conf=db_row.yolo_conf if db_row else None,
                hash_similarity=db_row.hash_similarity if db_row else None,
            )

            # 双向同步：送卡成功后，目标账号该卡数量 +1。
            if isinstance(record.target_account_id, int):
                target_row = account_card_repo.get(record.target_account_id, card_id)
                account_card_repo.increase_owned(
                    account_id=record.target_account_id,
                    card_id=card_id,
                    amount=1,
                    yolo_conf=target_row.yolo_conf if target_row else None,
                    hash_similarity=target_row.hash_similarity if target_row else None,
                )

        return updated
