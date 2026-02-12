# -*- coding: utf-8 -*-
"""
ExchangeCardRequestRepository

交换卡牌请求数据访问层。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import ExchangeCardRequest


class ExchangeCardRequestRepository:
    """交换卡牌请求数据访问。"""

    ACTIVE_STATUSES = {"sending", "sended"}
    FINAL_STATUSES = {"completed", "failed", "canceled"}

    def create(
        self,
        from_account_id: int,
        to_friend_id: str,
        target_card_id: int,
        target_card_rarity: str,
        to_account_id: Optional[int] = None,
        status: str = "sending",
    ) -> Optional[ExchangeCardRequest]:
        """创建交换请求；同一账号仅允许一条活跃请求。"""
        with Session(get_engine()) as session:
            active = self._get_active_by_account_with_session(session, from_account_id)
            if active is not None:
                return None

            request = ExchangeCardRequest(
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                to_friend_id=to_friend_id,
                target_card_id=target_card_id,
                target_card_rarity=target_card_rarity,
                status=status,
            )
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def get_by_id(self, request_id: int) -> Optional[ExchangeCardRequest]:
        """按主键查询请求。"""
        with Session(get_engine()) as session:
            return session.get(ExchangeCardRequest, request_id)

    def get_active_by_account(
        self, from_account_id: int
    ) -> Optional[ExchangeCardRequest]:
        """查询账号当前活跃请求（sending/sended）。"""
        with Session(get_engine()) as session:
            return self._get_active_by_account_with_session(session, from_account_id)

    def list_due_sended_requests(self, now: datetime) -> list[ExchangeCardRequest]:
        """查询已到 next_check_at 的 sended 请求。"""
        with Session(get_engine()) as session:
            statement = (
                select(ExchangeCardRequest)
                .where(
                    ExchangeCardRequest.status == "sended",
                    ExchangeCardRequest.next_check_at.is_not(None),
                    col(ExchangeCardRequest.next_check_at) <= now,
                )
                .order_by(col(ExchangeCardRequest.next_check_at))
            )
            return list(session.exec(statement).all())

    def update(self, request: ExchangeCardRequest) -> ExchangeCardRequest:
        """更新请求记录。"""
        with Session(get_engine()) as session:
            request.updated_at = datetime.now()
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def _get_active_by_account_with_session(
        self,
        session: Session,
        from_account_id: int,
    ) -> Optional[ExchangeCardRequest]:
        """在给定 Session 内查询活跃请求。"""
        statement = (
            select(ExchangeCardRequest)
            .where(
                ExchangeCardRequest.from_account_id == from_account_id,
                col(ExchangeCardRequest.status).in_(self.ACTIVE_STATUSES),
            )
            .order_by(col(ExchangeCardRequest.created_at))
            .limit(1)
        )
        return session.exec(statement).first()
