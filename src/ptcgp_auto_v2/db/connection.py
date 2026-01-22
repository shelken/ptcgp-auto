# -*- coding: utf-8 -*-
"""
数据库连接管理模块

使用 SQLite 作为默认数据库，支持单例模式和线程安全。
"""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 全局数据库实例
_db_instance: Optional["Database"] = None
_db_lock = threading.Lock()

# 默认数据库路径
DEFAULT_DB_NAME = "ptcgp_v2.db"


def get_default_db_path() -> Path:
    """获取默认数据库路径"""
    # 优先使用项目的 data 目录
    project_root = Path(__file__).parent.parent.parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / DEFAULT_DB_NAME


class Database:
    """
    SQLite 数据库连接管理器

    支持线程安全的连接池和自动 Schema 初始化。
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认为 data/ptcgp_v2.db
        """
        if db_path is None:
            db_path = get_default_db_path()

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
        -- 任务计划表
        CREATE TABLE IF NOT EXISTS task_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            task_types TEXT NOT NULL,  -- JSON 数组: ["open_pack", "send_gift"]
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        -- 账号表
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE NOT NULL,  -- deviceAccount 字段，唯一标识
            friend_id TEXT,                -- 朋友 ID，格式 XXXX-XXXX-XXXX-XXXX
            nintendo_id TEXT,              -- Nintendo 账号 ID（从 JWT 解析）
            nickname TEXT,                 -- 用户昵称
            country TEXT,                  -- 国家/地区代码
            xml_content BLOB,              -- XML 文件内容
            task_plan_id INTEGER,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (task_plan_id) REFERENCES task_plans(id) ON DELETE SET NULL
        );

        -- 任务实例表
        CREATE TABLE IF NOT EXISTS task_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending/running/completed/failed
            reset_type TEXT NOT NULL DEFAULT 'daily',  -- daily/weekly/once
            error_message TEXT,
            last_completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            UNIQUE(account_id, task_type)
        );

        -- 开包记录表
        CREATE TABLE IF NOT EXISTS pack_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            pack_type TEXT NOT NULL,
            opened_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        -- 账号开包配置表
        CREATE TABLE IF NOT EXISTS account_pack_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            pack_code TEXT NOT NULL,
            booster_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            UNIQUE(account_id, type)
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_accounts_game_id ON accounts(game_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_friend_id ON accounts(friend_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_task_plan ON accounts(task_plan_id);
        CREATE INDEX IF NOT EXISTS idx_task_instances_account ON task_instances(account_id);
        CREATE INDEX IF NOT EXISTS idx_task_instances_status ON task_instances(status);
        CREATE INDEX IF NOT EXISTS idx_pack_records_account_id ON pack_records(account_id);
        CREATE INDEX IF NOT EXISTS idx_pack_records_opened_at ON pack_records(opened_at);
        CREATE INDEX IF NOT EXISTS idx_pack_config_account ON account_pack_config(account_id);
        CREATE INDEX IF NOT EXISTS idx_pack_config_type ON account_pack_config(type);

        -- 插入默认任务计划
        INSERT OR IGNORE INTO task_plans (name, description, task_types)
        VALUES ('daily', '每日任务计划', '["open_pack", "send_gift"]');
        """

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(schema)
            # 执行迁移（添加新列到已存在的表）
            self._migrate_accounts_table(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate_accounts_table(self, conn: sqlite3.Connection):
        """迁移 accounts 表，添加新列（如果不存在）"""
        # 获取现有列
        cursor = conn.execute("PRAGMA table_info(accounts)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 需要添加的新列
        new_columns = [
            ("friend_id", "TEXT"),
            ("nintendo_id", "TEXT"),
            ("country", "TEXT"),
            ("xml_content", "BLOB"),
            ("session_token_iat", "INTEGER"),
            ("level", "INTEGER"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    conn.execute(
                        f"ALTER TABLE accounts ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"添加列 accounts.{col_name}")
                except sqlite3.OperationalError:
                    pass  # 列已存在

        # 移除旧索引（如果存在）
        try:
            conn.execute("DROP INDEX IF EXISTS idx_accounts_xml_hash")
        except sqlite3.OperationalError:
            pass

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

    def connect(self):
        """显式建立连接"""
        _ = self.connection

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


def reset_database():
    """重置全局数据库实例（仅用于测试）"""
    global _db_instance

    with _db_lock:
        if _db_instance is not None:
            _db_instance.close()
            _db_instance = None
