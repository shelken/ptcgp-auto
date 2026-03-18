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

from sqlalchemy import event
from ptcgp_auto_v2.db.sqlite_config import (
    SQLITE_BUSY_TIMEOUT_MS,
    apply_sqlite_pragmas,
)

logger = logging.getLogger(__name__)

# 全局数据库实例
_db_instance: Optional["Database"] = None
_db_lock = threading.Lock()


def get_default_db_path() -> Path:
    """获取默认数据库路径（从 settings 获取）"""
    from ptcgp_auto_v2.config.settings import get_settings

    return get_settings().db_path


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
                timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
            )
            apply_sqlite_pragmas(self._local.connection)
            # 使用 Row 对象方便按列名访问
            self._local.connection.row_factory = sqlite3.Row

        return self._local.connection

    def _init_schema(self):
        """初始化数据库表结构（自动同步模式）"""
        from sqlmodel import SQLModel, create_engine

        # 创建用于 Schema 管理的 Engine
        engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={
                "check_same_thread": False,
                "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
            },
        )
        event.listen(engine, "connect", apply_sqlite_pragmas)

        # 1. 自动创建所有不存在的表
        SQLModel.metadata.create_all(engine)

        # 2. 自动检查并添加缺失的列 (Auto-Migration)
        self._auto_migrate_columns(engine)

        # 3. 初始化默认数据
        self._init_default_data(engine)

    def _auto_migrate_columns(self, engine):
        """对比 Model 定义与数据库现状，自动添加缺失列"""
        from sqlmodel import SQLModel, inspect, text

        inspector = inspect(engine)

        with engine.connect() as conn:
            # 遍历所有注册的 Model
            for table_name, table in SQLModel.metadata.tables.items():
                if not inspector.has_table(table_name):
                    continue

                # 获取数据库中现有的列名
                existing_columns = {
                    col["name"] for col in inspector.get_columns(table_name)
                }

                # 遍历 Model 定义的列
                for column in table.columns:
                    if column.name not in existing_columns:
                        # 生成 ALTER TABLE 语句
                        # 注意：SQLite 对 ALTER TABLE 支持有限，仅支持添加特定类型的列
                        col_type = column.type.compile(engine.dialect)
                        default_val = ""

                        # 处理默认值 (简单处理，非空字段必须有默认值)
                        if column.server_default is not None:
                            # 如果有 server_default，直接使用
                            if hasattr(column.server_default, "arg"):
                                default_val = f" DEFAULT {column.server_default.arg}"
                            else:
                                default_val = f" DEFAULT {column.server_default}"
                        elif not column.nullable:
                            # 非空且无默认值时，提供安全默认值
                            type_str = str(col_type).upper()
                            if "INT" in type_str:
                                default_val = " DEFAULT 0"
                            elif "FLOAT" in type_str:
                                default_val = " DEFAULT 0.0"
                            else:
                                default_val = " DEFAULT ''"

                        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}{default_val}'
                        try:
                            conn.execute(text(sql))
                            logger.info(
                                f"自动迁移: 表 {table_name} 添加列 {column.name}"
                            )
                        except Exception as e:
                            logger.error(
                                f"自动迁移失败 {table_name}.{column.name}: {e}"
                            )
            conn.commit()

    def _init_default_data(self, engine):
        """初始化默认数据"""
        from sqlmodel import text

        with engine.connect() as conn:
            # 插入默认任务计划 (如果不存在)
            # 使用原生 SQL 以避免 Model 依赖复杂性
            sql = """
            INSERT OR IGNORE INTO task_plans (name, description, task_types, created_at)
            VALUES ('base', '基础任务计划', '[]', datetime('now', 'localtime'))
            """
            conn.execute(text(sql))

            # 迁移历史账号资源字段：accounts.exchange_points -> account_stats.exchange_points
            # 说明：部分历史库已删除旧列；只有旧列仍存在时才执行回填。
            if self._table_has_column(conn, "accounts", "exchange_points"):
                migrate_sql = """
                INSERT INTO account_stats (account_id, exchange_points, created_at, updated_at)
                SELECT a.id, a.exchange_points, datetime('now', 'localtime'), datetime('now', 'localtime')
                FROM accounts a
                WHERE a.exchange_points IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM account_stats s WHERE s.account_id = a.id
                  )
                """
                conn.execute(text(migrate_sql))
            else:
                logger.info("跳过账号资源旧字段迁移：accounts.exchange_points 列不存在")
            conn.commit()

    def _table_has_column(self, conn, table_name: str, column_name: str) -> bool:
        """检查指定表是否仍包含目标列。"""
        from sqlmodel import text

        pragma_sql = f'PRAGMA table_info("{table_name}")'
        rows = conn.execute(text(pragma_sql)).fetchall()
        return any(row[1] == column_name for row in rows)

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
