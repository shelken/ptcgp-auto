# -*- coding: utf-8 -*-
"""
ExchangeCardRequestRepository

交换卡牌请求数据访问层。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import col, select

from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.db.repositories.base import BaseRepository


@dataclass(slots=True)
class ExchangeCardRequestSnapshot:
    """交换请求快照。"""

    id: int
    from_account_id: int
    to_account_id: Optional[int]
    to_friend_id: str
    to_nickname: Optional[str]
    target_card_id: int
    target_card_rarity: str
    status: str
    failed_reason: Optional[str]
    cancel_reason: Optional[str]
    next_check_at: Optional[datetime]
    expire_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


_UNCHANGED = object()


class ExchangeCardRequestRepository(BaseRepository):
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
        active = self._get_active_by_account_with_session(from_account_id)
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
        self.session.add(request)
        self._finish_write(request)
        return request

    def get_by_id(self, request_id: int) -> Optional[ExchangeCardRequest]:
        """按主键查询请求。"""
        return self.session.get(ExchangeCardRequest, request_id)

    def get_by_id_data(self, request_id: int) -> Optional[ExchangeCardRequestSnapshot]:
        """按主键查询请求快照。"""
        row = self.session.get(ExchangeCardRequest, request_id)
        return None if row is None else self._to_data(ExchangeCardRequestSnapshot, row)

    def get_active_by_account_data(
        self, from_account_id: int
    ) -> Optional[ExchangeCardRequestSnapshot]:
        """查询账号当前活跃请求快照。"""
        row = self._get_active_by_account_with_session(from_account_id)
        return None if row is None else self._to_data(ExchangeCardRequestSnapshot, row)

    def has_active_request(self, from_account_id: int) -> bool:
        """判断账号是否存在活跃请求（sending/sended）。"""
        return self._get_active_by_account_with_session(from_account_id) is not None

    def update_fields_by_id(
        self,
        request_id: int,
        *,
        status: str | object = _UNCHANGED,
        failed_reason: Optional[str] | object = _UNCHANGED,
        cancel_reason: Optional[str] | object = _UNCHANGED,
        next_check_at: Optional[datetime] | object = _UNCHANGED,
        expire_at: Optional[datetime] | object = _UNCHANGED,
        to_nickname: Optional[str] | object = _UNCHANGED,
    ) -> bool:
        """按 ID 更新交换请求字段。"""
        request = self.session.get(ExchangeCardRequest, request_id)
        if request is None:
            return False

        for field_name, value in (
            ("status", status),
            ("failed_reason", failed_reason),
            ("cancel_reason", cancel_reason),
            ("next_check_at", next_check_at),
            ("expire_at", expire_at),
            ("to_nickname", to_nickname),
        ):
            if value is not _UNCHANGED:
                setattr(request, field_name, value)
        request.updated_at = datetime.now()
        self.session.add(request)
        self._finish_write()
        return True

    def mark_sended(
        self,
        request_id: int,
        next_check_at: Optional[datetime],
    ) -> bool:
        """按 ID 标记请求为 sended。"""
        return self.update_fields_by_id(
            request_id,
            status="sended",
            failed_reason=None,
            cancel_reason=None,
            next_check_at=next_check_at,
            expire_at=None,
        )

    def mark_failed(
        self, request_id: int, reason: str
    ) -> bool:
        """按 ID 标记请求为 failed。"""
        return self.update_fields_by_id(
            request_id,
            status="failed",
            failed_reason=reason,
            cancel_reason=None,
            next_check_at=None,
            expire_at=None,
        )

    def mark_canceled(
        self,
        request_id: int,
        reason: Optional[str] = None,
    ) -> bool:
        """按 ID 标记请求为 canceled。"""
        return self.update_fields_by_id(
            request_id,
            status="canceled",
            failed_reason=None,
            cancel_reason=reason,
            next_check_at=None,
            expire_at=None,
        )

    def mark_completed(self, request_id: int) -> bool:
        """按 ID 标记请求为 completed。"""
        return self.update_fields_by_id(
            request_id,
            status="completed",
            failed_reason=None,
            cancel_reason=None,
            next_check_at=None,
            expire_at=None,
        )

    def set_cancel_reason(self, request_id: int, reason: Optional[str]) -> bool:
        """设置取消原因。"""
        return self.update_fields_by_id(request_id, cancel_reason=reason)

    def update_active_nickname(
        self,
        from_account_id: int,
        to_friend_id: str,
        to_nickname: str,
    ):
        """更新账号对指定 friend_id 的活跃交换请求昵称。"""
        if not to_nickname:
            return
        statement = select(ExchangeCardRequest).where(
            ExchangeCardRequest.from_account_id == from_account_id,
            ExchangeCardRequest.to_friend_id == to_friend_id,
            col(ExchangeCardRequest.status).in_(self.ACTIVE_STATUSES),
        )
        rows = list(self.session.exec(statement).all())
        if not rows:
            return
        for row in rows:
            row.to_nickname = to_nickname
            row.updated_at = datetime.now()
            self.session.add(row)
        self._finish_write(*rows)

    def _get_active_by_account_with_session(
        self,
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
        return self.session.exec(statement).first()
