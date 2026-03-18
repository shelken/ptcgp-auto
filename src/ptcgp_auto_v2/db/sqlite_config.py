# -*- coding: utf-8 -*-
"""
SQLite 连接配置

统一维护运行期需要的 SQLite PRAGMA，避免不同入口行为不一致。
"""


SQLITE_BUSY_TIMEOUT_MS = 30_000


def apply_sqlite_pragmas(dbapi_connection, _connection_record=None) -> None:
    """对单个 SQLite 连接应用统一 PRAGMA。"""
    cursor = dbapi_connection.cursor()
    try:
        # 项目已移除物理外键约束，统一关闭。
        cursor.execute("PRAGMA foreign_keys = OFF")
        # WAL 允许并发读 + 单写，适合当前多线程任务场景。
        cursor.execute("PRAGMA journal_mode = WAL")
        # WAL 下使用 NORMAL，同步成本更低，足够满足当前 SQLite 任务库场景。
        cursor.execute("PRAGMA synchronous = NORMAL")
        # 遇到写锁时等待，而不是直接抛 database is locked。
        cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()
