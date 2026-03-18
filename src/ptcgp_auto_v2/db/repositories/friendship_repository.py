# -*- coding: utf-8 -*-
"""
FriendshipRepository

好友关系数据访问层。
"""

from typing import Optional

from sqlmodel import select

from ptcgp_auto_v2.db.models import AccountFriendship
from ptcgp_auto_v2.db.repositories.base import BaseRepository


class FriendshipRepository(BaseRepository):
    """好友关系数据访问"""

    def create(
        self, account_id: int, friend_id: str, friend_account_id: Optional[int] = None
    ) -> AccountFriendship:
        """创建好友关系（幂等，如果已存在则返回现有记录）"""
        existing = self._get_by_account_and_friend(account_id, friend_id)
        if existing:
            return existing

        friendship = AccountFriendship(
            account_id=account_id,
            friend_id=friend_id,
            friend_account_id=friend_account_id,
        )
        self.session.add(friendship)
        self._finish_write(friendship)
        return friendship

    def _get_by_account_and_friend(
        self, account_id: int, friend_id: str
    ) -> Optional[AccountFriendship]:
        """内部方法：根据账号和好友ID查询"""
        statement = select(AccountFriendship).where(
            AccountFriendship.account_id == account_id,
            AccountFriendship.friend_id == friend_id,
        )
        return self.session.exec(statement).first()

    def exists(self, account_id: int, friend_id: str) -> bool:
        """检查好友关系是否存在"""
        return self._get_by_account_and_friend(account_id, friend_id) is not None

    def get_friendship(
        self, account_id: int, friend_id: str
    ) -> Optional[AccountFriendship]:
        """获取单条好友关系记录。"""
        return self._get_by_account_and_friend(account_id, friend_id)

    def delete(self, account_id: int, friend_id: str) -> bool:
        """删除好友关系（物理删除）"""
        friendship = self._get_by_account_and_friend(account_id, friend_id)
        if friendship:
            self.session.delete(friendship)
            self._finish_write()
            return True
        return False

    def remove_friendship(self, account_id: int, friend_id: str) -> None:
        """删除双向好友关系（A→B 与 B→A）"""
        forward = self._get_by_account_and_friend(account_id, friend_id)
        if forward:
            self.session.delete(forward)

            if forward.friend_account_id:
                statement = select(AccountFriendship).where(
                    AccountFriendship.account_id == forward.friend_account_id,
                    AccountFriendship.friend_account_id == account_id,
                )
                reverse = self.session.exec(statement).first()
                if reverse:
                    self.session.delete(reverse)

        self._finish_write()

    def update_nickname(self, account_id: int, friend_id: str, nickname: str) -> bool:
        """更新好友昵称（系统外账号从游戏获取）。"""
        if not nickname:
            return False
        friendship = self._get_by_account_and_friend(account_id, friend_id)
        if friendship is None:
            return False
        friendship.friend_nickname = nickname
        self.session.add(friendship)
        self._finish_write()
        return True
