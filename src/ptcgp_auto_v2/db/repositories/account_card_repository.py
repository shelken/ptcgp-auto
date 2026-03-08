from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import case, distinct, func
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import Account, AccountCard, AccountStat, Card, CardPack


class AccountCardRepository:
    """账号-卡牌关联数据访问层"""

    _rarity_order_map = {
        "C": 1,
        "U": 2,
        "R": 3,
        "RR": 4,
        "AR": 5,
        "SR": 6,
        "SAR": 7,
        "UR": 8,
        "IM": 9,
        "S": 10,
        "SSR": 11,
    }

    def get(self, account_id: int, card_id: int) -> Optional[AccountCard]:
        with Session(get_engine()) as session:
            statement = select(AccountCard).where(
                AccountCard.account_id == account_id,
                AccountCard.card_id == card_id,
            )
            return session.exec(statement).first()

    def upsert(
        self,
        account_id: int,
        card_id: int,
        count: int = 1,
        yolo_conf: Optional[float] = None,
        hash_similarity: Optional[float] = None,
    ) -> AccountCard:
        with Session(get_engine()) as session:
            statement = select(AccountCard).where(
                AccountCard.account_id == account_id,
                AccountCard.card_id == card_id,
            )
            existing = session.exec(statement).first()
            if existing:
                existing.count = count
                existing.yolo_conf = yolo_conf
                existing.hash_similarity = hash_similarity
                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing

            record = AccountCard(
                account_id=account_id,
                card_id=card_id,
                count=count,
                yolo_conf=yolo_conf,
                hash_similarity=hash_similarity,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list_owned_cards(
        self,
        page: int,
        page_size: int,
        account_id: Optional[int] = None,
        rarities: Optional[List[str]] = None,
        card_types: Optional[List[str]] = None,
        set_codes: Optional[List[str]] = None,
        pack_names: Optional[List[str]] = None,
        elements: Optional[List[str]] = None,
        sort_by: str = "rarity",
    ) -> List[Dict[str, Any]]:
        rarities = rarities or []
        card_types = card_types or []
        set_codes = set_codes or []
        pack_names = pack_names or []
        elements = [str(e).lower() for e in (elements or []) if e]

        rarity_case = case(
            *[
                (col(Card.rarity) == rarity, order)
                for rarity, order in self._rarity_order_map.items()
            ],
            else_=0,
        )

        accounts_count = func.count(distinct(col(AccountCard.account_id)))
        total_count = func.sum(col(AccountCard.count))
        latest_acquired = func.max(col(AccountCard.created_at))

        with Session(get_engine()) as session:
            statement = (
                select(
                    Card,
                    accounts_count.label("accounts_count"),
                    total_count.label("total_count"),
                )
                .join(AccountCard, col(AccountCard.card_id) == col(Card.id))
                .group_by(col(Card.id))  # type: ignore[arg-type]
            )

            if account_id:
                statement = statement.where(col(AccountCard.account_id) == account_id)

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

            if sort_by == "acquired":
                statement = statement.order_by(
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

            statement = statement.offset(page * page_size).limit(page_size)

            rows = session.exec(statement).all()
            items = []
            for row in rows:
                card, accounts_count_value, total_count_value = row
                items.append(
                    {
                        "card": card,
                        "owned_accounts_count": int(accounts_count_value or 0),
                        "total_count": int(total_count_value or 0),
                    }
                )
            return items

    def get_owned_card_accounts(self, card_id: int) -> Dict[str, Any]:
        with Session(get_engine()) as session:
            statement = (
                select(AccountCard, Account, AccountStat)
                .join(Account, col(Account.id) == col(AccountCard.account_id))
                .outerjoin(AccountStat, col(AccountStat.account_id) == col(Account.id))
                .where(AccountCard.card_id == card_id)
                .order_by(col(Account.id))
            )
            rows = session.exec(statement).all()

            accounts = []
            total_count = 0
            for account_card, account, account_stat in rows:
                total_count += account_card.count
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
                "total_accounts": len(accounts),
                "total_count": total_count,
            }
