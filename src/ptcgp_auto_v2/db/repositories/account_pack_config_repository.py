# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from sqlmodel import select

from ptcgp_auto_v2.db.models import AccountPackConfig
from .base import BaseRepository


class AccountPackConfigRepository(BaseRepository):
    """账号开包配置数据访问层"""

    def get_by_account_and_type(
        self, account_id: int, config_type: str
    ) -> Optional[AccountPackConfig]:
        """根据账号和类型获取开包配置"""
        statement = select(AccountPackConfig).where(
            AccountPackConfig.account_id == account_id,
            AccountPackConfig.type == config_type,
        )
        return self.session.exec(statement).first()

    def get_by_account(self, account_id: int) -> List[AccountPackConfig]:
        """获取账号的所有开包配置"""
        statement = (
            select(AccountPackConfig)
            .where(AccountPackConfig.account_id == account_id)
            .order_by(AccountPackConfig.type)
        )
        return list(self.session.exec(statement).all())

    def create(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建开包配置"""
        self.session.add(config)
        self._finish_write(config)
        return config

    def update(self, config: AccountPackConfig) -> bool:
        """更新开包配置"""
        db_config = self.session.get(AccountPackConfig, config.id)
        if not db_config:
            return False
        db_config.type = config.type
        db_config.pack_code = config.pack_code
        db_config.booster_name = config.booster_name
        db_config.updated_at = datetime.now()
        self.session.add(db_config)
        self._finish_write()
        return True

    def upsert(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建或更新开包配置"""
        existing = self.get_by_account_and_type(config.account_id, config.type)
        if existing:
            config.id = existing.id
            self.update(config)
            return config
        return self.create(config)

    def delete(self, config_id: int) -> bool:
        """删除开包配置"""
        config = self.session.get(AccountPackConfig, config_id)
        if config:
            self.session.delete(config)
            self._finish_write()
            return True
        return False

    def delete_by_account_and_type(self, account_id: int, config_type: str) -> bool:
        """根据账号和类型删除开包配置"""
        statement = select(AccountPackConfig).where(
            AccountPackConfig.account_id == account_id,
            AccountPackConfig.type == config_type,
        )
        config = self.session.exec(statement).first()
        if config:
            self.session.delete(config)
            self._finish_write()
            return True
        return False
