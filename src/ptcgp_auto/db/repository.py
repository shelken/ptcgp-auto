"""
数据访问层

提供账号和开包记录的 CRUD 操作。
"""

from datetime import datetime, timedelta
from typing import List, Optional

from .connection import Database
from .models import Account, PackRecord, AccountConfig
from ..logger import get_logger

logger = get_logger(__name__)


class AccountRepository:
    """账号数据访问仓库"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, account: Account) -> Account:
        """
        创建新账号

        Args:
            account: 账号对象（id 会被忽略）

        Returns:
            创建后的账号对象（包含生成的 id）
        """
        cursor = self.db.execute(
            """
            INSERT INTO accounts (game_id, username, xml_path, xml_hash)
            VALUES (?, ?, ?, ?)
            """,
            (account.game_id, account.username, account.xml_path, account.xml_hash),
        )
        self.db.commit()
        account.id = cursor.lastrowid
        logger.debug(f"创建账号: {account.game_id} (id={account.id})")
        return account

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        cursor = self.db.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        )
        row = cursor.fetchone()
        return Account.from_row(row)

    def get_by_game_id(self, game_id: str) -> Optional[Account]:
        """根据游戏 ID 获取账号"""
        cursor = self.db.execute(
            "SELECT * FROM accounts WHERE game_id = ?", (game_id,)
        )
        row = cursor.fetchone()
        return Account.from_row(row)

    def get_by_xml_hash(self, xml_hash: str) -> Optional[Account]:
        """根据 XML 哈希获取账号"""
        cursor = self.db.execute(
            "SELECT * FROM accounts WHERE xml_hash = ?", (xml_hash,)
        )
        row = cursor.fetchone()
        return Account.from_row(row)

    def get_all(self, enabled_only: bool = False) -> List[Account]:
        """
        获取所有账号

        Args:
            enabled_only: 是否只返回启用的账号
        """
        if enabled_only:
            cursor = self.db.execute(
                """
                SELECT a.* FROM accounts a
                LEFT JOIN account_configs c ON a.id = c.account_id
                WHERE c.enabled = 1 OR c.enabled IS NULL
                ORDER BY a.id
                """
            )
        else:
            cursor = self.db.execute("SELECT * FROM accounts ORDER BY id")
        return [Account.from_row(row) for row in cursor.fetchall()]

    def update(self, account: Account) -> bool:
        """
        更新账号信息

        Args:
            account: 要更新的账号对象

        Returns:
            是否更新成功
        """
        if account.id is None:
            return False

        self.db.execute(
            """
            UPDATE accounts
            SET username = ?, xml_path = ?, xml_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (account.username, account.xml_path, account.xml_hash, account.id),
        )
        self.db.commit()
        logger.debug(f"更新账号: {account.game_id} (id={account.id})")
        return True

    def delete(self, account_id: int) -> bool:
        """删除账号"""
        self.db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.db.commit()
        logger.debug(f"删除账号: id={account_id}")
        return True

    def count(self) -> int:
        """获取账号总数"""
        cursor = self.db.execute("SELECT COUNT(*) as cnt FROM accounts")
        return cursor.fetchone()["cnt"]


class PackRecordRepository:
    """开包记录数据访问仓库"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, record: PackRecord) -> PackRecord:
        """创建开包记录"""
        cursor = self.db.execute(
            """
            INSERT INTO pack_records (account_id, pack_type)
            VALUES (?, ?)
            """,
            (record.account_id, record.pack_type),
        )
        self.db.commit()
        record.id = cursor.lastrowid
        return record

    def get_last_pack_time(self, account_id: int) -> Optional[datetime]:
        """
        获取账号最后一次开包时间

        Args:
            account_id: 账号 ID

        Returns:
            最后开包时间，如果从未开过包则返回 None
        """
        cursor = self.db.execute(
            """
            SELECT MAX(opened_at) as last_opened
            FROM pack_records
            WHERE account_id = ?
            """,
            (account_id,),
        )
        row = cursor.fetchone()
        if row and row["last_opened"]:
            try:
                return datetime.fromisoformat(
                    row["last_opened"].replace(" ", "T")
                )
            except (ValueError, AttributeError):
                return None
        return None

    def get_accounts_pending_packs(self, hours: int = 24) -> List[Account]:
        """
        获取待开包的账号（上次开包时间超过指定小时数）

        Args:
            hours: 时间阈值（小时）

        Returns:
            待开包的账号列表
        """
        threshold = datetime.now() - timedelta(hours=hours)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        cursor = self.db.execute(
            """
            SELECT a.* FROM accounts a
            LEFT JOIN account_configs c ON a.id = c.account_id
            WHERE (c.enabled = 1 OR c.enabled IS NULL)
            AND (
                a.id NOT IN (SELECT DISTINCT account_id FROM pack_records)
                OR a.id IN (
                    SELECT account_id FROM pack_records
                    GROUP BY account_id
                    HAVING MAX(opened_at) < ?
                )
            )
            ORDER BY a.id
            """,
            (threshold_str,),
        )
        return [Account.from_row(row) for row in cursor.fetchall()]

    def get_records_by_account(
        self, account_id: int, limit: int = 10
    ) -> List[PackRecord]:
        """获取账号的开包记录"""
        cursor = self.db.execute(
            """
            SELECT * FROM pack_records
            WHERE account_id = ?
            ORDER BY opened_at DESC
            LIMIT ?
            """,
            (account_id, limit),
        )
        return [PackRecord.from_row(row) for row in cursor.fetchall()]


class AccountConfigRepository:
    """账号配置数据访问仓库"""

    def __init__(self, db: Database):
        self.db = db

    def get_or_create(self, account_id: int) -> AccountConfig:
        """获取或创建账号配置"""
        cursor = self.db.execute(
            "SELECT * FROM account_configs WHERE account_id = ?",
            (account_id,),
        )
        row = cursor.fetchone()
        if row:
            return AccountConfig.from_row(row)

        # 创建默认配置
        config = AccountConfig(account_id=account_id)
        cursor = self.db.execute(
            """
            INSERT INTO account_configs (account_id, pack_preference, enabled)
            VALUES (?, ?, ?)
            """,
            (account_id, config.pack_preference_json(), config.enabled),
        )
        self.db.commit()
        config.id = cursor.lastrowid
        return config

    def update(self, config: AccountConfig) -> bool:
        """更新账号配置"""
        if config.id is None:
            return False

        self.db.execute(
            """
            UPDATE account_configs
            SET pack_preference = ?, enabled = ?
            WHERE id = ?
            """,
            (config.pack_preference_json(), config.enabled, config.id),
        )
        self.db.commit()
        return True

    def set_enabled(self, account_id: int, enabled: bool) -> bool:
        """设置账号启用状态"""
        config = self.get_or_create(account_id)
        config.enabled = enabled
        return self.update(config)
