# -*- coding: utf-8 -*-
"""数据库初始化迁移测试。"""

from pathlib import Path

from sqlmodel import create_engine, text

from ptcgp_auto_v2.db.connection import Database


def _create_database_shell(db_path: Path) -> Database:
    """构造一个跳过 __init__ 的 Database 实例供单元测试调用。"""
    database = Database.__new__(Database)
    database.db_path = db_path
    return database


def test_init_default_data_skips_exchange_points_migration_without_legacy_column(
    tmp_path: Path,
):
    """当旧列不存在时，初始化应跳过回填而不是抛异常。"""
    db_path = tmp_path / "missing_legacy_column.db"
    engine = create_engine(f"sqlite:///{db_path}")
    database = _create_database_shell(db_path)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE task_plans (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    task_types TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                """
                CREATE TABLE account_stats (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    exchange_points INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )

    database._init_default_data(engine)

    with engine.connect() as conn:
        plan_count = conn.execute(
            text("SELECT COUNT(*) FROM task_plans WHERE name = 'base'")
        ).scalar_one()
        stat_count = conn.execute(text("SELECT COUNT(*) FROM account_stats")).scalar_one()

    assert plan_count == 1
    assert stat_count == 0


def test_init_default_data_migrates_exchange_points_when_legacy_column_exists(
    tmp_path: Path,
):
    """当旧列存在时，应仅回填缺失且非空的账号资源数据。"""
    db_path = tmp_path / "with_legacy_column.db"
    engine = create_engine(f"sqlite:///{db_path}")
    database = _create_database_shell(db_path)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE task_plans (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    task_types TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY,
                    exchange_points INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE account_stats (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    exchange_points INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO accounts (id, exchange_points)
                VALUES (1, 100), (2, NULL), (3, 300)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO account_stats (account_id, exchange_points, created_at, updated_at)
                VALUES (3, 999, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """
            )
        )

    database._init_default_data(engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT account_id, exchange_points
                FROM account_stats
                ORDER BY account_id
                """
            )
        ).fetchall()

    assert rows == [(1, 100), (3, 999)]
