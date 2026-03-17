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

    def create(
        self,
        from_account_id: int,
        to_friend_id: str,
        target_card_id: int,
        target_card_rarity: str,
        to_account_id: Optional[int] = None,
        to_nickname: Optional[str] = None,
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
                to_nickname=to_nickname,
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

    def has_active_request(self, from_account_id: int) -> bool:
        """判断账号是否存在活跃请求（sending/sended）。"""
        return self.get_active_by_account(from_account_id) is not None

    def update(self, request: ExchangeCardRequest) -> ExchangeCardRequest:
        """更新请求记录。"""
        with Session(get_engine()) as session:
            request.updated_at = datetime.now()
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def mark_sended(
        self,
        request: ExchangeCardRequest,
        next_check_at: Optional[datetime],
    ) -> ExchangeCardRequest:
        """标记请求为 sended。"""
        request.status = "sended"
        request.next_check_at = next_check_at
        request.failed_reason = None
        return self.update(request)

    def mark_failed(
        self, request: ExchangeCardRequest, reason: str
    ) -> ExchangeCardRequest:
        """标记请求为 failed。"""
        request.status = "failed"
        request.failed_reason = reason
        request.next_check_at = None
        return self.update(request)

    def mark_canceled(
        self,
        request: ExchangeCardRequest,
        reason: Optional[str] = None,
    ) -> ExchangeCardRequest:
        """标记请求为 canceled。"""
        request.status = "canceled"
        request.cancel_reason = reason
        request.next_check_at = None
        return self.update(request)

    def mark_completed(self, request: ExchangeCardRequest) -> ExchangeCardRequest:
        """标记请求为 completed。"""
        request.status = "completed"
        request.next_check_at = None
        request.failed_reason = None
        return self.update(request)

    def update_active_nickname(
        self,
        from_account_id: int,
        to_friend_id: str,
        to_nickname: str,
    ):
        """更新账号对指定 friend_id 的活跃交换请求昵称。"""
        if not to_nickname:
            return
        with Session(get_engine()) as session:
            statement = select(ExchangeCardRequest).where(
                ExchangeCardRequest.from_account_id == from_account_id,
                ExchangeCardRequest.to_friend_id == to_friend_id,
                col(ExchangeCardRequest.status).in_(self.ACTIVE_STATUSES),
            )
            rows = list(session.exec(statement).all())
            if not rows:
                return
            for row in rows:
                row.to_nickname = to_nickname
                row.updated_at = datetime.now()
                session.add(row)
            session.commit()

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
