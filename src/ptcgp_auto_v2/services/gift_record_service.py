# -*- coding: utf-8 -*-
"""
送卡记录服务。

负责送卡流水状态维护与 account_cards 数量同步。
"""

from dataclasses import dataclass
import re
from typing import Optional
from datetime import datetime

from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import AccountGiftRecord
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str


COUNT_TRANSITION_PATTERN = re.compile(r"(\d+)\s*>\s*(\d+)")


@dataclass(slots=True, frozen=True)
class GiftRecordData:
    """送卡记录纯数据。"""

    id: int
    account_id: int
    target_account_id: Optional[int]
    target_friend_id: str
    card_id: Optional[int]
    card_set_code: Optional[str]
    card_number: Optional[int]
    before_count: Optional[int]
    after_count: Optional[int]
    count_source: Optional[str]
    status: str
    error_code: Optional[str]
    error_message: Optional[str]
    biz_date_local: str
    created_at: datetime
    updated_at: datetime


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

    @staticmethod
    def _record_to_data(record: AccountGiftRecord) -> GiftRecordData:
        """将送卡记录模型转成纯数据。"""
        if record.id is None:
            raise RuntimeError("送卡记录 ID 为空，无法构造数据")
        return GiftRecordData(
            id=record.id,
            account_id=record.account_id,
            target_account_id=record.target_account_id,
            target_friend_id=record.target_friend_id,
            card_id=record.card_id,
            card_set_code=record.card_set_code,
            card_number=record.card_number,
            before_count=record.before_count,
            after_count=record.after_count,
            count_source=record.count_source,
            status=record.status,
            error_code=record.error_code,
            error_message=record.error_message,
            biz_date_local=record.biz_date_local,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    def ensure_daily_record(
        cls,
        account_id: int,
        target_friend_id: str,
        target_account_id: Optional[int],
        card_set_code: Optional[str],
        card_number: Optional[int],
    ) -> GiftRecordData:
        """创建或读取当天送卡记录。"""
        with session_scope() as session:
            record = RepositoryFactory(session).account_gift_records().create_or_get_daily(
                account_id=account_id,
                target_friend_id=target_friend_id,
                target_account_id=target_account_id,
                card_set_code=card_set_code,
                card_number=card_number,
                biz_date_local=cls.today_local_date(),
            )
            return cls._record_to_data(record)

    @classmethod
    def is_daily_success(
        cls,
        account_id: int,
        target_friend_id: str,
    ) -> bool:
        """判断当日是否已成功送卡。"""
        with session_scope() as session:
            return (
                RepositoryFactory(session)
                .account_gift_records()
                .get_daily_success_record(
                    account_id=account_id,
                    target_friend_id=target_friend_id,
                    biz_date_local=cls.today_local_date(),
                )
                is not None
            )

    @classmethod
    def has_daily_attempt(
        cls,
        account_id: int,
        target_friend_id: str,
    ) -> bool:
        """判断当日是否已执行过一次送卡尝试（不含 init）。"""
        with session_scope() as session:
            record = RepositoryFactory(session).account_gift_records().get_daily_record(
                account_id=account_id,
                target_friend_id=target_friend_id,
                biz_date_local=cls.today_local_date(),
            )
            return record is not None and record.status != "init"

    @staticmethod
    def ensure_send_card_daily_pending(account_id: int) -> bool:
        """确保目标账号的 send_card_daily 任务处于 pending。"""
        with session_scope() as session:
            RepositoryFactory(session).task_instances().ensure_pending(
                account_id=account_id,
                task_type="send_card_daily",
                reset_type="interval",
            )
        return True

    @staticmethod
    def update_status(
        record_id: int,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> GiftRecordData:
        """更新记录状态与错误信息。"""
        with session_scope() as session:
            repo = RepositoryFactory(session).account_gift_records()
            db_record = repo.get_by_id(record_id)
            if db_record is None:
                raise RuntimeError("更新送卡记录失败：记录不存在")
            db_record.status = status
            db_record.error_code = error_code
            db_record.error_message = error_message
            db_record.updated_at = datetime.now()
            session.flush()
            session.refresh(db_record)
            return GiftRecordService._record_to_data(db_record)

    @staticmethod
    def mark_success_and_sync_count(
        record_id: int,
        card_id: Optional[int],
        before_count: Optional[int],
        after_count: Optional[int],
    ) -> GiftRecordData:
        """标记成功并同步 account_cards 的剩余数量。"""
        resolved_after_count = after_count
        count_source = "ui"

        with session_scope() as session:
            repos = RepositoryFactory(session)
            account_card_repo = repos.account_cards()
            gift_record_repo = repos.account_gift_records()
            db_record = gift_record_repo.get_by_id(record_id)
            if db_record is None:
                raise RuntimeError("送卡成功收敛失败：记录不存在")

            db_row = None
            if card_id is not None:
                db_row = account_card_repo.get(db_record.account_id, card_id)

            if resolved_after_count is None:
                if before_count is not None:
                    resolved_after_count = max(before_count - 1, 0)
                    count_source = "fallback"
                elif db_row is not None:
                    resolved_after_count = max(int(db_row.count) - 1, 0)
                    count_source = "db"
            db_record.card_id = card_id
            db_record.before_count = before_count
            db_record.after_count = resolved_after_count
            db_record.count_source = (
                count_source if resolved_after_count is not None else None
            )
            db_record.status = "success"
            db_record.error_code = None
            db_record.error_message = None
            db_record.updated_at = datetime.now()
            session.flush()
            session.refresh(db_record)

            if card_id is not None and resolved_after_count is not None:
                account_card_repo.upsert(
                    account_id=db_record.account_id,
                    card_id=card_id,
                    count=resolved_after_count,
                    yolo_conf=db_row.yolo_conf if db_row else None,
                    hash_similarity=db_row.hash_similarity if db_row else None,
                )

                # 双向同步：送卡成功后，目标账号该卡数量 +1。
                if isinstance(db_record.target_account_id, int):
                    target_row = account_card_repo.get(db_record.target_account_id, card_id)
                    account_card_repo.increase_owned(
                        account_id=db_record.target_account_id,
                        card_id=card_id,
                        amount=1,
                        yolo_conf=target_row.yolo_conf if target_row else None,
                        hash_similarity=target_row.hash_similarity
                        if target_row
                        else None,
                    )

            return GiftRecordService._record_to_data(db_record)
