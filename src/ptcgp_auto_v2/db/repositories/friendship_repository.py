# -*- coding: utf-8 -*-
"""
FriendshipRepository

好友关系数据访问层。
"""

from typing import List, Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountFriendship


class FriendshipRepository:
    """好友关系数据访问"""

    def create(
        self, account_id: int, friend_id: str, friend_account_id: Optional[int] = None
    ) -> AccountFriendship:
        """创建好友关系（幂等，如果已存在则返回现有记录）"""
        with Session(get_engine()) as session:
            existing = self._get_by_account_and_friend(session, account_id, friend_id)
            if existing:
                return existing

            friendship = AccountFriendship(
                account_id=account_id,
                friend_id=friend_id,
                friend_account_id=friend_account_id,
            )
            session.add(friendship)
            session.commit()
            session.refresh(friendship)
            return friendship

    def _get_by_account_and_friend(
        self, session: Session, account_id: int, friend_id: str
    ) -> Optional[AccountFriendship]:
        """内部方法：根据账号和好友ID查询"""
        statement = select(AccountFriendship).where(
            AccountFriendship.account_id == account_id,
            AccountFriendship.friend_id == friend_id,
        )
        return session.exec(statement).first()

    def exists(self, account_id: int, friend_id: str) -> bool:
        """检查好友关系是否存在"""
        with Session(get_engine()) as session:
            return (
                self._get_by_account_and_friend(session, account_id, friend_id)
                is not None
            )

    def get_friendship(
        self, account_id: int, friend_id: str
    ) -> Optional[AccountFriendship]:
        """获取单条好友关系记录。"""
        with Session(get_engine()) as session:
            return self._get_by_account_and_friend(session, account_id, friend_id)

    def delete(self, account_id: int, friend_id: str) -> bool:
        """删除好友关系（物理删除）"""
        with Session(get_engine()) as session:
            friendship = self._get_by_account_and_friend(session, account_id, friend_id)
            if friendship:
                session.delete(friendship)
                session.commit()
                return True
            return False

    def remove_friendship(self, account_id: int, friend_id: str) -> None:
        """删除双向好友关系（A→B 与 B→A）"""
        with Session(get_engine()) as session:
            forward = self._get_by_account_and_friend(session, account_id, friend_id)
            if forward:
                session.delete(forward)

                if forward.friend_account_id:
                    statement = select(AccountFriendship).where(
                        AccountFriendship.account_id == forward.friend_account_id,
                        AccountFriendship.friend_account_id == account_id,
                    )
                    reverse = session.exec(statement).first()
                    if reverse:
                        session.delete(reverse)

            session.commit()

    def update_nickname(self, account_id: int, friend_id: str, nickname: str) -> bool:
        """更新好友昵称（系统外账号从游戏获取）。"""
        if not nickname:
            return False
        with Session(get_engine()) as session:
            friendship = self._get_by_account_and_friend(session, account_id, friend_id)
            if friendship is None:
                return False
            friendship.friend_nickname = nickname
            session.add(friendship)
            session.commit()
            return True
