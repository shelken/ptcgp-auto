# -*- coding: utf-8 -*-
"""
送卡配对服务。

负责根据账号资产排序生成稳定送卡关系，并在任务执行前做增量补齐。
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import case
from sqlmodel import col, func, select

from ptcgp_auto_v2.db.engine import get_session, session_scope
from ptcgp_auto_v2.db.models import Account, AccountCard, AccountGiftPair, Card
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.utils.account_cooldown import is_account_past_days


@dataclass(slots=True, frozen=True)
class GiftPairData:
    """送卡配对纯数据。"""

    id: int
    account_id: int
    target_account_id: int | None
    target_friend_id: str
    strategy: str


class GiftPairingService:
    """送卡配对服务。"""

    STRATEGY_FIXED_A1_153 = "fixed_card_a1_153"
    COOLDOWN_DAYS = 14

    @classmethod
    def is_account_past_cooldown(cls, created_at: Optional[datetime]) -> bool:
        """判断账号是否已过送卡冷冻期。"""
        return is_account_past_days(created_at, cls.COOLDOWN_DAYS)

    @staticmethod
    def plan_missing_pairs(
        sorted_account_ids: list[int],
        existing_pair_map: dict[int, int],
    ) -> list[tuple[int, int]]:
        """在既有稳定关系不变的前提下，为未配对账号生成补齐配对。"""
        locked_account_ids = set(existing_pair_map) | set(existing_pair_map.values())

        unpaired: list[int] = [
            account_id
            for account_id in sorted_account_ids
            if account_id not in locked_account_ids
        ]

        pairs: list[tuple[int, int]] = []
        for index in range(0, len(unpaired) - 1, 2):
            pairs.append((unpaired[index], unpaired[index + 1]))
        return pairs

    @classmethod
    def ensure_pairs_for_account(cls, account_id: int) -> GiftPairData | None:
        """增量补齐送卡配对，并返回指定账号的当前有效配对。"""
        ranked_accounts = cls._load_ranked_accounts()
        friend_map = {
            item["account_id"]: item["friend_id"]
            for item in ranked_accounts
            if item["friend_id"]
        }
        sorted_ids = [item["account_id"] for item in ranked_accounts]

        with session_scope() as session:
            pair_repo = RepositoryFactory(session).account_gift_pairs()
            active_pairs = pair_repo.get_all_active()
            active_map = {row.account_id: row for row in active_pairs}

            existing_pair_map = cls._build_valid_existing_pair_map(
                active_map,
                friend_map,
            )

            for row in active_pairs:
                if row.account_id not in existing_pair_map:
                    pair_repo.deactivate_active_pair(row.account_id)

            missing_pairs = cls.plan_missing_pairs(
                sorted_account_ids=sorted_ids,
                existing_pair_map=existing_pair_map,
            )
            for left_id, right_id in missing_pairs:
                left_friend_id = friend_map.get(left_id)
                right_friend_id = friend_map.get(right_id)
                if not left_friend_id or not right_friend_id:
                    continue
                pair_repo.upsert_active_pair(
                    account_id=left_id,
                    target_friend_id=right_friend_id,
                    target_account_id=right_id,
                    strategy=cls.STRATEGY_FIXED_A1_153,
                )
                pair_repo.upsert_active_pair(
                    account_id=right_id,
                    target_friend_id=left_friend_id,
                    target_account_id=left_id,
                    strategy=cls.STRATEGY_FIXED_A1_153,
                )

            pair = pair_repo.get_active_by_account(account_id)
            return cls._pair_to_data(pair) if pair else None

    @staticmethod
    def _pair_to_data(pair: AccountGiftPair) -> GiftPairData:
        """将送卡配对模型转成纯数据。"""
        if pair.id is None:
            raise RuntimeError("送卡配对 ID 为空，无法构造数据")
        return GiftPairData(
            id=pair.id,
            account_id=pair.account_id,
            target_account_id=pair.target_account_id,
            target_friend_id=pair.target_friend_id,
            strategy=pair.strategy,
        )

    @staticmethod
    def _build_valid_existing_pair_map(
        active_map: dict[int, AccountGiftPair],
        friend_map: dict[int, str],
    ) -> dict[int, int]:
        """构建有效且双向一致的稳定配对映射。"""
        pair_map: dict[int, int] = {}
        for account_id, row in active_map.items():
            target_id = row.target_account_id
            if target_id is None:
                continue
            reverse = active_map.get(target_id)
            if reverse is None:
                continue
            if reverse.target_account_id != account_id:
                continue

            expected_target_friend = friend_map.get(target_id)
            expected_reverse_friend = friend_map.get(account_id)
            if not expected_target_friend or not expected_reverse_friend:
                continue
            if row.target_friend_id != expected_target_friend:
                continue
            if reverse.target_friend_id != expected_reverse_friend:
                continue

            pair_map[account_id] = target_id
            pair_map[target_id] = account_id
        return pair_map

    @staticmethod
    def _load_ranked_accounts() -> list[dict]:
        """加载参与送卡的账号并按 SR/SAR 总量排序。"""
        cooldown_threshold = datetime.now() - timedelta(
            days=GiftPairingService.COOLDOWN_DAYS
        )
        rarity_score = func.coalesce(
            func.sum(
                case(
                    (col(Card.rarity).in_(["SR", "SAR"]), col(AccountCard.count)),
                    else_=0,
                )
            ),
            0,
        )

        with get_session() as session:
            statement = (
                select(
                    col(Account.id),
                    col(Account.friend_id),
                    rarity_score.label("rarity_score"),
                )
                .select_from(Account)
                .outerjoin(AccountCard, col(Account.id) == col(AccountCard.account_id))
                .outerjoin(Card, col(AccountCard.card_id) == col(Card.id))
                .where(
                    col(Account.friend_id).is_not(None),
                    col(Account.friend_id) != "",
                    col(Account.created_at) <= cooldown_threshold,
                )
                .group_by(col(Account.id), col(Account.friend_id))
                .order_by(rarity_score.desc(), col(Account.id).asc())
            )
            rows = session.exec(statement).all()

        return [
            {
                "account_id": account_id,
                "friend_id": str(friend_id),
                "rarity_score": int(rarity_score_value or 0),
            }
            for account_id, friend_id, rarity_score_value in rows
            if isinstance(account_id, int) and friend_id
        ]
