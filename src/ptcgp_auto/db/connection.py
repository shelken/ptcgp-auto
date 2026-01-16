"""
数据库连接管理

使用 SQLite 作为默认数据库，支持单例模式。
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from ..utils import get_data_dir
from ..logger import get_logger

logger = get_logger(__name__)

# 全局数据库实例
_db_instance: Optional["Database"] = None
_db_lock = threading.Lock()


class Database:
    """SQLite 数据库连接管理器"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认为数据目录下的 ptcgp.db
        """
        if db_path is None:
            # 使用全局数据目录
            data_dir = get_data_dir()
            db_path = data_dir / "ptcgp.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_schema()

        logger.info(f"数据库已初始化: {self.db_path}")

    @property
    def connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（线程安全）"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            # 启用外键约束
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            # 使用 Row 对象方便按列名访问
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_schema(self):
        """初始化数据库表结构"""
        schema = """
        -- 账号表
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE NOT NULL,
            username TEXT,
            xml_path TEXT,
            xml_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 开包记录表
        CREATE TABLE IF NOT EXISTS pack_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            pack_type TEXT NOT NULL,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        -- 账号配置表
        CREATE TABLE IF NOT EXISTS account_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL UNIQUE,
            pack_preference TEXT,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_accounts_game_id ON accounts(game_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_xml_hash ON accounts(xml_hash);
        CREATE INDEX IF NOT EXISTS idx_pack_records_account_id ON pack_records(account_id);
        CREATE INDEX IF NOT EXISTS idx_pack_records_opened_at ON pack_records(opened_at);
        """

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(schema)
            conn.commit()
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL 语句"""
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """批量执行 SQL 语句"""
        return self.connection.executemany(sql, params_list)

    def commit(self):
        """提交事务"""
        self.connection.commit()

    def rollback(self):
        """回滚事务"""
        self.connection.rollback()

    def close(self):
        """关闭当前线程的连接"""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """
    获取全局数据库实例（单例模式）

    Args:
        db_path: 可选的数据库路径，仅在首次调用时有效

    Returns:
        Database 实例
    """
    global _db_instance

    with _db_lock:
        if _db_instance is None:
            _db_instance = Database(db_path)
        return _db_instance
