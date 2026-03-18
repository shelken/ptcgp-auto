# -*- coding: utf-8 -*-
"""
FriendRequestRepository

好友请求数据访问层。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlmodel import col, select

from ptcgp_auto_v2.db.models import AccountFriendRequest
from ptcgp_auto_v2.db.repositories.base import BaseRepository


@dataclass(slots=True)
class FriendRequestSnapshot:
    """好友请求快照。"""

    id: int
    from_account_id: int
    to_account_id: Optional[int]
    to_friend_id: Optional[str]
    to_nickname: Optional[str]
    request_type: str
    status: str
    failed_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class FriendRequestRepository(BaseRepository):
    """好友请求数据访问"""

    def create(
        self,
        from_account_id: int,
        to_friend_id: Optional[str],
        to_account_id: Optional[int] = None,
        to_nickname: Optional[str] = None,
        request_type: str = "add",
        status: str = "sending",
    ) -> AccountFriendRequest:
        """创建请求记录"""
        # 请求去重：同一 (from_account_id, to_friend_id, status) 仅保留一条
        statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.to_friend_id == to_friend_id,
            AccountFriendRequest.status == status,
        )
        existing = self.session.exec(statement).first()
        if existing is not None:
            return existing

        request = AccountFriendRequest(
            from_account_id=from_account_id,
            to_friend_id=to_friend_id,
            to_account_id=to_account_id,
            to_nickname=to_nickname,
            request_type=request_type,
            status=status,
        )
        self.session.add(request)
        self._finish_write(request)
        return request

    def get_by_from_account_and_status_data(
        self, from_account_id: int, status: str
    ) -> List[FriendRequestSnapshot]:
        """获取发送方的指定状态请求快照。"""
        statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.status == status,
        )
        return [
            self._to_data(FriendRequestSnapshot, row)
            for row in self.session.exec(statement).all()
            if row.id is not None
        ]

    def get_by_id(self, request_id: int) -> Optional[AccountFriendRequest]:
        """按主键查询请求记录。"""
        return self.session.get(AccountFriendRequest, request_id)

    def get_by_id_data(self, request_id: int) -> Optional[FriendRequestSnapshot]:
        """按主键查询请求快照。"""
        row = self.session.get(AccountFriendRequest, request_id)
        return None if row is None else self._to_data(FriendRequestSnapshot, row)

    def get_add_requests_by_to_account_and_status_data(
        self, to_account_id: int, status: str
    ) -> List[FriendRequestSnapshot]:
        """获取接收方的指定状态 add 类型请求快照。"""
        statement = select(AccountFriendRequest).where(
            AccountFriendRequest.to_account_id == to_account_id,
            AccountFriendRequest.status == status,
            AccountFriendRequest.request_type == "add",
        )
        return [
            self._to_data(FriendRequestSnapshot, row)
            for row in self.session.exec(statement).all()
            if row.id is not None
        ]

    def get_by_from_account_and_type_data(
        self, from_account_id: int, request_type: str, status: str
    ) -> List[FriendRequestSnapshot]:
        """获取发送方的指定类型和状态的请求快照。"""
        statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.request_type == request_type,
            AccountFriendRequest.status == status,
        )
        return [
            self._to_data(FriendRequestSnapshot, row)
            for row in self.session.exec(statement).all()
            if row.id is not None
        ]

    def get_pending_request(
        self, from_account_id: int, to_friend_id: str
    ) -> Optional[AccountFriendRequest]:
        """获取待处理的请求（应用层防止重复）"""
        sending_statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.to_friend_id == to_friend_id,
            AccountFriendRequest.status == "sending",
        )
        sending_row = self.session.exec(sending_statement).first()
        if sending_row is not None:
            return sending_row

        sended_statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.to_friend_id == to_friend_id,
            AccountFriendRequest.status == "sended",
        )
        return self.session.exec(sended_statement).first()

    def get_pending_request_data(
        self, from_account_id: int, to_friend_id: str
    ) -> Optional[FriendRequestSnapshot]:
        """获取待处理请求快照（sending 优先，其次 sended）。"""
        row = self.get_pending_request(from_account_id, to_friend_id)
        return None if row is None else self._to_data(FriendRequestSnapshot, row)

    def has_pending_delete_request(
        self, from_account_id: int, to_friend_id: str
    ) -> bool:
        """是否存在待处理删除请求（deleting）。"""
        statement = select(AccountFriendRequest.id).where(
            AccountFriendRequest.from_account_id == from_account_id,
            AccountFriendRequest.to_friend_id == to_friend_id,
            AccountFriendRequest.request_type == "delete",
            AccountFriendRequest.status == "deleting",
        )
        return self.session.exec(statement).first() is not None

    def delete_pending(self, request_id: int) -> bool:
        """删除待处理请求（仅 sending/sended/deleting）。"""
        request = self.session.get(AccountFriendRequest, request_id)
        if request is None:
            return False

        if request.status not in {"sending", "sended", "deleting"}:
            return False

        self.session.delete(request)
        self._finish_write()
        return True

    def get_external_sended_requests_data(
        self, from_account_id: int
    ) -> List[FriendRequestSnapshot]:
        """获取发送方的外部好友 sended 请求快照。"""
        statement = select(AccountFriendRequest).where(
            AccountFriendRequest.from_account_id == from_account_id,
            col(AccountFriendRequest.to_account_id).is_(None),
            AccountFriendRequest.status == "sended",
            AccountFriendRequest.request_type == "add",
        )
        return [
            self._to_data(FriendRequestSnapshot, row)
            for row in self.session.exec(statement).all()
            if row.id is not None
        ]

    def update_status(
        self,
        request_id: int,
        status: str,
        failed_reason: Optional[str] = None,
    ) -> bool:
        """按 ID 更新请求状态。"""
        request = self.session.get(AccountFriendRequest, request_id)
        if request is None:
            return False

        request.status = status
        request.failed_reason = failed_reason
        request.updated_at = datetime.now()
        self.session.add(request)
        self._finish_write()
        return True

    def update_nickname(self, request_id: int, nickname: str) -> bool:
        """按 ID 更新请求昵称。"""
        if not nickname:
            return False
        request = self.session.get(AccountFriendRequest, request_id)
        if request is None:
            return False
        request.to_nickname = nickname
        request.updated_at = datetime.now()
        self.session.add(request)
        self._finish_write()
        return True
