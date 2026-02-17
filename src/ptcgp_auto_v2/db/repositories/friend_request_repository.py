# -*- coding: utf-8 -*-
"""
FriendRequestRepository

好友请求数据访问层。
"""

from typing import List, Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountFriendRequest


class FriendRequestRepository:
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
        with Session(get_engine()) as session:
            # 请求去重：同一 (from_account_id, to_friend_id, status) 仅保留一条
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.status == status,
            )
            existing = session.exec(statement).first()
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
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def get_by_from_account_and_status(
        self, from_account_id: int, status: str
    ) -> List[AccountFriendRequest]:
        """获取发送方的指定状态请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.status == status,
            )
            return list(session.exec(statement).all())

    def get_by_id(self, request_id: int) -> Optional[AccountFriendRequest]:
        """按主键查询请求记录。"""
        with Session(get_engine()) as session:
            return session.get(AccountFriendRequest, request_id)

    def get_by_to_account_and_status(
        self, to_account_id: int, status: str
    ) -> List[AccountFriendRequest]:
        """获取接收方的指定状态请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.to_account_id == to_account_id,
                AccountFriendRequest.status == status,
            )
            return list(session.exec(statement).all())

    def get_add_requests_by_to_account_and_status(
        self, to_account_id: int, status: str
    ) -> List[AccountFriendRequest]:
        """获取接收方的指定状态 add 类型请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.to_account_id == to_account_id,
                AccountFriendRequest.status == status,
                AccountFriendRequest.request_type == "add",
            )
            return list(session.exec(statement).all())

    def get_by_from_account_and_type(
        self, from_account_id: int, request_type: str, status: str
    ) -> List[AccountFriendRequest]:
        """获取发送方的指定类型和状态的请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.request_type == request_type,
                AccountFriendRequest.status == status,
            )
            return list(session.exec(statement).all())

    def get_pending_request(
        self, from_account_id: int, to_friend_id: str
    ) -> Optional[AccountFriendRequest]:
        """获取待处理的请求（应用层防止重复）"""
        with Session(get_engine()) as session:
            sending_statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.status == "sending",
            )
            sending_row = session.exec(sending_statement).first()
            if sending_row is not None:
                return sending_row

            sended_statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.status == "sended",
            )
            return session.exec(sended_statement).first()

    def get_by_account_friend_status(
        self,
        from_account_id: int,
        to_friend_id: str,
        status: str,
    ) -> Optional[AccountFriendRequest]:
        """按 (from_account_id, to_friend_id, status) 查询请求。"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.status == status,
            )
            return session.exec(statement).first()

    def has_pending_add_request(self, from_account_id: int, to_friend_id: str) -> bool:
        """是否存在待处理添加请求（sending/sended）。"""
        with Session(get_engine()) as session:
            sending_statement = select(AccountFriendRequest.id).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.request_type == "add",
                AccountFriendRequest.status == "sending",
            )
            if session.exec(sending_statement).first() is not None:
                return True

            sended_statement = select(AccountFriendRequest.id).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.request_type == "add",
                AccountFriendRequest.status == "sended",
            )
            return session.exec(sended_statement).first() is not None

    def has_pending_delete_request(
        self, from_account_id: int, to_friend_id: str
    ) -> bool:
        """是否存在待处理删除请求（deleting）。"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest.id).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.request_type == "delete",
                AccountFriendRequest.status == "deleting",
            )
            return session.exec(statement).first() is not None

    def update(self, request: AccountFriendRequest) -> AccountFriendRequest:
        """更新请求记录"""
        with Session(get_engine()) as session:
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def update_nickname(self, request_id: int, nickname: str) -> bool:
        """更新请求目标昵称。"""
        if not nickname:
            return False
        with Session(get_engine()) as session:
            request = session.get(AccountFriendRequest, request_id)
            if request is None:
                return False
            request.to_nickname = nickname
            session.add(request)
            session.commit()
            return True

    def delete_pending(self, request_id: int) -> bool:
        """删除待处理请求（仅 sending/sended/deleting）。"""
        with Session(get_engine()) as session:
            request = session.get(AccountFriendRequest, request_id)
            if request is None:
                return False

            if request.status not in {"sending", "sended", "deleting"}:
                return False

            session.delete(request)
            session.commit()
            return True

    def get_external_sended_requests(
        self, from_account_id: int
    ) -> List[AccountFriendRequest]:
        """获取发送方的外部好友 sended 请求（to_account_id 为 null）。"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_account_id == None,
                AccountFriendRequest.status == "sended",
                AccountFriendRequest.request_type == "add",
            )
            return list(session.exec(statement).all())
