# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import tuple_
from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import PackCard, PackRecord
from ptcgp_auto_v2.utils.game_time import get_game_day_window

logger = logging.getLogger(__name__)


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
            day_start, day_end = get_game_day_window()
            statement = (
                select(PackRecord)
                .where(
                    PackRecord.account_id == account_id,
                    PackRecord.opened_at >= day_start,
                    PackRecord.opened_at < day_end,
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
        cards: list[dict[str, Any]] | None = None,
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

    def get_pack_usage_counts(self, pack_keys: list[tuple[str, str]]) -> dict:
        """统计指定 pack_code/pack_name 的开包次数。"""
        if not pack_keys:
            return {}

        with Session(get_engine()) as session:
            statement = (
                select(
                    PackRecord.pack_code,
                    PackRecord.pack_name,
                    func.count().label("count"),
                )
                .where(
                    tuple_(PackRecord.pack_code, PackRecord.pack_name).in_(pack_keys)
                )
                .group_by(PackRecord.pack_code, PackRecord.pack_name)
            )
            results = session.exec(statement).all()
            counts = {(code, name): count for code, name, count in results}

        for key in pack_keys:
            counts.setdefault(key, 0)
        return counts
