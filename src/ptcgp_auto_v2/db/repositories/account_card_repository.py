from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import String, Select, case, cast, distinct, func, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import Account, AccountCard, AccountStat, Card, CardPack
from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS
from ptcgp_auto_v2.config.rarity_icons import RARITY_META
from .base import BaseRepository


class AccountCardRepository(BaseRepository):
    """账号-卡牌关联数据访问层"""

    # 从 RARITY_META 动态构建（单一数据源）
    _rarity_order_map = {code: meta["priority"] for code, meta in RARITY_META.items()}

    def _build_account_search_filters(self, account_query: str) -> list[Any]:
        """构建账号搜索条件，仅支持旧的三字段查询。"""
        like_value = f"%{account_query}%"
        return [
            cast(Account.id, String).ilike(like_value),
            Account.nickname.ilike(like_value),
            Account.friend_id.ilike(like_value),
        ]

    def _build_card_ownership_subquery(self, account_query: str):
        """构建按卡牌聚合后的拥有信息子查询。"""
        statement = select(
            col(AccountCard.card_id).label("card_id"),
            func.count(distinct(col(AccountCard.account_id))).label("accounts_count"),
            func.coalesce(func.sum(col(AccountCard.count)), 0).label("total_count"),
            func.max(col(AccountCard.created_at)).label("latest_acquired_at"),
        )

        if account_query:
            statement = statement.join(
                Account, col(Account.id) == col(AccountCard.account_id)
            ).where(or_(*self._build_account_search_filters(account_query)))

        return statement.group_by(col(AccountCard.card_id)).subquery()

    def _apply_card_filters(
        self,
        statement: Select,
        *,
        rarities: List[str],
        card_types: List[str],
        set_codes: List[str],
        pack_names: List[str],
        elements: List[str],
    ) -> Select:
        """统一追加卡牌元数据筛选条件。"""
        if rarities:
            statement = statement.where(col(Card.rarity).in_(rarities))

        if card_types:
            statement = statement.where(col(Card.type).in_(card_types))

        if set_codes:
            statement = statement.where(col(Card.set_code).in_(set_codes))

        if elements:
            statement = statement.where(func.lower(col(Card.element)).in_(elements))

        if pack_names:
            pack_subquery = (
                select(CardPack.card_id)
                .where(col(CardPack.pack_name).in_(pack_names))
                .distinct()
            )
            statement = statement.where(col(Card.id).in_(pack_subquery))

        return statement

    def _apply_ownership_scope(
        self,
        statement: Select,
        *,
        ownership_total_count: Any,
        ownership_scope: str,
    ) -> Select:
        """统一追加拥有范围过滤。"""
        if ownership_scope == "missing":
            return statement.where(ownership_total_count <= 0)
        if ownership_scope == "all":
            return statement
        return statement.where(ownership_total_count > 0)

    @staticmethod
    def _get_by_account_and_card(
        session: Session, account_id: int, card_id: int
    ) -> Optional[AccountCard]:
        """读取单条账号卡牌记录。"""
        statement = select(AccountCard).where(
            AccountCard.account_id == account_id,
            AccountCard.card_id == card_id,
        )
        return session.exec(statement).first()

    def get(self, account_id: int, card_id: int) -> Optional[AccountCard]:
        return self._get_by_account_and_card(self.session, account_id, card_id)

    def upsert(
        self,
        account_id: int,
        card_id: int,
        count: int = 1,
        yolo_conf: Optional[float] = None,
        hash_similarity: Optional[float] = None,
    ) -> AccountCard:
        existing = self._get_by_account_and_card(self.session, account_id, card_id)
        if existing is None:
            existing = AccountCard(
                account_id=account_id,
                card_id=card_id,
                count=count,
                yolo_conf=yolo_conf,
                hash_similarity=hash_similarity,
            )
        else:
            existing.count = count
            existing.yolo_conf = yolo_conf
            existing.hash_similarity = hash_similarity
            existing.updated_at = datetime.now()
        self.session.add(existing)
        self._finish_write(existing)
        return existing

    def increase_owned(
        self,
        account_id: int,
        card_id: int,
        amount: int = 0,
        yolo_conf: Optional[float] = None,
        hash_similarity: Optional[float] = None,
    ) -> AccountCard:
        """统一维护拥有数量：amount=0 时至少写为 1，amount>0 时按增量更新。"""
        if amount < 0:
            raise ValueError("amount 不能小于 0")

        existing = self._get_by_account_and_card(self.session, account_id, card_id)
        current_count = int(existing.count or 0) if existing else 0
        next_count = max(current_count + amount, 1)
        if existing is None:
            existing = AccountCard(
                account_id=account_id,
                card_id=card_id,
                count=next_count,
                yolo_conf=yolo_conf,
                hash_similarity=hash_similarity,
            )
        else:
            existing.count = next_count
            existing.yolo_conf = yolo_conf
            existing.hash_similarity = hash_similarity
            existing.updated_at = datetime.now()
        self.session.add(existing)
        self._finish_write(existing)
        return existing

    def list_owned_cards(
        self,
        page: int,
        page_size: int,
        account_query: Optional[str] = None,
        rarities: Optional[List[str]] = None,
        card_types: Optional[List[str]] = None,
        set_codes: Optional[List[str]] = None,
        pack_names: Optional[List[str]] = None,
        elements: Optional[List[str]] = None,
        sort_by: str = "rarity",
        ownership_scope: str = "owned",
    ) -> List[Dict[str, Any]]:
        rarities = rarities or []
        card_types = card_types or []
        set_codes = set_codes or []
        pack_names = pack_names or []
        elements = [str(e).lower() for e in (elements or []) if e]
        normalized_account_query = (account_query or "").strip()
        normalized_scope = ownership_scope if ownership_scope in {
            "owned",
            "missing",
            "all",
        } else "owned"

        rarity_case = case(
            *[
                (col(Card.rarity) == rarity, order)
                for rarity, order in self._rarity_order_map.items()
            ],
            else_=0,
        )
        ownership_subquery = self._build_card_ownership_subquery(normalized_account_query)
        accounts_count = func.coalesce(ownership_subquery.c.accounts_count, 0)
        total_count = func.coalesce(ownership_subquery.c.total_count, 0)
        latest_acquired = ownership_subquery.c.latest_acquired_at
        acquired_missing_rank = case((latest_acquired.is_(None), 1), else_=0)

        statement = (
            select(
                Card,
                accounts_count.label("accounts_count"),
                total_count.label("total_count"),
                latest_acquired.label("latest_acquired_at"),
            )
            .outerjoin(ownership_subquery, ownership_subquery.c.card_id == col(Card.id))
        )
        statement = self._apply_card_filters(
            statement,
            rarities=rarities,
            card_types=card_types,
            set_codes=set_codes,
            pack_names=pack_names,
            elements=elements,
        )
        statement = self._apply_ownership_scope(
            statement,
            ownership_total_count=total_count,
            ownership_scope=normalized_scope,
        )
        if sort_by == "acquired":
            statement = statement.order_by(
                acquired_missing_rank.asc(),
                latest_acquired.desc(),
                rarity_case.desc(),
                col(Card.set_code),
                col(Card.number),
            )
        elif sort_by == "count":
            statement = statement.order_by(
                total_count.desc(),
                rarity_case.desc(),
                col(Card.set_code),
                col(Card.number),
            )
        else:
            statement = statement.order_by(
                rarity_case.desc(),
                col(Card.set_code),
                col(Card.number),
            )
        statement = statement.offset(page * page_size).limit(page_size + 1)
        rows = self.session.exec(statement).all()
        items = []
        for card, accounts_count_value, total_count_value, latest_acquired_value in rows:
            normalized_total_count = int(total_count_value or 0)
            items.append(
                {
                    "card": card,
                    "owned_accounts_count": int(accounts_count_value or 0),
                    "total_count": normalized_total_count,
                    "latest_acquired_at": latest_acquired_value,
                    "ownership_state": (
                        "owned" if normalized_total_count > 0 else "missing"
                    ),
                }
            )
        return items

    def count_cards_by_scope(
        self,
        account_query: Optional[str] = None,
        rarities: Optional[List[str]] = None,
        card_types: Optional[List[str]] = None,
        set_codes: Optional[List[str]] = None,
        pack_names: Optional[List[str]] = None,
        elements: Optional[List[str]] = None,
        ownership_scope: str = "owned",
    ) -> int:
        """统计当前列表条件下的卡牌数量。"""
        rarities = rarities or []
        card_types = card_types or []
        set_codes = set_codes or []
        pack_names = pack_names or []
        elements = [str(e).lower() for e in (elements or []) if e]
        normalized_account_query = (account_query or "").strip()
        normalized_scope = ownership_scope if ownership_scope in {
            "owned",
            "missing",
            "all",
        } else "owned"

        ownership_subquery = self._build_card_ownership_subquery(normalized_account_query)
        total_count = func.coalesce(ownership_subquery.c.total_count, 0)

        statement = (
            select(func.count())
            .select_from(Card)
            .outerjoin(ownership_subquery, ownership_subquery.c.card_id == col(Card.id))
        )
        statement = self._apply_card_filters(
            statement,
            rarities=rarities,
            card_types=card_types,
            set_codes=set_codes,
            pack_names=pack_names,
            elements=elements,
        )
        statement = self._apply_ownership_scope(
            statement,
            ownership_total_count=total_count,
            ownership_scope=normalized_scope,
        )
        return int(self.session.exec(statement).one() or 0)

    def get_high_rarity_progress(self) -> List[Dict[str, int | str]]:
        """统计全局高稀有度卡牌进度。"""
        ownership_subquery = self._build_card_ownership_subquery("")
        total_count = func.coalesce(ownership_subquery.c.total_count, 0)
        owned_case = case((total_count > 0, 1), else_=0)

        statement = (
            select(
                col(Card.rarity).label("rarity"),
                func.count(col(Card.id)).label("total_cards"),
                func.sum(owned_case).label("owned_cards"),
            )
            .outerjoin(ownership_subquery, ownership_subquery.c.card_id == col(Card.id))
            .where(col(Card.rarity).in_(HIGH_RARITY_TARGETS))
            .group_by(col(Card.rarity))
        )
        rows = self.session.exec(statement).all()

        progress_map = {
            str(rarity): {
                "rarity": str(rarity),
                "owned_count": int(owned_cards or 0),
                "total_count": int(total_cards or 0),
            }
            for rarity, total_cards, owned_cards in rows
        }
        return [
            progress_map.get(
                rarity,
                {"rarity": rarity, "owned_count": 0, "total_count": 0},
            )
            for rarity in HIGH_RARITY_TARGETS
        ]

    def get_owned_card_accounts(self, card_id: int) -> Dict[str, Any]:
        return self.list_owned_card_accounts_page(
            card_id=card_id,
            q="",
            sort_by="account_id",
            sort_order="asc",
            page=0,
            page_size=1000000,
        )

    def list_owned_card_accounts_page(
        self,
        *,
        card_id: int,
        q: str,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """分页获取拥有指定卡牌的账号列表。"""
        statement = (
            select(AccountCard, Account, AccountStat)
            .join(Account, col(Account.id) == col(AccountCard.account_id))
            .outerjoin(AccountStat, col(AccountStat.account_id) == col(Account.id))
            .where(AccountCard.card_id == card_id)
        )
        total_statement = (
            select(
                func.count(col(AccountCard.account_id)),
                func.coalesce(func.sum(col(AccountCard.count)), 0),
            )
            .select_from(AccountCard)
            .join(Account, col(Account.id) == col(AccountCard.account_id))
            .where(AccountCard.card_id == card_id)
        )
        normalized_q = q.strip()
        if normalized_q:
            condition = or_(*self._build_account_search_filters(normalized_q))
            statement = statement.where(condition)
            total_statement = total_statement.where(condition)
        reverse = sort_order == "desc"
        if sort_by == "friend_id":
            order_column = col(Account.friend_id)
        elif sort_by == "nickname":
            order_column = col(Account.nickname)
        elif sort_by == "count":
            order_column = col(AccountCard.count)
        elif sort_by == "exchange_points":
            order_column = col(AccountStat.exchange_points)
        else:
            order_column = col(Account.id)
        statement = statement.order_by(
            order_column.desc() if reverse else order_column.asc(),
            col(Account.id).desc() if reverse else col(Account.id).asc(),
        )
        statement = statement.offset(page * page_size).limit(page_size)
        rows = self.session.exec(statement).all()
        total_items, total_count = self.session.exec(total_statement).one()
        accounts = []
        for account_card, account, account_stat in rows:
            accounts.append(
                {
                    "account_id": account.id,
                    "friend_id": account.friend_id,
                    "game_id": account.game_id,
                    "nickname": account.nickname,
                    "count": account_card.count,
                    "exchange_points": (
                        account_stat.exchange_points if account_stat else None
                    ),
                }
            )
        return {
            "accounts": accounts,
            "total_accounts": int(total_items or 0),
            "total_count": int(total_count or 0),
        }
