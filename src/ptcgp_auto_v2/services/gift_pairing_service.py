# -*- coding: utf-8 -*-
"""
送卡配对服务。

负责读取固定送卡配对关系，并在缺失时做一次性补齐。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import case
from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.db.engine import session_scope
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

    @classmethod
    def ensure_pair_for_account(cls, account_id: int) -> GiftPairData | None:
        """读取账号固定送卡配对；若缺失则按既有固定关系补齐一次。"""
        with session_scope() as session:
            repos = RepositoryFactory(session)
            pair_repo = repos.account_gift_pairs()
            pair = pair_repo.get_by_account(account_id)
            if pair is not None:
                cls._refresh_target_friend_snapshot(
                    pair_repo=pair_repo,
                    account_repo=repos.accounts(),
                    pair=pair,
                )
                return cls._pair_to_data(pair)

            ranked_accounts = cls._load_ranked_accounts(session)
            friend_map = {
                item["account_id"]: item["friend_id"]
                for item in ranked_accounts
                if item["friend_id"]
            }
            sorted_ids = [item["account_id"] for item in ranked_accounts]
            existing_pairs = pair_repo.list_all()

            cls._backfill_reverse_pairs(
                pair_repo=pair_repo,
                existing_pairs=existing_pairs,
                friend_map=friend_map,
            )

            existing_pair_map = cls._build_existing_pair_map(existing_pairs)
            missing_pairs = cls.plan_missing_pairs(
                sorted_account_ids=sorted_ids,
                existing_pair_map=existing_pair_map,
            )
            for left_id, right_id in missing_pairs:
                left_friend_id = friend_map.get(left_id)
                right_friend_id = friend_map.get(right_id)
                if not left_friend_id or not right_friend_id:
                    continue
                pair_repo.create_if_missing(
                    account_id=left_id,
                    target_friend_id=right_friend_id,
                    target_account_id=right_id,
                    strategy=cls.STRATEGY_FIXED_A1_153,
                )
                pair_repo.create_if_missing(
                    account_id=right_id,
                    target_friend_id=left_friend_id,
                    target_account_id=left_id,
                    strategy=cls.STRATEGY_FIXED_A1_153,
                )

            pair = pair_repo.get_by_account(account_id)
            if pair is not None:
                cls._refresh_target_friend_snapshot(
                    pair_repo=pair_repo,
                    account_repo=repos.accounts(),
                    pair=pair,
                )
            return cls._pair_to_data(pair) if pair else None

    @staticmethod
    def plan_missing_pairs(
        sorted_account_ids: list[int],
        existing_pair_map: dict[int, int],
    ) -> list[tuple[int, int]]:
        """为尚未建立固定关系的账号生成一次性配对。"""
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
    def _refresh_target_friend_snapshot(
        *,
        pair_repo,
        account_repo,
        pair: AccountGiftPair,
    ) -> None:
        """用目标账号当前 friend_id 刷新配对里的执行快照。"""
        target_account_id = pair.target_account_id
        if not isinstance(target_account_id, int):
            return
        target_account = account_repo.get_by_id(target_account_id)
        if target_account is None or not target_account.friend_id:
            return
        current_friend_id = str(target_account.friend_id)
        if pair.target_friend_id == current_friend_id:
            return
        if pair.id is None:
            raise RuntimeError("送卡配对 ID 为空，无法刷新目标快照")
        pair_repo.update_target_friend_id(pair.id, current_friend_id)
        pair.target_friend_id = current_friend_id

    @classmethod
    def _backfill_reverse_pairs(
        cls,
        *,
        pair_repo,
        existing_pairs: list[AccountGiftPair],
        friend_map: dict[int, str],
    ) -> None:
        """为已有单向固定配对补齐反向记录。"""
        existing_by_account = {
            row.account_id: row for row in existing_pairs if row.account_id is not None
        }
        for row in existing_pairs:
            target_id = row.target_account_id
            if not isinstance(target_id, int):
                continue
            if target_id in existing_by_account:
                continue
            source_friend_id = friend_map.get(row.account_id)
            if not source_friend_id:
                continue
            reverse = pair_repo.create_if_missing(
                account_id=target_id,
                target_friend_id=source_friend_id,
                target_account_id=row.account_id,
                strategy=row.strategy or cls.STRATEGY_FIXED_A1_153,
            )
            existing_by_account[target_id] = reverse
            existing_pairs.append(reverse)

    @staticmethod
    def _build_existing_pair_map(
        existing_pairs: list[AccountGiftPair],
    ) -> dict[int, int]:
        """基于已建立固定关系锁定账号，避免后续重排。"""
        existing_by_account = {
            row.account_id: row for row in existing_pairs if row.account_id is not None
        }
        pair_map: dict[int, int] = {}
        for row in existing_pairs:
            target_id = row.target_account_id
            if not isinstance(target_id, int):
                continue
            if row.account_id == target_id:
                continue
            reverse = existing_by_account.get(target_id)
            if reverse is None or reverse.target_account_id != row.account_id:
                continue
            pair_map[row.account_id] = target_id
            pair_map[target_id] = row.account_id
        return pair_map

    @staticmethod
    def _load_ranked_accounts(session: Session) -> list[dict]:
        """加载可参与送卡的账号并按 SR/SAR 总量排序。"""
        rarity_score = func.coalesce(
            func.sum(
                case(
                    (col(Card.rarity).in_(["SR", "SAR"]), col(AccountCard.count)),
                    else_=0,
                )
            ),
            0,
        )

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
