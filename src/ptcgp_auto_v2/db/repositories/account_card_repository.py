from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountCard


class AccountCardRepository:
    """账号-卡牌关联数据访问层"""

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
